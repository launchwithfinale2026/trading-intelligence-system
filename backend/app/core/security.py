"""Password hashing and JWT issuance/verification.

Password hashing uses bcrypt directly (not passlib — passlib's bcrypt
backend has had compatibility breaks with recent bcrypt releases, and we
only need two functions here, not a multi-algorithm abstraction).
"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import get_settings

JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(*, subject: str, expires_minutes: int | None = None) -> str:
    settings = get_settings()
    expire_minutes = expires_minutes if expires_minutes is not None else settings.access_token_expire_minutes
    expire_at = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    payload = {"sub": subject, "exp": expire_at}
    return jwt.encode(payload, settings.secret_key, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> str:
    """Returns the token's subject (the user id, as a string).

    Raises jwt.PyJWTError (or a subclass) if the token is invalid, expired,
    or malformed — callers translate that into an UnauthorizedError.
    """
    settings = get_settings()
    payload = jwt.decode(token, settings.secret_key, algorithms=[JWT_ALGORITHM])
    return payload["sub"]
