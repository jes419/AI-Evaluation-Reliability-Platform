
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import EvaluationRun
from app.repositories.evaluation_run_repository import EvaluationRunRepository


def test_create_and_retrieve_evaluation_run():
    engine = create_engine("sqlite://")
    testing_session_local = sessionmaker(bind=engine)

    Base.metadata.create_all(bind=engine)

    db = testing_session_local()

    try:
        repository = EvaluationRunRepository(db)

        evaluation_run = EvaluationRun()
        created_run = repository.create(evaluation_run)

        assert created_run.id is not None
        assert created_run.status == "pending"

        retrieved_run = repository.get_by_id(created_run.id)

        assert retrieved_run is not None
        assert retrieved_run.id == created_run.id
        assert retrieved_run.status == "pending"

        db.rollback()
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_finalize_if_running_updates_evaluation_run():
    engine = create_engine("sqlite://")
    testing_session_local = sessionmaker(bind=engine)

    Base.metadata.create_all(bind=engine)

    db = testing_session_local()

    try:
        evaluation_run = EvaluationRun(status="running")
        db.add(evaluation_run)
        db.commit()

        repository = EvaluationRunRepository(db)
        result = {"score": 0.95, "passed": True}
        completed_at = datetime.now(timezone.utc)

        updated = repository.finalize_if_running(
            run_id=evaluation_run.id,
            result=result,
            completed_at=completed_at,
        )

        assert updated is True

        db.commit()
        db.expire_all()

        finalized_run = repository.get_by_id(evaluation_run.id)

        assert finalized_run is not None
        assert finalized_run.status == "completed"
        assert finalized_run.result == result
        assert finalized_run.error_message is None
        assert finalized_run.completed_at is not None
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_finalize_if_running_rejects_already_completed_run():
    engine = create_engine("sqlite://")
    testing_session_local = sessionmaker(bind=engine)

    Base.metadata.create_all(bind=engine)

    db = testing_session_local()

    try:
        evaluation_run = EvaluationRun(status="running")
        db.add(evaluation_run)
        db.commit()

        repository = EvaluationRunRepository(db)

        first_result = {"score": 0.95}
        completed_at = datetime.now(timezone.utc)

        first_update = repository.finalize_if_running(
            run_id=evaluation_run.id,
            result=first_result,
            completed_at=completed_at,
        )

        assert first_update is True

        db.commit()

        second_update = repository.finalize_if_running(
            run_id=evaluation_run.id,
            result={"score": 0.98},
            completed_at=datetime.now(timezone.utc),
        )

        assert second_update is False

        db.rollback()
        db.expire_all()

        finalized_run = repository.get_by_id(evaluation_run.id)

        assert finalized_run is not None
        assert finalized_run.status == "completed"
        assert finalized_run.result == first_result
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_two_sessions_competing_to_finalize_same_run():
    engine = create_engine("sqlite://")
    testing_session_local = sessionmaker(bind=engine)

    Base.metadata.create_all(bind=engine)

    setup_db = testing_session_local()
    first_db = testing_session_local()
    second_db = testing_session_local()

    try:
        evaluation_run = EvaluationRun(status="running")
        setup_db.add(evaluation_run)
        setup_db.commit()

        run_id = evaluation_run.id

        first_repository = EvaluationRunRepository(first_db)
        second_repository = EvaluationRunRepository(second_db)

        first_result = {"score": 0.95, "passed": True}
        second_result = {"score": 0.98, "passed": True}

        first_update = first_repository.finalize_if_running(
            run_id=run_id,
            result=first_result,
            completed_at=datetime.now(timezone.utc),
        )

        assert first_update is True

        first_db.commit()

        second_update = second_repository.finalize_if_running(
            run_id=run_id,
            result=second_result,
            completed_at=datetime.now(timezone.utc),
        )

        assert second_update is False

        second_db.rollback()

        verification_db = testing_session_local()

        try:
            finalized_run = EvaluationRunRepository(
                verification_db
            ).get_by_id(run_id)

            assert finalized_run is not None
            assert finalized_run.status == "completed"
            assert finalized_run.result == first_result
            assert finalized_run.error_message is None
            assert finalized_run.completed_at is not None
        finally:
            verification_db.close()
    finally:
        setup_db.close()
        first_db.close()
        second_db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
