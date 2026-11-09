"""Password hashing with Argon2id (via pwdlib), plus the light CSRF guard.

Passwords are never stored or logged in plain text. Argon2id is deliberately slow
and salted, so a leaked hash is expensive to crack.
"""

from pwdlib import PasswordHash
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

_password_hash = PasswordHash.recommended()

# Verifying against this when the email is unknown keeps the response time similar
# to a wrong password, so attackers cannot discover which emails exist.
_DUMMY_HASH = _password_hash.hash("dummy-password-for-timing")


def hash_password(plain: str) -> str:
    return _password_hash.hash(plain)


def verify_password(plain: str, hashed: str | None) -> bool:
    if hashed is None:
        _password_hash.verify(plain, _DUMMY_HASH)
        return False
    return _password_hash.verify(plain, hashed)


# --- CSRF -----------------------------------------------------------------
CSRF_HEADER = "X-Requested-With"
CSRF_HEADER_VALUE = "fetch"
_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class CsrfHeaderMiddleware(BaseHTTPMiddleware):
    """State-changing API calls must send ``X-Requested-With: fetch``.

    Another website cannot add a custom header to a cross-site request without a
    CORS pre-flight, which this app never allows. Combined with SameSite=Lax session
    cookies, this blocks cross-site request forgery.
    """

    async def dispatch(self, request: Request, call_next):
        if (
            request.method in _UNSAFE_METHODS
            and request.url.path.startswith("/api/")
            and request.headers.get(CSRF_HEADER) != CSRF_HEADER_VALUE
        ):
            return JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "code": "csrf_check_failed",
                        "message": f"Missing '{CSRF_HEADER}: {CSRF_HEADER_VALUE}' header.",
                        "details": None,
                    }
                },
            )
        return await call_next(request)
