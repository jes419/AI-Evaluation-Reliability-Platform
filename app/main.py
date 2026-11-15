
from fastapi import FastAPI

from app.api.routes.evaluation_runs import router as evaluation_runs_router


app = FastAPI(
    title="AI Evaluation Reliability Platform",
    description=(
        "A platform for managing evaluation runs with "
        "reliable state transitions, persistent results, "
        "and idempotent finalization."
    ),
    version="0.1.0",
)

app.include_router(evaluation_runs_router)


@app.get(
    "/health",
    tags=["Health"],
)
def health_check() -> dict[str, str]:
    return {"status": "healthy"}
