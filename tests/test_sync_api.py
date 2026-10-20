import pytest
from fastapi.testclient import TestClient

from api.dependencies import get_sync_service
from main import main_app


class FakeSyncService:
    def __init__(self, accepts: bool) -> None:
        self.accepts = accepts

    def trigger(self) -> bool:
        return self.accepts


@pytest.fixture
def client():
    yield TestClient(main_app)
    main_app.dependency_overrides.clear()


def test_trigger_started(client):
    main_app.dependency_overrides[get_sync_service] = lambda: FakeSyncService(True)

    response = client.post("/api/sync/trigger")

    assert response.status_code == 200
    assert response.json() == {
        "status": "started",
        "message": "Synchronization triggered",
    }


def test_trigger_already_running(client):
    main_app.dependency_overrides[get_sync_service] = lambda: FakeSyncService(False)

    response = client.post("/api/sync/trigger")

    assert response.status_code == 200
    assert response.json()["status"] == "already_running"
