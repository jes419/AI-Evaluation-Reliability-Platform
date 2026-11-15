
from alembic import command
from alembic.config import Config

from app.core.database import PROJECT_ROOT


def main(config: Config | None = None) -> None:
    if config is None:
        config = Config(str(PROJECT_ROOT / "alembic.ini"))

    command.upgrade(config, "head")
    print("Database schema is up to date.")


if __name__ == "__main__":
    main()
