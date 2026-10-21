from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.schemas.auth import Credentials, Token, UserRead
from app.services import auth

router = APIRouter(tags=["Autenticación"])
DB = Annotated[Session, Depends(get_session)]


@router.post("/register", response_model=UserRead, status_code=201)
def register(credentials: Credentials, session: DB):
    return auth.register(session, credentials)


@router.post("/login", response_model=Token)
def login(credentials: Credentials, session: DB, request: Request):
    return auth.login(session, credentials, request.app.state.settings)
