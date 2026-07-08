"""Aplica as migrações Alembic programaticamente (usado no lifespan da API).

Equivalente a `alembic upgrade head` rodado de backend/ — mesma configuração,
mesmos scripts. O parâmetro database_url existe para os testes apontarem para
um banco descartável.
"""
from pathlib import Path

from alembic import command
from alembic.config import Config

from .config import settings

BACKEND_DIR = Path(__file__).resolve().parent.parent


def run_migrations(database_url: str | None = None) -> None:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    url = database_url or settings.database_url
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))  # escapa p/ configparser
    command.upgrade(cfg, "head")
