from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_health_returns_liveness_status():
    app = create_app(Settings(check_dependencies=False))
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "agentflow-api",
        "version": "0.1.0",
    }


def test_ready_skips_dependency_checks_when_disabled():
    app = create_app(Settings(check_dependencies=False))
    client = TestClient(app)

    response = client.get("/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"] == {
        "database": "skipped",
        "redis": "skipped",
        "minio": "skipped",
    }

