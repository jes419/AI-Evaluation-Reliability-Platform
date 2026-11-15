
import pytest

from datetime import datetime, timezone

from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import EvaluationRun
from app.services.evaluation_run_service import EvaluationRunService


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine)

    testing_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

    db = testing_session_local()

    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def arrange_competing_completion(
    service,
    db_session,
    monkeypatch,
    winning_result,
    winning_completed_at,
):
    finalize_if_running = service.repository.finalize_if_running

    def finalize_after_competing_update(run_id, result, completed_at):
        statement = (
            update(EvaluationRun)
            .where(
                EvaluationRun.id == run_id,
                EvaluationRun.status == "running",
            )
            .values(
                status="completed",
                result=winning_result,
                error_message=None,
                completed_at=winning_completed_at,
                updated_at=winning_completed_at,
            )
            .execution_options(synchronize_session=False)
        )
        execution_result = db_session.execute(statement)
        assert execution_result.rowcount == 1
        db_session.commit()

        return finalize_if_running(
            run_id=run_id,
            result=result,
            completed_at=completed_at,
        )

    monkeypatch.setattr(
        service.repository,
        "finalize_if_running",
        finalize_after_competing_update,
    )


def test_create_evaluation_run(db_session):
    service = EvaluationRunService(db_session)

    run = service.create_run()

    assert run.id is not None
    assert run.status == "pending"
    assert run.result is None
    assert run.error_message is None
    assert run.completed_at is None
    assert run.created_at is not None
    assert run.updated_at is not None


def test_start_evaluation_run(db_session):
    service = EvaluationRunService(db_session)

    run = service.create_run()
    original_updated_at = run.updated_at

    started_run = service.start_run(run.id)

    assert started_run.status == "running"
    assert started_run.updated_at is not None
    assert started_run.updated_at >= original_updated_at


def test_complete_evaluation_run(db_session):
    service = EvaluationRunService(db_session)

    run = service.create_run()
    service.start_run(run.id)

    result = {"score": 0.95, "passed": True}
    completed_run = service.complete_run(run.id, result)

    assert completed_run.status == "completed"
    assert completed_run.result == result
    assert completed_run.error_message is None
    assert completed_run.completed_at is not None
    assert completed_run.updated_at == completed_run.completed_at


def test_fail_evaluation_run(db_session):
    service = EvaluationRunService(db_session)

    run = service.create_run()
    service.start_run(run.id)

    failed_run = service.fail_run(
        run.id,
        "Evaluation failed",
    )

    assert failed_run.status == "failed"
    assert failed_run.error_message == "Evaluation failed"
    assert failed_run.completed_at is not None
    assert failed_run.updated_at == failed_run.completed_at


def test_cannot_start_non_pending_run(db_session):
    service = EvaluationRunService(db_session)

    run = service.create_run()
    service.start_run(run.id)

    with pytest.raises(
        ValueError,
        match="Only pending runs can be started",
    ):
        service.start_run(run.id)


def test_cannot_complete_pending_run(db_session):
    service = EvaluationRunService(db_session)

    run = service.create_run()

    with pytest.raises(
        ValueError,
        match="Only running runs can be completed",
    ):
        service.complete_run(run.id, {"score": 0.95})


def test_cannot_fail_pending_run(db_session):
    service = EvaluationRunService(db_session)

    run = service.create_run()

    with pytest.raises(
        ValueError,
        match="Only running runs can be failed",
    ):
        service.fail_run(run.id, "Evaluation failed")


def test_repeated_completion_with_same_result_is_idempotent(db_session):
    service = EvaluationRunService(db_session)

    run = service.create_run()
    service.start_run(run.id)

    result = {"score": 0.95, "passed": True}

    first_completion = service.complete_run(run.id, result)
    original_completed_at = first_completion.completed_at
    original_updated_at = first_completion.updated_at

    second_completion = service.complete_run(run.id, result)

    assert second_completion.id == first_completion.id
    assert second_completion.status == "completed"
    assert second_completion.result == result
    assert second_completion.completed_at == original_completed_at
    assert second_completion.updated_at == original_updated_at


def test_repeated_completion_with_different_result_is_rejected(db_session):
    service = EvaluationRunService(db_session)

    run = service.create_run()
    service.start_run(run.id)

    service.complete_run(run.id, {"score": 0.95})

    with pytest.raises(
        ValueError,
        match="already completed with a different result",
    ):
        service.complete_run(run.id, {"score": 0.98})


