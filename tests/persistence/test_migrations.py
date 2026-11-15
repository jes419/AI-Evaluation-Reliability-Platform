from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import DateTime, String, create_engine, inspect, text
from sqlalchemy.engine import Connection

from app.init_database import main as initialize_database


BASELINE_REVISION = "a4c98d5f2e71"
CURRENT_REVISION = "be4c5f4e3330"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def migration_context():
    engine = create_engine("sqlite://")
    connection = engine.connect()
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", "invalid://must-not-be-used")
    config.attributes["connection"] = connection

    try:
        yield connection, config
    finally:
        connection.close()
        engine.dispose()


def assert_current_schema(connection: Connection) -> None:
    inspector = inspect(connection)
    columns = {
        column["name"]: column
        for column in inspector.get_columns("evaluation_runs")
    }

    assert set(columns) == {
        "id",
        "status",
        "created_at",
        "updated_at",
        "result",
        "error_message",
        "completed_at",
    }
    assert columns["id"]["type"].length == 36
    assert isinstance(columns["id"]["type"], String)
    assert columns["id"]["nullable"] is False
    assert columns["status"]["type"].length == 20
    assert isinstance(columns["status"]["type"], String)
    assert columns["status"]["nullable"] is False
    assert isinstance(columns["created_at"]["type"], DateTime)
    assert columns["created_at"]["nullable"] is False
    assert isinstance(columns["updated_at"]["type"], DateTime)
    assert columns["updated_at"]["nullable"] is False
    assert columns["result"]["nullable"] is True
    assert columns["error_message"]["nullable"] is True
    assert columns["completed_at"]["nullable"] is True
    assert inspector.get_pk_constraint("evaluation_runs")[
        "constrained_columns"
    ] == ["id"]
    assert "ix_evaluation_runs_status" in {
        index["name"] for index in inspector.get_indexes("evaluation_runs")
    }


def assert_revision(connection: Connection, revision: str) -> None:
    actual_revision = connection.scalar(
        text("SELECT version_num FROM alembic_version")
    )
    assert actual_revision == revision


def insert_original_row(connection: Connection, run_id: str) -> None:
    connection.execute(
        text(
            """
            INSERT INTO evaluation_runs (id, status, created_at, updated_at)
            VALUES (:id, :status, :created_at, :updated_at)
            """
        ),
        {
            "id": run_id,
            "status": "pending",
            "created_at": "2025-01-02 03:04:05",
            "updated_at": "2025-01-02 03:04:05",
        },
    )
    connection.commit()


def test_fresh_database_upgrades_to_head(migration_context):
    connection, config = migration_context

    command.upgrade(config, "head")

    assert_current_schema(connection)
    assert_revision(connection, CURRENT_REVISION)


def test_original_schema_upgrade_preserves_existing_row(migration_context):
    connection, config = migration_context
    command.upgrade(config, BASELINE_REVISION)
    insert_original_row(connection, "legacy-run")

    command.upgrade(config, "head")

    assert_current_schema(connection)
    assert_revision(connection, CURRENT_REVISION)
    row = connection.execute(
        text(
            """
            SELECT id, status, created_at, updated_at, result,
                   error_message, completed_at
            FROM evaluation_runs
            WHERE id = :id
            """
        ),
        {"id": "legacy-run"},
    ).mappings().one()
    assert row["id"] == "legacy-run"
    assert row["status"] == "pending"
    assert row["created_at"] == "2025-01-02 03:04:05"
    assert row["updated_at"] == "2025-01-02 03:04:05"
    assert row["result"] is None
    assert row["error_message"] is None
    assert row["completed_at"] is None


def test_unversioned_legacy_database_can_be_stamped_and_upgraded(
    migration_context,
):
    connection, config = migration_context
    connection.exec_driver_sql(
        """
        CREATE TABLE evaluation_runs (
            id VARCHAR(36) NOT NULL,
            status VARCHAR(20) NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            PRIMARY KEY (id)
        )
        """
    )
    connection.exec_driver_sql(
        "CREATE INDEX ix_evaluation_runs_status ON evaluation_runs (status)"
    )
    insert_original_row(connection, "unversioned-run")

    command.stamp(config, BASELINE_REVISION)
    command.upgrade(config, "head")

    assert_current_schema(connection)
    assert_revision(connection, CURRENT_REVISION)
    row = connection.execute(
        text("SELECT id, result FROM evaluation_runs WHERE id = :id"),
        {"id": "unversioned-run"},
    ).mappings().one()
    assert row["id"] == "unversioned-run"
    assert row["result"] is None


def test_database_at_existing_revision_upgrades_without_recreating_schema(
    migration_context,
):
    connection, config = migration_context
    command.upgrade(config, BASELINE_REVISION)
    insert_original_row(connection, "current-run")
    connection.exec_driver_sql(
        "ALTER TABLE evaluation_runs ADD COLUMN result JSON"
    )
    connection.exec_driver_sql(
        "ALTER TABLE evaluation_runs ADD COLUMN error_message VARCHAR(2000)"
    )
    connection.exec_driver_sql(
        "ALTER TABLE evaluation_runs ADD COLUMN completed_at DATETIME"
    )
    connection.execute(
        text("UPDATE alembic_version SET version_num = :revision"),
        {
            "revision": CURRENT_REVISION,
        },
    )
    connection.execute(
        text(
            """
            UPDATE evaluation_runs
            SET status = 'completed', result = :result,
                updated_at = :updated_at, completed_at = :completed_at
            WHERE id = :id
            """
        ),
        {
            "id": "current-run",
            "result": '{"score": 1}',
            "updated_at": "2025-01-02 03:04:06",
            "completed_at": "2025-01-02 03:04:06",
        },
    )
    connection.commit()
    assert_revision(connection, CURRENT_REVISION)

    command.upgrade(config, "head")

    assert_current_schema(connection)
    assert_revision(connection, CURRENT_REVISION)
    row = connection.execute(
        text(
            "SELECT id, status, result FROM evaluation_runs WHERE id = :id"
        ),
        {"id": "current-run"},
    ).mappings().one()
    assert row["id"] == "current-run"
    assert row["status"] == "completed"
    assert row["result"] == '{"score": 1}'


def test_initializer_can_run_repeatedly(migration_context):
    connection, config = migration_context

    initialize_database(config)
    assert_current_schema(connection)
    assert_revision(connection, CURRENT_REVISION)

    insert_original_row(connection, "initializer-run")
    initialize_database(config)

    assert_current_schema(connection)
    assert_revision(connection, CURRENT_REVISION)
    assert connection.scalar(
        text("SELECT id FROM evaluation_runs WHERE id = :id"),
        {"id": "initializer-run"},
    ) == "initializer-run"
