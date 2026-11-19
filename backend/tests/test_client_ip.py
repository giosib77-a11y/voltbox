"""The client's IP address behind Render and Cloudflare (A-117).

On Render the peer the app sees is always loopback, so `request.client.host`
made every shopper one rate-limit bucket and every audit row `127.0.0.1`.
`client_ip` reads Cloudflare's `CF-Connecting-IP`, but only from a trusted peer
(loopback, or FORWARDED_ALLOW_IPS) and only when it is exactly one bare address.

The first half is the function on its own; the second half drives the real app,
because the point is that the audit log and the access line - not only the
function - see the address.
"""

import json
import logging
from collections.abc import AsyncGenerator, Callable, Generator

import httpx
import pytest
from app.core.client_ip import client_ip
from app.core.config import settings
from app.core.logging import NO_CLIENT, JsonFormatter, client_pseudonym
from app.core.rate_limit import client_key
from app.db.models import ROLE_ADMIN, AdminAuditLog
from app.db.session import get_db
from app.main import app, create_app
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from tests.factories import auth_header, make_user

type PeerClient = Callable[[str], httpx.AsyncClient]

HEADER = b"cf-connecting-ip"
REAL = "203.0.113.7"


def request_from(peer: str | None, *values: str) -> Request:
    scope: dict[str, object] = {
        "type": "http",
        "headers": [(HEADER, value.encode()) for value in values],
    }
    if peer is not None:
        scope["client"] = (peer, 50000)
    return Request(scope)


@pytest.fixture(autouse=True)
def no_allow_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test names its own FORWARDED_ALLOW_IPS; the shell's must not leak in."""
    monkeypatch.setattr(settings, "forwarded_allow_ips", "")


# ── the function ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize("peer", ["127.0.0.1", "127.0.0.5", "::1", "::ffff:127.0.0.1"])
def test_a_loopback_peer_is_believed(peer: str) -> None:
    assert client_ip(request_from(peer, REAL)) == REAL


def test_the_header_is_normalised() -> None:
    assert client_ip(request_from("127.0.0.1", "2001:DB8:0:0:0:0:0:1")) == "2001:db8::1"
    assert client_ip(request_from("127.0.0.1", " 203.0.113.7 ")) == REAL
    assert client_ip(request_from("127.0.0.1", "::ffff:203.0.113.7")) == REAL


@pytest.mark.parametrize(
    ("allow", "peer"),
    [
        ("10.1.0.2", "10.1.0.2"),
        ("10.1.0.0/24", "10.1.0.77"),
        ("192.0.2.1, 10.1.0.0/24 ,", "10.1.0.77"),
        ("fd00::/8", "fd00::5"),
        ("10.1.0.2", "::ffff:10.1.0.2"),
    ],
)
def test_a_peer_in_forwarded_allow_ips_is_believed(
    monkeypatch: pytest.MonkeyPatch, allow: str, peer: str
) -> None:
    monkeypatch.setattr(settings, "forwarded_allow_ips", allow)

    assert client_ip(request_from(peer, REAL)) == REAL


def test_a_peer_outside_the_allow_list_is_not(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "forwarded_allow_ips", "10.1.0.2,10.2.0.0/24")

    assert client_ip(request_from("10.1.0.3", REAL)) == "10.1.0.3"
    assert client_ip(request_from("10.2.1.1", REAL)) == "10.2.1.1"


def test_an_untrusted_peer_cannot_choose_its_address() -> None:
    assert client_ip(request_from("198.51.100.9", REAL)) == "198.51.100.9"


@pytest.mark.parametrize("allow", ["*", "*,127.0.0.1", "10.1.0.2/99", "not-an-ip", "10.1.0.2/24/1"])
def test_a_wildcard_or_junk_entry_trusts_nobody(
    monkeypatch: pytest.MonkeyPatch, allow: str
) -> None:
    """uvicorn reads `*` as "everyone"; here it fails safe."""
    monkeypatch.setattr(settings, "forwarded_allow_ips", allow)

    assert client_ip(request_from("198.51.100.9", REAL)) == "198.51.100.9"


def test_a_junk_entry_does_not_spoil_the_valid_ones(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "forwarded_allow_ips", "garbage,*,10.1.0.2")

    assert client_ip(request_from("10.1.0.2", REAL)) == REAL
    assert client_ip(request_from("198.51.100.9", REAL)) == "198.51.100.9"


@pytest.mark.parametrize(
    "value",
    [
        "garbage",
        "",
        "   ",
        "1.2.3.4, 5.6.7.8",
        "1.2.3.4,5.6.7.8",
        "1.2.3.4:80",
        "[::1]:80",
        "[2001:db8::1]",
        "fe80::1%eth0",
        "fe80::1%25eth0",
        "999.1.1.1",
        "1.2.3",
        "01.2.3.4",
        "1.2.3.4/32",
        "2001:db8::1 2001:db8::2",
        "1" * 400,
        "::ffff:" + "1" * 60,
    ],
)
def test_a_malformed_header_falls_back_to_the_peer(value: str) -> None:
    assert client_ip(request_from("127.0.0.1", value)) == "127.0.0.1"


