from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session


class Base(DeclarativeBase):
    pass


def build_engine(database_url: str) -> Engine:
    is_sqlite = make_url(database_url).get_backend_name() == "sqlite"
    kwargs = {}
    if is_sqlite:
        kwargs["connect_args"] = {
            "check_same_thread": False,
            "timeout": 30,
            "autocommit": False,
        }
    engine = create_engine(database_url, **kwargs)
    if is_sqlite:

        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, _record):
            previous = connection.autocommit
            connection.autocommit = True
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
            connection.autocommit = previous

    return engine


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session
