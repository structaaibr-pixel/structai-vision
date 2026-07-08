from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import storage
from .migrations import run_migrations
from .routers import auth, buildings, captures, measurements


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()  # alembic upgrade head — schema só muda via migração (D1)
    storage.ensure_bucket()
    yield


app = FastAPI(
    title="StructAI Vision API",
    version="0.2.0",
    description="Medição de m² de fachadas via fotogrametria (Sessões 0-3). "
                "Arquitetura completa: docs/roadmap.md",
    lifespan=lifespan,
)


@app.get("/health", tags=["infra"])
def health() -> dict:
    return {"status": "ok", "service": "structai-vision", "version": "0.2.0"}


app.include_router(auth.router)
app.include_router(buildings.router)
app.include_router(captures.router)
app.include_router(measurements.router)
