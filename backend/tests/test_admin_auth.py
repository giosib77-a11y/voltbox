"""Admin authorization.

What it covers: that every route under the admin prefix is protected, that a
customer cannot reach it, that a deactivated admin loses access immediately,
and that nobody can register themselves as an admin.

The protection test walks the live OpenAPI schema rather than a hand-written
list, so an endpoint added later is covered automatically. That is the point:
a forgotten dependency on one new route is exactly the mistake this catches.
"""

import re
from uuid import uuid4

import httpx
import pytest
from app.db.models import ROLE_ADMIN, ROLE_CUSTOMER
from app.main import app
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import auth_header, make_user

ADMIN_PREFIX = "/api/v1/admin"

# Any well-formed value works: authorization runs before the path is resolved,
# so the request never reaches the handler that would care about the id.
DUMMY = str(uuid4())


def admin_operations() -> list[tuple[str, str]]:
    """Every (method, concrete path) pair currently mounted under /admin."""
    paths = app.openapi()["paths"]
    operations = []
    for template, methods in paths.items():
        if not template.startswith(ADMIN_PREFIX):
            continue
        concrete = re.sub(r"\{[^}]+\}", DUMMY, template)
        for method in methods:
            operations.append((method.upper(), concrete))
    return sorted(operations)


def test_the_admin_router_actually_has_routes() -> None:
    """Guards the guard: an empty list would make every test below vacuous."""
    assert admin_operations(), "no admin routes found - the protection tests prove nothing"


@pytest.mark.parametrize(("method", "path"), admin_operations())
async def test_admin_routes_reject_anonymous(
    client: httpx.AsyncClient, method: str, path: str
) -> None:
    response = await client.request(method, path)

    # HTTPBearer runs with auto_error=False and the project raises its own
    # UnauthorizedError, so a missing token is 401 rather than FastAPI's 403.
    assert response.status_code == 401, f"{method} {path} answered {response.status_code}"
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


@pytest.mark.parametrize(("method", "path"), admin_operations())
async def test_admin_routes_reject_customers(
    client: httpx.AsyncClient, db: AsyncSession, method: str, path: str
) -> None:
    customer = await make_user(db, email=f"customer-{uuid4().hex[:8]}@example.ge")

    response = await client.request(method, path, headers=auth_header(customer))

    assert response.status_code == 403, f"{method} {path} answered {response.status_code}"
    assert response.json()["error"]["code"] == "ADMIN_REQUIRED"


@pytest.mark.parametrize(("method", "path"), admin_operations())
async def test_admin_routes_reject_a_deactivated_admin(
    client: httpx.AsyncClient, db: AsyncSession, method: str, path: str
) -> None:
    blocked = await make_user(
        db, email=f"blocked-{uuid4().hex[:8]}@example.ge", role=ROLE_ADMIN, is_active=False
    )

    response = await client.request(method, path, headers=auth_header(blocked))

    # get_current_user re-reads the row, so deactivation takes effect at once
    # instead of when the 30-minute access token expires.
    assert response.status_code == 401, f"{method} {path} answered {response.status_code}"


async def test_admin_me_returns_the_signed_in_admin(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    admin = await make_user(db, email="boss@voltbox.ge", role=ROLE_ADMIN)

    response = await client.get(f"{ADMIN_PREFIX}/me", headers=auth_header(admin))

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "boss@voltbox.ge"
    assert body["role"] == ROLE_ADMIN
    assert body["isActive"] is True


async def test_admin_me_never_leaks_credentials(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    admin = await make_user(db, email="leak@voltbox.ge", role=ROLE_ADMIN)

    body = (await client.get(f"{ADMIN_PREFIX}/me", headers=auth_header(admin))).json()

    for forbidden in ("passwordHash", "password_hash", "tokenHash", "password"):
        assert forbidden not in body


async def test_registration_cannot_grant_the_admin_role(client: httpx.AsyncClient) -> None:
    """`role` is not a field on RegisterRequest and ApiRequest forbids extras."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "firstName": "მალხაზი",
            "lastName": "ცხადაძე",
            "email": "sneaky@example.ge",
            "password": "supersecret1",
            "role": ROLE_ADMIN,
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_a_normal_registration_creates_a_customer(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "firstName": "ნინო",
            "lastName": "კაპანაძე",
            "email": "plain@example.ge",
            "password": "supersecret1",
        },
    )
    assert response.status_code == 201

    admin = response.json()
    # The storefront session never exposes the role at all.
    assert "role" not in admin["user"]

    login = await client.post(
        "/api/v1/auth/login", json={"email": "plain@example.ge", "password": "supersecret1"}
    )
    token = login.json()["token"]
    denied = await client.get(f"{ADMIN_PREFIX}/me", headers={"Authorization": f"Bearer {token}"})

    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "ADMIN_REQUIRED"


async def test_the_role_column_defaults_to_customer(db: AsyncSession) -> None:
    user = await make_user(db, email="default-role@example.ge")
    assert user.role == ROLE_CUSTOMER


async def test_the_session_tells_an_admin_that_they_are_one(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    """The storefront needs this to draw a link to the panel.

    Without it an administrator who signs in through the shop has no way to
    discover /admin at all - the address is only known to whoever memorised it.
    """
    admin = await make_user(db, email="flagged@voltbox.ge", role=ROLE_ADMIN)

    response = await client.get("/api/v1/auth/me", headers=auth_header(admin))

    assert response.status_code == 200
    body = response.json()
    assert body["isAdmin"] is True
    # A capability flag, not the taxonomy: the role string stays server-side.
    assert "role" not in body


async def test_a_customer_session_is_not_flagged_as_admin(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    customer = await make_user(db, email="unflagged@example.ge")

    body = (await client.get("/api/v1/auth/me", headers=auth_header(customer))).json()

    assert body["isAdmin"] is False


async def test_the_flag_follows_a_promotion(client: httpx.AsyncClient, db: AsyncSession) -> None:
    user = await make_user(db, email="promoted@example.ge")
    assert (await client.get("/api/v1/auth/me", headers=auth_header(user))).json()[
        "isAdmin"
    ] is False

    user.role = ROLE_ADMIN
    await db.flush()

    # Read from the row on every request, so it cannot go stale in a token.
    body = (await client.get("/api/v1/auth/me", headers=auth_header(user))).json()
    assert body["isAdmin"] is True
