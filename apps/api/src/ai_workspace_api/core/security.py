import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from jose import JWTError, jwt

from ai_workspace_api.core.config import Settings

ALGORITHM = "HS256"
PASSWORD_HASH_PREFIX = "bcrypt-sha256$"  # noqa: S105


class InvalidTokenError(ValueError):
    pass


def hash_password(password: str) -> str:
    hashed_password = bcrypt.hashpw(_password_digest(password), bcrypt.gensalt()).decode("utf-8")
    return f"{PASSWORD_HASH_PREFIX}{hashed_password}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        if password_hash.startswith(PASSWORD_HASH_PREFIX):
            encoded_hash = password_hash.removeprefix(PASSWORD_HASH_PREFIX).encode("utf-8")
            return bcrypt.checkpw(_password_digest(password), encoded_hash)
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def _password_digest(password: str) -> bytes:
    return hashlib.sha256(password.encode("utf-8")).digest()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_opaque_token() -> str:
    return secrets.token_urlsafe(48)


def create_access_token(
    *,
    subject: str,
    settings: Settings,
    organization_id: str | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_ttl_minutes)).timestamp()),
        "typ": "access",
    }
    if organization_id:
        payload["org"] = organization_id
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm=ALGORITHM)


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[ALGORITHM],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
        )
    except JWTError as exc:
        raise InvalidTokenError("Invalid access token") from exc
    if payload.get("typ") != "access":
        raise InvalidTokenError("Unexpected token type")
    return payload