def test_two_headers_fall_back_to_the_peer() -> None:
    assert client_ip(request_from("127.0.0.1", REAL, "198.51.100.1")) == "127.0.0.1"
    assert client_ip(request_from("127.0.0.1", REAL, REAL)) == "127.0.0.1"


def test_no_header_is_the_peer() -> None:
    assert client_ip(request_from("127.0.0.1")) == "127.0.0.1"
    assert client_ip(request_from("198.51.100.9")) == "198.51.100.9"


def test_no_client_is_none() -> None:
    assert client_ip(request_from(None, REAL)) is None
    assert client_ip(request_from(None)) is None


def test_a_peer_that_is_not_an_address_is_not_believed() -> None:
    """A unix socket or a hostname in `client` vouches for nothing."""
    assert client_ip(request_from("localhost", REAL)) == "localhost"
    assert client_ip(request_from("", REAL)) == ""


def test_the_limiter_key_for_no_client_is_the_log_marker() -> None:
    assert client_key(request_from(None)) == NO_CLIENT
    assert client_key(request_from("127.0.0.1", REAL)) == REAL


# ── the audit log ────────────────────────────────────────────────────────────


@pytest.fixture
async def peer_client(db: AsyncSession) -> AsyncGenerator[PeerClient]:
    """A client factory: `make(peer)` -> an httpx client whose connection is `peer`."""

    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    opened: list[httpx.AsyncClient] = []

    def make(peer: str) -> httpx.AsyncClient:
        http_client = httpx.AsyncClient(
            transport=ASGITransport(app=app, client=(peer, 50000)), base_url="http://test"
        )
        opened.append(http_client)
        return http_client

    try:
        yield make
    finally:
        for http_client in opened:
            await http_client.aclose()
        app.dependency_overrides.clear()


async def _audit_ip_after_creating_a_brand(
    db: AsyncSession, http_client: httpx.AsyncClient, extra: dict[str, str]
) -> str | None:
    admin = await make_user(db, email="ip-admin@voltbox.ge", role=ROLE_ADMIN)
    response = await http_client.post(
        "/api/v1/admin/brands",
        headers={**auth_header(admin), **extra},
        json={"name": "Ip Probe"},
    )
    assert response.status_code == 201, response.text
    entry = await db.scalar(
        select(AdminAuditLog).where(AdminAuditLog.entity_id == response.json()["id"])
    )
    assert entry is not None
    return entry.ip


async def test_the_audit_row_carries_the_real_client_not_loopback(
    db: AsyncSession, peer_client: PeerClient
) -> None:
    ip = await _audit_ip_after_creating_a_brand(
        db, peer_client("127.0.0.1"), {"CF-Connecting-IP": REAL}
    )

    assert ip == REAL


async def test_an_untrusted_peer_gets_its_own_address_in_the_audit_row(
    db: AsyncSession, peer_client: PeerClient
) -> None:
    ip = await _audit_ip_after_creating_a_brand(
        db, peer_client("198.51.100.9"), {"CF-Connecting-IP": REAL}
    )

    assert ip == "198.51.100.9"


async def test_without_the_header_the_audit_row_has_the_peer(
    db: AsyncSession, peer_client: PeerClient
) -> None:
    assert await _audit_ip_after_creating_a_brand(db, peer_client("127.0.0.1"), {}) == "127.0.0.1"


# ── the access line ──────────────────────────────────────────────────────────


@pytest.fixture
def access_lines() -> Generator[list[str]]:
    lines: list[str] = []

    class Collector(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            if record.name == "voltbox.access":
                lines.append(self.format(record))

    handler = Collector(level=logging.DEBUG)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    previous_level = root.level
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    try:
        yield lines
    finally:
        root.removeHandler(handler)
        root.setLevel(previous_level)


async def _logged_client(lines: list[str], peer: str, headers: dict[str, str]) -> str:
    transport = ASGITransport(app=create_app(), client=(peer, 5000))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
        assert (await http_client.get("/api/v1/health/live", headers=headers)).status_code == 200
    return str(json.loads(lines[-1])["client"])


async def test_the_access_line_pseudonymises_the_forwarded_address(
    access_lines: list[str],
) -> None:
    logged = await _logged_client(access_lines, "127.0.0.1", {"CF-Connecting-IP": REAL})

    assert logged == client_pseudonym(REAL)
    assert logged != client_pseudonym("127.0.0.1")
    assert all(REAL not in line for line in access_lines)


async def test_the_access_line_ignores_the_header_from_an_untrusted_peer(
    access_lines: list[str],
) -> None:
    logged = await _logged_client(access_lines, "198.51.100.9", {"CF-Connecting-IP": REAL})

    assert logged == client_pseudonym("198.51.100.9")
