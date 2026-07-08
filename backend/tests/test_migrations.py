"""As migrações Alembic criam o schema completo a partir do zero."""
from sqlalchemy import create_engine, inspect

from app.migrations import run_migrations


def test_upgrade_head_creates_schema(tmp_path):
    url = f"sqlite:///{tmp_path}/mig.db"
    run_migrations(url)

    engine = create_engine(url)
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    assert {"users", "buildings", "captures", "measurements",
            "alembic_version"} <= tables

    capture_cols = {c["name"] for c in insp.get_columns("captures")}
    assert "has_video" in capture_cols  # migração 0002
    engine.dispose()


def test_upgrade_is_idempotent(tmp_path):
    url = f"sqlite:///{tmp_path}/mig.db"
    run_migrations(url)
    run_migrations(url)  # segundo upgrade head não pode quebrar
