from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import create_token, hash_password, unauthorized, verify_password
from app.repositories import users
from app.schemas.auth import Credentials, Token, UserRead


def register(session: Session, credentials: Credentials) -> UserRead:
    password_hash = hash_password(credentials.password.get_secret_value())
    try:
        with session.begin():
            user = users.add(session, credentials.username, password_hash)
            response = UserRead.model_validate(user)
    except IntegrityError:
        raise HTTPException(409, "El usuario ya existe") from None
    return response


def login(session: Session, credentials: Credentials, settings: Settings) -> Token:
    user = users.by_username(session, credentials.username)
    if not verify_password(
        credentials.password.get_secret_value(), user.password_hash if user else None
    ):
        raise unauthorized()
    return Token(access_token=create_token(user.id, settings))
