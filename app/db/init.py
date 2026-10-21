from sqlalchemy import Engine

from app.core.config import Settings
from app.db.session import Base, build_engine


def initialize_database(engine: Engine) -> None:
    # Import mapped models before collecting their metadata.
    import app.models  # noqa: F401

    Base.metadata.create_all(engine)


def main() -> None:
    engine = build_engine(Settings().database_url)
    try:
        initialize_database(engine)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
