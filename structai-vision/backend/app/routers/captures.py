"""Sessão 2 (lado servidor) — recepção de capturas.

Recebe fotos (celular ou drone) + arquivo GCP opcional + notas do técnico,
salva tudo no MinIO e enfileira a reconstrução (Sessão 3). A reconstrução
NUNCA é síncrona.
"""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Capture, CaptureSource, CaptureStatus, User
from ..schemas import CaptureOut
from .. import storage
from ..workers.reconstruction import run_reconstruction
from .buildings import get_owned_building

router = APIRouter(tags=["captures"])

IMAGE_TYPES = {"image/jpeg", "image/png", "image/tiff"}


@router.post("/buildings/{building_id}/captures", response_model=CaptureOut,
             status_code=202)
async def create_capture(
    building_id: int,
    images: list[UploadFile] = File(..., description="fotos da fachada"),
    gcp: UploadFile | None = File(None, description="gcp_list.txt (formato ODM)"),
    source: CaptureSource = Form(CaptureSource.phone),
    notes: str | None = Form(None, description="observações (ex.: transcrição Whisper)"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_owned_building(building_id, db, user)
    if len(images) < 5:
        raise HTTPException(422, "envie pelo menos 5 imagens (ideal: 30+ com "
                                 "70-80% de sobreposição)")

    capture = Capture(building_id=building_id, source=source,
                      status=CaptureStatus.pending, image_count=len(images),
                      has_gcp=gcp is not None, notes=notes)
    db.add(capture)
    db.commit()

    for i, f in enumerate(images):
        if f.content_type not in IMAGE_TYPES:
            raise HTTPException(422, f"tipo não suportado: {f.content_type}")
        data = await f.read()
        storage.put_bytes(
            f"captures/{capture.id}/images/{i:04d}_{f.filename or 'img.jpg'}",
            data, f.content_type or "image/jpeg")

    if gcp is not None:
        storage.put_bytes(f"captures/{capture.id}/gcp_list.txt",
                          await gcp.read(), "text/plain")

    run_reconstruction.delay(capture.id)
    return capture


@router.get("/captures/{capture_id}", response_model=CaptureOut)
def get_capture(capture_id: int, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    c = db.get(Capture, capture_id)
    if c is None:
        raise HTTPException(404, "captura não encontrada")
    get_owned_building(c.building_id, db, user)
    return c
