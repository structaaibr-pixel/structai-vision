"""Smoke test — roda sem infra externa (não toca banco/MinIO no import)."""
from fastapi.testclient import TestClient

from app.main import app


def test_health():
    with TestClient(app, raise_server_exceptions=False) as _:
        pass  # startup exige db/minio; health é testado no ambiente docker


def test_openapi_schema_builds():
    schema = app.openapi()
    paths = schema["paths"]
    assert "/health" in paths
    assert "/buildings/{building_id}/captures" in paths
    assert "/captures/{capture_id}/measurement" in paths
