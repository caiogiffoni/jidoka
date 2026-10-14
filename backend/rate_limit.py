"""Shared rate limiter instance and key functions.

All browser traffic reaches FastAPI through Next.js Server Actions / route
handlers, so the socket address is always the Next server's. Keying limits on
it would make every limit global: ten bad logins from anyone would lock login
for everyone. Instead:

- The Next server forwards the real client IP in ``CLIENT_IP_HEADER`` along
  with a shared secret in ``PROXY_SECRET_HEADER``. The forwarded IP is trusted
  **only** when that secret matches ``INTERNAL_PROXY_SECRET`` (constant-time
  compare); otherwise we fall back to the socket address, so a direct caller
  can't pick its own bucket by spoofing the header. With no secret configured
  (local dev) the header is never trusted and nothing crashes.
- Authenticated, user-scoped endpoints key on the user id from the bearer
  token (``user_or_ip_key``), falling back to the client IP.
- Login additionally keys failed attempts on the normalized email
  (``login_email_allowed`` / ``record_failed_login``), so one account can't be
  brute-forced from many IPs.
"""

import hmac
import ipaddress
import os

from limits import parse
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

CLIENT_IP_HEADER = "x-jidoka-client-ip"
PROXY_SECRET_HEADER = "x-internal-proxy-secret"

LOGIN_EMAIL_LIMIT = parse("10/minute")
_LOGIN_EMAIL_NAMESPACE = "login-email"


def _proxy_secret() -> str:
    return os.environ.get("INTERNAL_PROXY_SECRET", "")


def _trusted_proxy(request: Request) -> bool:
    expected = _proxy_secret()
    if not expected:
        return False
    provided = request.headers.get(PROXY_SECRET_HEADER, "")
    return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


def client_ip(request: Request) -> str:
    """The real client IP: forwarded by a trusted proxy, else the socket address."""
    if _trusted_proxy(request):
        forwarded = request.headers.get(CLIENT_IP_HEADER, "").split(",")[0].strip()
        try:
            return str(ipaddress.ip_address(forwarded))
        except ValueError:
            pass
    return get_remote_address(request)


def user_or_ip_key(request: Request) -> str:
    """Key on the authenticated user id when a valid bearer token is present."""
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and token:
        # Lazy import: auth imports this module for the limiter.
        import auth

        try:
            sub = auth._decode_token(token).get("sub")
        except Exception:
            sub = None
        if sub:
            return f"user:{sub}"
    return f"ip:{client_ip(request)}"


limiter = Limiter(key_func=client_ip)


def login_email_allowed(email: str) -> bool:
    """False once ``email`` has used up its failed-login budget."""
    if not limiter.enabled:
        return True
    return limiter.limiter.test(LOGIN_EMAIL_LIMIT, _LOGIN_EMAIL_NAMESPACE, email)


def record_failed_login(email: str) -> None:
    if limiter.enabled:
        limiter.limiter.hit(LOGIN_EMAIL_LIMIT, _LOGIN_EMAIL_NAMESPACE, email)
