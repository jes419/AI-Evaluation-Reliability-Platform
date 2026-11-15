
from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import EvaluationRun


class EvaluationRunRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, evaluation_run: EvaluationRun) -> EvaluationRun:
        self.db.add(evaluation_run)
        self.db.flush()
        self.db.refresh(evaluation_run)
        return evaluation_run

    def get_by_id(self, run_id: str) -> EvaluationRun | None:
        statement = select(EvaluationRun).where(
            EvaluationRun.id == run_id
        )
        return self.db.scalar(statement)

    def list_all(self) -> list[EvaluationRun]:
        statement = select(EvaluationRun).order_by(
            EvaluationRun.created_at.desc(),
            EvaluationRun.id.asc(),
        )
        return list(self.db.scalars(statement).all())

    def finalize_if_running(
        self,
        run_id: str,
        result: dict[str, Any],
        completed_at: datetime,
    ) -> bool:
        statement = (
            update(EvaluationRun)
            .where(
                EvaluationRun.id == run_id,
                EvaluationRun.status == "running",
            )
            .values(
                status="completed",
                result=result,
                error_message=None,
                completed_at=completed_at,
                updated_at=completed_at,
            )
            .execution_options(synchronize_session=False)
        )

        execution_result = self.db.execute(statement)
        return execution_result.rowcount == 1
