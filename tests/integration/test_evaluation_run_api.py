
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


def setup_database():
    Base.metadata.create_all(bind=engine)


def teardown_database():
    Base.metadata.drop_all(bind=engine)


def test_evaluation_run_api():
    setup_database()

    try:
        with TestClient(app) as client:
            create_response = client.post("/evaluation-runs")

            assert create_response.status_code == 201

            created_run = create_response.json()
            run_id = created_run["id"]

            assert created_run["status"] == "pending"
            assert created_run["result"] is None
            assert created_run["error_message"] is None
            assert created_run["completed_at"] is None
            assert created_run["created_at"] is not None
            assert created_run["updated_at"] is not None

            get_response = client.get(f"/evaluation-runs/{run_id}")

            assert get_response.status_code == 200
            assert get_response.json()["id"] == run_id

            list_response = client.get("/evaluation-runs")

            assert list_response.status_code == 200
            assert len(list_response.json()) == 1

            missing_response = client.get(
                "/evaluation-runs/00000000-0000-0000-0000-000000000000"
            )

            assert missing_response.status_code == 404
    finally:
        teardown_database()


def test_evaluation_run_complete_api():
    setup_database()

    try:
        with TestClient(app) as client:
            create_response = client.post("/evaluation-runs")
            run_id = create_response.json()["id"]

            start_response = client.post(
                f"/evaluation-runs/{run_id}/start"
            )

            assert start_response.status_code == 200
            assert start_response.json()["status"] == "running"

            result = {"score": 0.95, "passed": True}

            complete_response = client.post(
                f"/evaluation-runs/{run_id}/complete",
                json={"result": result},
            )

            assert complete_response.status_code == 200
            completed_run = complete_response.json()

            assert completed_run["status"] == "completed"
            assert completed_run["result"] == result
            assert completed_run["error_message"] is None
            assert completed_run["completed_at"] is not None
            assert completed_run["updated_at"] == completed_run["completed_at"]

            duplicate_response = client.post(
                f"/evaluation-runs/{run_id}/complete",
                json={"result": result},
            )

            assert duplicate_response.status_code == 200
            assert duplicate_response.json()["result"] == result
            assert (
                duplicate_response.json()["completed_at"]
                == completed_run["completed_at"]
            )
    finally:
        teardown_database()


def test_evaluation_run_fail_api():
    setup_database()

    try:
        with TestClient(app) as client:
            create_response = client.post("/evaluation-runs")
            run_id = create_response.json()["id"]

            start_response = client.post(
                f"/evaluation-runs/{run_id}/start"
            )

            assert start_response.status_code == 200

            fail_response = client.post(
                f"/evaluation-runs/{run_id}/fail",
                json={"error_message": "Evaluation failed"},
            )

            assert fail_response.status_code == 200
            failed_run = fail_response.json()

            assert failed_run["status"] == "failed"
            assert failed_run["error_message"] == "Evaluation failed"
            assert failed_run["completed_at"] is not None
            assert failed_run["updated_at"] == failed_run["completed_at"]
    finally:
        teardown_database()


def test_start_missing_evaluation_run_api():
    setup_database()

    try:
        with TestClient(app) as client:
            response = client.post(
                "/evaluation-runs/00000000-0000-0000-0000-000000000000/start"
            )

            assert response.status_code == 404
            assert response.json()["detail"] == "Evaluation run not found"
    finally:
        teardown_database()


def test_complete_pending_evaluation_run_api():
    setup_database()

    try:
        with TestClient(app) as client:
            create_response = client.post("/evaluation-runs")
            run_id = create_response.json()["id"]

            response = client.post(
                f"/evaluation-runs/{run_id}/complete",
                json={"result": {"score": 0.95}},
            )

            assert response.status_code == 409
            assert (
                response.json()["detail"]
                == "Only running runs can be completed"
            )
    finally:
        teardown_database()


def test_repeated_completion_with_same_result_api():
    setup_database()

    try:
        with TestClient(app) as client:
            create_response = client.post("/evaluation-runs")
            run_id = create_response.json()["id"]

            start_response = client.post(
                f"/evaluation-runs/{run_id}/start"
            )

            assert start_response.status_code == 200

            result = {"score": 0.95, "passed": True}

            first_response = client.post(
                f"/evaluation-runs/{run_id}/complete",
                json={"result": result},
            )

            assert first_response.status_code == 200

            original_completed_at = first_response.json()["completed_at"]

            second_response = client.post(
                f"/evaluation-runs/{run_id}/complete",
                json={"result": result},
            )

            assert second_response.status_code == 200
            assert second_response.json()["status"] == "completed"
            assert second_response.json()["result"] == result
            assert (
                second_response.json()["completed_at"]
                == original_completed_at
            )
    finally:
        teardown_database()


