"""The client's IP address - one definition for everything that needs it.

What it does: `client_ip(request)` answers "which address did this request come
from?" for the rate limiter's key, the access line's `client` pseudonym and the
`ip` of every admin audit row. Three readers, one function, so the log shows
what the limiter counts and the audit log says what the log says.

Why it is not just `request.client.host`: on Render the app sits behind Render's
proxy, which sits behind Cloudflare. What the app sees as the peer is the
loopback address (measured: `admin_audit_log.ip = 127.0.0.1`, and a browser and
Render's own health check had the same access-log `client`), so every shopper
shared one rate-limit bucket - the login limit and the 30 orders a day were for
the whole shop - and the audit log held no real address. Cloudflare puts the
address it saw into `CF-Connecting-IP`.

The rule:

  - Peer = `request.client.host`. No peer, no answer (None).
  - If the peer is TRUSTED and the request carries exactly one `CF-Connecting-IP`
    whose value is a bare IPv4 or IPv6 address, that address (normalised).
  - Anything else is the peer, as before. A `CF-Connecting-IP` from a peer that is
    not trusted is ignored, so the header cannot be used to pick one's own
    bucket. A header that is empty, a list, has a port, has a scope id (`%`), is
    absurdly long, is repeated, or that `ipaddress` refuses falls back to the
    peer too: a malformed value is never half-believed.

TRUSTED means a loopback address (127.0.0.0/8, ::1: the proxy on the same
machine) or an address matched by `FORWARDED_ALLOW_IPS`, the variable gunicorn
and uvicorn already read for `X-Forwarded-For`: comma-separated IPs and CIDR
networks, parsed the way uvicorn's `_TrustedHosts` does (a bare address is a
single-host network; an entry that is neither is ignored). `*` does NOT mean
"everyone" here, although it does to uvicorn: gunicorn.conf.py already refuses
it in a deployment, and where nothing refuses it (a local run) trusting every
peer would let any caller choose its address, so it is ignored and fails safe.

Why `request.client.host` is a sound "direct peer" test even though uvicorn's
ProxyHeadersMiddleware may already have rewritten it from `X-Forwarded-For`:
uvicorn replaces `scope["client"]` only when the real peer is in
FORWARDED_ALLOW_IPS, so an untrusted peer is never rewritten - a value that is
in FORWARDED_ALLOW_IPS can only be the real, trusted peer. What still holds: when
a trusted proxy's `X-Forwarded-For` has already rewritten the client to an
untrusted (public) address, that address is used as it always was and
`CF-Connecting-IP` is not consulted. And a loopback value is trusted on its own
account, which includes a loopback written into `X-Forwarded-For`; that costs
nothing as long as the header it unlocks cannot be chosen by the client, which
is the deployment assumption below.

Deployment assumption: `CF-Connecting-IP` is believable only because all public
traffic to the Render service passes through Cloudflare, which overwrites any
value the client sent, and because only a trusted peer's header is read. A
service reachable some other way (a second front door that does not set the
header) would let a caller choose its address from a trusted hop.
"""

import ipaddress
import logging
from functools import lru_cache

from starlette.requests import Request

from app.core.config import settings

logger = logging.getLogger(__name__)

CLIENT_IP_HEADER = "cf-connecting-ip"

#: An IPv6 address with an embedded IPv4 tail is at most 45 characters. Anything
#: longer is not an address, and is rejected before it reaches the parser.
_MAX_ADDRESS_LENGTH = 45

type _Address = ipaddress.IPv4Address | ipaddress.IPv6Address
type _Network = ipaddress.IPv4Network | ipaddress.IPv6Network


def _parse(text: str) -> _Address | None:
    """A bare address as `ipaddress` reads it, or None. IPv4-mapped IPv6
    (`::ffff:1.2.3.4`) is the IPv4 address it stands for, so the two spellings of
    one client are one client."""
    try:
        address = ipaddress.ip_address(text)
    except ValueError:
        return None
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        return address.ipv4_mapped
    return address


@lru_cache(maxsize=8)
def _trusted_networks(allow_ips: str) -> tuple[_Network, ...]:
    """FORWARDED_ALLOW_IPS as networks, parsed once per distinct value.

    Invalid entries (and `*`, see the module docstring) are skipped, not
    errors: gunicorn.conf.py is where a deployment's value is judged, and a
    typo here must not turn into a 500 on every request.
    """
    networks: list[_Network] = []
    for entry in allow_ips.split(","):
        entry = entry.strip()
        if not entry:
            continue
        try:
            networks.append(ipaddress.ip_network(entry))
        except ValueError:
            logger.warning(
                "FORWARDED_ALLOW_IPS entry ignored for client IP trust: not an IP or CIDR"
            )
    return tuple(networks)


def _is_trusted(peer: str) -> bool:
    address = _parse(peer)
    if address is None:
        return False  # a unix socket, a hostname: not an address we can vouch for
    if address.is_loopback:
        return True
    return any(address in network for network in _trusted_networks(settings.forwarded_allow_ips))


def _header_address(request: Request) -> str | None:
    values = request.headers.getlist(CLIENT_IP_HEADER)
    if len(values) != 1:
        return None
    value = values[0].strip()
    if not value or len(value) > _MAX_ADDRESS_LENGTH or "%" in value:
        return None
    address = _parse(value)
    return None if address is None else str(address)


def client_ip(request: Request) -> str | None:
    """The address this request came from, or None when the server reported none."""
    if request.client is None:
        return None
    peer = request.client.host
    if _is_trusted(peer):
        forwarded = _header_address(request)
        if forwarded is not None:
            return forwarded
    return peer
