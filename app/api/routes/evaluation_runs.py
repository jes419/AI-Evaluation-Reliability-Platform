
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas import EvaluationRunResponse
from app.services.evaluation_run_service import EvaluationRunService


router = APIRouter(
    prefix="/evaluation-runs",
    tags=["Evaluation Runs"],
)


class EvaluationResultRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: dict[str, Any] = Field(default_factory=dict)


class EvaluationFailureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_message: str = Field(min_length=1, max_length=2000)


def handle_service_error(exc: ValueError) -> HTTPException:
    error_status = (
        status.HTTP_404_NOT_FOUND
        if str(exc) == "Evaluation run not found"
        else status.HTTP_409_CONFLICT
    )

    return HTTPException(
        status_code=error_status,
        detail=str(exc),
    )


@router.post(
    "",
    response_model=EvaluationRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_evaluation_run(
    db: Session = Depends(get_db),
) -> EvaluationRunResponse:
    service = EvaluationRunService(db)
    return service.create_run()


@router.get(
    "",
    response_model=list[EvaluationRunResponse],
)
def list_evaluation_runs(
    db: Session = Depends(get_db),
) -> list[EvaluationRunResponse]:
    service = EvaluationRunService(db)
    return service.list_runs()


@router.get(
    "/{run_id}",
    response_model=EvaluationRunResponse,
)
def get_evaluation_run(
    run_id: str,
    db: Session = Depends(get_db),
) -> EvaluationRunResponse:
    service = EvaluationRunService(db)
    evaluation_run = service.get_run(run_id)

    if evaluation_run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation run not found",
        )

    return evaluation_run


@router.post(
    "/{run_id}/start",
    response_model=EvaluationRunResponse,
)
def start_evaluation_run(
    run_id: str,
    db: Session = Depends(get_db),
) -> EvaluationRunResponse:
    service = EvaluationRunService(db)

    try:
        return service.start_run(run_id)
    except ValueError as exc:
        raise handle_service_error(exc) from exc


@router.post(
    "/{run_id}/complete",
    response_model=EvaluationRunResponse,
)
def complete_evaluation_run(
    run_id: str,
    request: EvaluationResultRequest,
    db: Session = Depends(get_db),
) -> EvaluationRunResponse:
    service = EvaluationRunService(db)

    try:
        return service.complete_run(run_id, request.result)
    except ValueError as exc:
        raise handle_service_error(exc) from exc


@router.post(
    "/{run_id}/fail",
    response_model=EvaluationRunResponse,
)
def fail_evaluation_run(
    run_id: str,
    request: EvaluationFailureRequest,
    db: Session = Depends(get_db),
) -> EvaluationRunResponse:
    service = EvaluationRunService(db)

    try:
        return service.fail_run(run_id, request.error_message)
    except ValueError as exc:
        raise handle_service_error(exc) from exc
