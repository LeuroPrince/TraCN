from fastapi.testclient import TestClient

from app.main import app


def test_llm_config_does_not_leak_api_key() -> None:
    client = TestClient(app)

    response = client.get("/api/llm/config")

    assert response.status_code == 200
    payload = response.json()
    assert "api_key" not in payload
    assert "has_api_key" in payload
