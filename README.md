# AI Evaluation Reliability Platform

A Python-based platform for managing AI evaluation runs with persistent storage, controlled lifecycle transitions, and reliable result finalization.

## Overview

The AI Evaluation Reliability Platform provides an API for creating, tracking, and managing evaluation runs.

Each evaluation run follows a controlled lifecycle:

- `pending`: The run has been created but not started.
- `running`: The run is currently being processed.
- `completed`: The run has finished successfully and contains an evaluation result.
- `failed`: The run has finished unsuccessfully and contains an error message.

The platform prevents invalid lifecycle transitions and supports idempotent completion when the same result is submitted more than once.

## Features

- Create and retrieve evaluation runs
- List all evaluation runs
- Start pending evaluation runs
- Complete running evaluation runs
- Fail running evaluation runs
- Persist evaluation results and failure messages
- Prevent invalid lifecycle transitions
- Support repeated completion with the same result
- Reject conflicting completion results
- Use conditional database updates for lifecycle transitions
- Manage database schema changes with Alembic
- Automated unit, API integration, and persistence tests

## Technology Stack

- Python 3.11+
- FastAPI
- Pydantic
- SQLAlchemy
- SQLite
- Alembic
- Pytest
- HTTPX

## Project Structure

```text
.
├── app/
│   ├── api/
│   │   └── routes/
│   ├── core/
│   ├── evaluation/
│   ├── models/
│   ├── repositories/
│   ├── schemas/
│   ├── services/
│   ├── init_database.py
│   └── main.py
├── docs/
├── migrations/
│   └── versions/
├── tests/
│   ├── integration/
│   ├── persistence/
│   └── unit/
├── alembic.ini
├── pyproject.toml
└── README.md
```

## Requirements

- Python 3.11 or later
- pip
- Git

## Installation

Clone the repository and navigate to the project directory.

Create a virtual environment:

```powershell
python -m venv .venv
```

Activate the virtual environment on Windows:

```powershell
.venv\Scripts\Activate.ps1
```

Install the project and development dependencies:

```powershell
python -m pip install -e ".[dev]"
```

## Database Setup

Apply database migrations:

```powershell
python -m alembic upgrade head
```

This creates the schema on a new database and applies any pending revisions.
The optional initializer uses the same Alembic migration path and is safe to
run again:

```powershell
python -m app.init_database
```

For an existing unversioned database, back it up and verify that the
`evaluation_runs` table has the original columns (`id`, `status`, `created_at`,
and `updated_at`) and the `ix_evaluation_runs_status` index before recording
the baseline revision and upgrading:

```powershell
python -m alembic stamp a4c98d5f2e71
python -m alembic upgrade head
```

If an unversioned database already has the result fields, verify that it
matches the current schema before stamping it at `be4c5f4e3330`:

```powershell
python -m alembic stamp be4c5f4e3330
```

Databases already stamped at `be4c5f4e3330` can be upgraded normally; the
existing revision ID is retained.

Check the current migration revision:

```powershell
python -m alembic current
```

## Running the Application

Start the FastAPI development server:

```powershell
python -m uvicorn app.main:app --reload
```

The API will be available at:

`http://127.0.0.1:8000`

Interactive API documentation:

`http://127.0.0.1:8000/docs`

Health check:

`http://127.0.0.1:8000/health`

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/evaluation-runs` | Create an evaluation run |
| GET | `/evaluation-runs` | List evaluation runs |
| GET | `/evaluation-runs/{run_id}` | Retrieve an evaluation run |
| POST | `/evaluation-runs/{run_id}/start` | Start a pending run |
| POST | `/evaluation-runs/{run_id}/complete` | Complete a running run |
| POST | `/evaluation-runs/{run_id}/fail` | Fail a running run |

## Example Requests

### Create an Evaluation Run

```http
POST /evaluation-runs
```

### Start an Evaluation Run

```http
POST /evaluation-runs/{run_id}/start
```

### Complete an Evaluation Run

```http
POST /evaluation-runs/{run_id}/complete
Content-Type: application/json
```

Request body:

```json
{
  "result": {
    "score": 0.95,
    "passed": true
  }
}
```

### Fail an Evaluation Run

```http
POST /evaluation-runs/{run_id}/fail
Content-Type: application/json
```

Request body:

```json
{
  "error_message": "Evaluation failed"
}
```

## Lifecycle Rules

The supported lifecycle transitions are:

```text
pending
   |
   v
running
   |
   +------> completed
   |
   +------> failed
```

The platform enforces the following rules:

- Only pending runs can be started.
- Only running runs can be completed.
- Only running runs can be failed.
- A completed run cannot be failed.
- A failed run cannot be completed.
- Repeating completion with the same result returns the existing completed run.
- Repeating completion with a different result is rejected.

## Testing

Run the complete test suite:

```powershell
python -m pytest -v
```

Run unit tests:

```powershell
python -m pytest tests/unit -v
```

Run API integration tests:

```powershell
python -m pytest tests/integration -v
```

Run persistence tests:

```powershell
python -m pytest tests/persistence -v
```

The current test suite contains 33 passing tests across unit, API integration, and persistence test categories.

## Database Migrations

Generate a migration after changing database models:

```powershell
python -m alembic revision --autogenerate -m "describe schema change"
```

Apply migrations:

```powershell
python -m alembic upgrade head
```

Revert the latest migration:

```powershell
python -m alembic downgrade -1
```

## Reliability Considerations

Evaluation run finalization uses a conditional database update that only succeeds when the run is still in the `running` state.

This prevents a finalization request from overwriting a run that has already transitioned out of the running state.

The persistence tests verify competing finalization attempts using separate database sessions. They do not constitute a full simultaneous concurrency or production-load test.

## Current Limitations

- SQLite is currently used for persistence.
- The API is designed as a local development platform.
- No authentication or authorization layer is currently implemented.
- No distributed task queue is currently included.
- Production deployment and load testing have not yet been validated.
- The current test suite does not establish production concurrency guarantees.

## License

No license has been specified yet.
