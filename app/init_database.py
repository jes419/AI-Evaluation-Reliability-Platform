
from app.core.database import init_db
from app.models import EvaluationRun


def main() -> None:
    init_db()
    print("Database tables initialized successfully.")


if __name__ == "__main__":
    main()
