from fastapi import FastAPI

from . import storage
from .database import Base, engine
from .routers import auth, buildings, captures, measurements

app = FastAPI(
    title="StructAI Vision API",
    version="0.1.0",
    description="Medição de m² de fachadas via fotogrametria (Sessões 0-3). "
                "Arquitetura completa: docs/roadmap.md",
)


@app.on_event("startup")
def startup() -> None:
    # scaffold: create_all direto; migrar p/ Alembic quando o schema estabilizar
    Base.metadata.create_all(engine)
    storage.ensure_bucket()


@app.get("/health", tags=["infra"])
def health() -> dict:
    return {"status": "ok", "service": "structai-vision", "version": "0.1.0"}


app.include_router(auth.router)
app.include_router(buildings.router)
app.include_router(captures.router)
app.include_router(measurements.router)
