from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from argon2 import PasswordHasher, Type
from argon2.exceptions import VerificationError
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings
from app.models.user import User
from app.repositories import users

password_hasher = PasswordHasher(type=Type.ID)
bearer = HTTPBearer(auto_error=False)
# Verify even when a username is unknown, to avoid an obvious fast-failure path.
_dummy_hash = password_hasher.hash("unused-dummy-password")


def unauthorized() -> HTTPException:
    return HTTPException(
        401, "Credenciales inválidas o token vencido", headers={"WWW-Authenticate": "Bearer"}
    )


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, stored_hash: str | None) -> bool:
    try:
        valid = password_hasher.verify(stored_hash or _dummy_hash, password)
        return valid and stored_hash is not None
    except VerificationError:
        return False


def create_token(user_id: int, settings: Settings) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(user_id),
            "iat": now,
            "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        },
        settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )


def current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if credentials is None:
        raise unauthorized()
    try:
        claims = jwt.decode(
            credentials.credentials,
            request.app.state.settings.jwt_secret.get_secret_value(),
            algorithms=["HS256"],
            options={"require": ["sub", "exp", "iat"]},
        )
        user_id = int(claims["sub"])
        if not 0 < user_id <= 2**63 - 1:
            raise ValueError("Invalid user id")
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise unauthorized() from None
    # Authentication does not open the business session's transaction.
    with request.app.state.session_factory() as session:
        user = users.by_id(session, user_id)
        if user is None:
            raise unauthorized()
        return user
