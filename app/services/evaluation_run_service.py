
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models import EvaluationRun
from app.repositories.evaluation_run_repository import EvaluationRunRepository


class EvaluationRunService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = EvaluationRunRepository(db)

    def create_run(self) -> EvaluationRun:
        try:
            evaluation_run = EvaluationRun()
            created_run = self.repository.create(evaluation_run)
            self.db.commit()
            self.db.refresh(created_run)
            return created_run
        except Exception:
            self.db.rollback()
            raise

    def get_run(self, run_id: str) -> EvaluationRun | None:
        return self.repository.get_by_id(run_id)

    def list_runs(self) -> list[EvaluationRun]:
        return self.repository.list_all()

    def start_run(self, run_id: str) -> EvaluationRun:
        updated = self._transition_run(
            run_id=run_id,
            expected_status="pending",
            new_status="running",
        )

        if not updated:
            self._raise_transition_error(
                run_id,
                "Only pending runs can be started",
            )

        return self._get_updated_run(run_id)

    def complete_run(
        self,
        run_id: str,
        result: dict[str, Any],
    ) -> EvaluationRun:
        evaluation_run = self._get_existing_run(run_id)

        if evaluation_run.status == "completed":
            if evaluation_run.result == result:
                return evaluation_run

            raise ValueError(
                "Evaluation run is already completed with a different result"
            )

        completed_at = datetime.now(timezone.utc)

        try:
            updated = self.repository.finalize_if_running(
                run_id=run_id,
                result=result,
                completed_at=completed_at,
            )

            if not updated:
                self.db.rollback()
                evaluation_run = self._get_existing_run(run_id)

                if evaluation_run.status == "completed":
                    if evaluation_run.result == result:
                        return evaluation_run

                    raise ValueError(
                        "Evaluation run is already completed with a different result"
                    )

                raise ValueError("Only running runs can be completed")

            self.db.commit()
            return self._get_updated_run(run_id)
        except Exception:
            self.db.rollback()
            raise

    def fail_run(
        self,
        run_id: str,
        error_message: str,
    ) -> EvaluationRun:
        completed_at = datetime.now(timezone.utc)

        try:
            statement = (
                update(EvaluationRun)
                .where(
                    EvaluationRun.id == run_id,
                    EvaluationRun.status == "running",
                )
                .values(
                    status="failed",
                    error_message=error_message,
                    completed_at=completed_at,
                    updated_at=completed_at,
                )
                .execution_options(synchronize_session=False)
            )

            execution_result = self.db.execute(statement)

            if execution_result.rowcount != 1:
                self.db.rollback()
                self._raise_transition_error(
                    run_id,
                    "Only running runs can be failed",
                )

            self.db.commit()
            return self._get_updated_run(run_id)
        except Exception:
            self.db.rollback()
            raise

    def _transition_run(
        self,
        run_id: str,
        expected_status: str,
        new_status: str,
    ) -> bool:
        try:
            statement = (
                update(EvaluationRun)
                .where(
                    EvaluationRun.id == run_id,
                    EvaluationRun.status == expected_status,
                )
                .values(
                    status=new_status,
                    updated_at=datetime.now(timezone.utc),
                )
                .execution_options(synchronize_session=False)
            )

            execution_result = self.db.execute(statement)

            if execution_result.rowcount != 1:
                self.db.rollback()
                return False

            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            raise

    def _raise_transition_error(
        self,
        run_id: str,
        message: str,
    ) -> None:
        self._get_existing_run(run_id)
        raise ValueError(message)

    def _get_updated_run(self, run_id: str) -> EvaluationRun:
        self.db.expire_all()
        return self._get_existing_run(run_id)

    def _get_existing_run(self, run_id: str) -> EvaluationRun:
        evaluation_run = self.repository.get_by_id(run_id)

        if evaluation_run is None:
            raise ValueError("Evaluation run not found")

        return evaluation_run