def test_completion_accepts_equivalent_competing_result(
    db_session,
    monkeypatch,
):
    service = EvaluationRunService(db_session)
    run = service.create_run()
    service.start_run(run.id)

    winning_result = {
        "metrics": {"accuracy": 1, "consistency": 0.93},
        "passed": True,
    }
    requested_result = {
        "passed": True,
        "metrics": {"consistency": 0.93, "accuracy": 1.0},
    }
    winning_completed_at = datetime(2025, 1, 2, 3, 4, 5)
    arrange_competing_completion(
        service,
        db_session,
        monkeypatch,
        winning_result,
        winning_completed_at,
    )

    completed_run = service.complete_run(run.id, requested_result)

    assert completed_run.status == "completed"
    assert completed_run.result == winning_result
    assert type(completed_run.result["metrics"]["accuracy"]) is int
    assert completed_run.completed_at == winning_completed_at
    assert completed_run.updated_at == winning_completed_at

    db_session.expire_all()
    persisted_run = service.get_run(run.id)
    assert persisted_run is not None
    assert persisted_run.result == winning_result
    assert type(persisted_run.result["metrics"]["accuracy"]) is int
    assert persisted_run.completed_at == winning_completed_at
    assert persisted_run.updated_at == winning_completed_at


def test_completion_rejects_conflicting_competing_result(
    db_session,
    monkeypatch,
):
    service = EvaluationRunService(db_session)
    run = service.create_run()
    service.start_run(run.id)

    winning_result = {"score": 0.95, "passed": True}
    requested_result = {"score": 0.98, "passed": True}
    winning_completed_at = datetime(2025, 1, 2, 3, 4, 5)
    arrange_competing_completion(
        service,
        db_session,
        monkeypatch,
        winning_result,
        winning_completed_at,
    )

    with pytest.raises(
        ValueError,
        match="already completed with a different result",
    ):
        service.complete_run(run.id, requested_result)

    db_session.expire_all()
    persisted_run = service.get_run(run.id)
    assert persisted_run is not None
    assert persisted_run.status == "completed"
    assert persisted_run.result == winning_result
    assert persisted_run.completed_at == winning_completed_at
    assert persisted_run.updated_at == winning_completed_at


def test_cannot_fail_completed_run(db_session):
    service = EvaluationRunService(db_session)

    run = service.create_run()
    service.start_run(run.id)
    service.complete_run(run.id, {"score": 0.95})

    with pytest.raises(
        ValueError,
        match="Only running runs can be failed",
    ):
        service.fail_run(run.id, "Late failure")


def test_cannot_complete_failed_run(db_session):
    service = EvaluationRunService(db_session)

    run = service.create_run()
    service.start_run(run.id)
    service.fail_run(run.id, "Evaluation failed")

    with pytest.raises(
        ValueError,
        match="Only running runs can be completed",
    ):
        service.complete_run(run.id, {"score": 0.95})


def test_cannot_start_completed_run(db_session):
    service = EvaluationRunService(db_session)

    run = service.create_run()
    service.start_run(run.id)
    service.complete_run(run.id, {"score": 0.95})

    with pytest.raises(
        ValueError,
        match="Only pending runs can be started",
    ):
        service.start_run(run.id)


def test_cannot_start_failed_run(db_session):
    service = EvaluationRunService(db_session)

    run = service.create_run()
    service.start_run(run.id)
    service.fail_run(run.id, "Evaluation failed")

    with pytest.raises(
        ValueError,
        match="Only pending runs can be started",
    ):
        service.start_run(run.id)


def test_run_not_found(db_session):
    service = EvaluationRunService(db_session)

    with pytest.raises(
        ValueError,
        match="Evaluation run not found",
    ):
        service.start_run("00000000-0000-0000-0000-000000000000")


def test_completion_preserves_result_after_session_refresh(db_session):
    service = EvaluationRunService(db_session)

    run = service.create_run()
    service.start_run(run.id)

    result = {
        "score": 0.95,
        "passed": True,
        "metrics": {
            "accuracy": 0.97,
            "consistency": 0.93,
        },
    }

    service.complete_run(run.id, result)
    db_session.expire_all()

    retrieved_run = service.get_run(run.id)

    assert retrieved_run is not None
    assert retrieved_run.status == "completed"
    assert retrieved_run.result == result


def test_failure_preserves_error_after_session_refresh(db_session):
    service = EvaluationRunService(db_session)

    run = service.create_run()
    service.start_run(run.id)

    error_message = "Evaluation failed during processing"

    service.fail_run(run.id, error_message)
    db_session.expire_all()

    retrieved_run = service.get_run(run.id)

    assert retrieved_run is not None
    assert retrieved_run.status == "failed"
    assert retrieved_run.error_message == error_message
