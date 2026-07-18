from fastapi.testclient import TestClient


def test_health_check_reports_database(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Survival Agent API",
        "environment": "development",
        "database": {
            "status": "healthy",
            "engine": "sqlite",
            "journal_mode": "wal",
        },
    }
