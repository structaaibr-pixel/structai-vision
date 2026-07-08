"""Smoke tests — rodam sem infra externa (o lifespan não é executado)."""
from fastapi.testclient import TestClient

from app.main import app


def test_health():
    client = TestClient(app)  # sem `with` → lifespan (migração/MinIO) não roda
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_openapi_schema_builds():
    schema = app.openapi()
    paths = schema["paths"]
    assert "/health" in paths
    assert "/buildings/{building_id}/captures" in paths
    assert "/captures/{capture_id}/measurement" in paths