def test_repeated_completion_with_different_result_api():
    setup_database()

    try:
        with TestClient(app) as client:
            create_response = client.post("/evaluation-runs")
            run_id = create_response.json()["id"]

            client.post(f"/evaluation-runs/{run_id}/start")

            first_response = client.post(
                f"/evaluation-runs/{run_id}/complete",
                json={"result": {"score": 0.95}},
            )

            assert first_response.status_code == 200

            response = client.post(
                f"/evaluation-runs/{run_id}/complete",
                json={"result": {"score": 0.98}},
            )

            assert response.status_code == 409
            assert response.json()["detail"] == (
                "Evaluation run is already completed with a different result"
            )
    finally:
        teardown_database()


def test_cannot_start_running_evaluation_run_api():
    setup_database()

    try:
        with TestClient(app) as client:
            run_id = client.post("/evaluation-runs").json()["id"]

            first_response = client.post(
                f"/evaluation-runs/{run_id}/start"
            )

            assert first_response.status_code == 200

            second_response = client.post(
                f"/evaluation-runs/{run_id}/start"
            )

            assert second_response.status_code == 409
            assert (
                second_response.json()["detail"]
                == "Only pending runs can be started"
            )
    finally:
        teardown_database()


def test_cannot_fail_pending_evaluation_run_api():
    setup_database()

    try:
        with TestClient(app) as client:
            run_id = client.post("/evaluation-runs").json()["id"]

            response = client.post(
                f"/evaluation-runs/{run_id}/fail",
                json={"error_message": "Evaluation failed"},
            )

            assert response.status_code == 409
            assert (
                response.json()["detail"]
                == "Only running runs can be failed"
            )
    finally:
        teardown_database()


def test_cannot_fail_completed_evaluation_run_api():
    setup_database()

    try:
        with TestClient(app) as client:
            run_id = client.post("/evaluation-runs").json()["id"]

            client.post(f"/evaluation-runs/{run_id}/start")

            complete_response = client.post(
                f"/evaluation-runs/{run_id}/complete",
                json={"result": {"score": 0.95}},
            )

            assert complete_response.status_code == 200

            fail_response = client.post(
                f"/evaluation-runs/{run_id}/fail",
                json={"error_message": "Late failure"},
            )

            assert fail_response.status_code == 409
            assert (
                fail_response.json()["detail"]
                == "Only running runs can be failed"
            )
    finally:
        teardown_database()


def test_cannot_complete_failed_evaluation_run_api():
    setup_database()

    try:
        with TestClient(app) as client:
            run_id = client.post("/evaluation-runs").json()["id"]

            client.post(f"/evaluation-runs/{run_id}/start")

            fail_response = client.post(
                f"/evaluation-runs/{run_id}/fail",
                json={"error_message": "Evaluation failed"},
            )

            assert fail_response.status_code == 200

            complete_response = client.post(
                f"/evaluation-runs/{run_id}/complete",
                json={"result": {"score": 0.95}},
            )

            assert complete_response.status_code == 409
            assert (
                complete_response.json()["detail"]
                == "Only running runs can be completed"
            )
    finally:
        teardown_database()


def test_fail_missing_evaluation_run_api():
    setup_database()

    try:
        with TestClient(app) as client:
            response = client.post(
                "/evaluation-runs/00000000-0000-0000-0000-000000000000/fail",
                json={"error_message": "Evaluation failed"},
            )

            assert response.status_code == 404
            assert response.json()["detail"] == "Evaluation run not found"
    finally:
        teardown_database()


def test_fail_rejects_empty_error_message_api():
    setup_database()

    try:
        with TestClient(app) as client:
            run_id = client.post("/evaluation-runs").json()["id"]

            client.post(f"/evaluation-runs/{run_id}/start")

            response = client.post(
                f"/evaluation-runs/{run_id}/fail",
                json={"error_message": ""},
            )

            assert response.status_code == 422
    finally:
        teardown_database()


def teardown_module():
    app.dependency_overrides.clear()
    engine.dispose()
