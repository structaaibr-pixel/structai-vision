"""Fixtures compartilhadas — banco SQLite descartável (criado pelas migrações
Alembic reais) + storage e fila Celery substituídos por fakes em memória.
Nenhum teste depende de Postgres/MinIO/Redis: é o que permite CI sem infra.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import storage
from app.auth import get_current_user
from app.database import get_db
from app.main import app
from app.migrations import run_migrations
from app.models import Building, User
from app.routers import captures as captures_router


@pytest.fixture()
def db_session(tmp_path):
    url = f"sqlite:///{tmp_path}/test.db"
    run_migrations(url)  # o schema de teste nasce das migrações, não do create_all
    engine = create_engine(url)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def user(db_session):
    u = User(email="tecnico@structai.com", hashed_password="hash-irrelevante")
    db_session.add(u)
    db_session.commit()
    return u


@pytest.fixture()
def building(db_session, user):
    b = Building(owner_id=user.id, name="Ed. Alfa", address="Rua A, 123")
    db_session.add(b)
    db_session.commit()
    return b


@pytest.fixture()
def fake_storage(monkeypatch):
    """Captura os uploads em memória: {key: bytes}."""
    saved: dict[str, bytes] = {}

    def put_stream(key, stream, content_type="application/octet-stream"):
        saved[key] = stream.read()
        return key

    monkeypatch.setattr(storage, "put_stream", put_stream)
    return saved


@pytest.fixture()
def fake_reconstruction(monkeypatch):
    """Registra os capture_ids enfileirados em vez de falar com o Redis."""
    calls: list[int] = []
    monkeypatch.setattr(captures_router.run_reconstruction, "delay",
                        lambda capture_id: calls.append(capture_id))
    return calls


@pytest.fixture()
def client(db_session, user, fake_storage, fake_reconstruction):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: user
    yield TestClient(app)  # sem `with` → lifespan (migração real/MinIO) não roda
    app.dependency_overrides.clear()
