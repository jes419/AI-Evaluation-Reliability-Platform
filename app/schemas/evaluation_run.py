
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvaluationRunResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
    )

    id: str
    status: str = Field(min_length=1, max_length=20)
    result: dict[str, Any] | None = None
    error_message: str | None = Field(
        default=None,
        max_length=2000,
    )
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
