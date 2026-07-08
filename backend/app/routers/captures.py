"""Sessão 2 (lado servidor) — recepção de capturas.

Recebe fotos (celular ou drone) e/ou vídeo da fachada + arquivo GCP opcional
+ notas do técnico, salva tudo no MinIO em streaming (sem carregar o arquivo
inteiro em memória) e enfileira a reconstrução (Sessão 3). Os frames do vídeo
são extraídos no início da task (app/preprocess.py). A reconstrução NUNCA é
síncrona.
"""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ..auth import get_current_user
from ..database import get_db
from ..models import Capture, CaptureSource, CaptureStatus, User
from ..schemas import CaptureOut
from .. import storage
from ..workers.reconstruction import run_reconstruction
from .buildings import get_owned_building

router = APIRouter(tags=["captures"])

IMAGE_TYPES = {"image/jpeg", "image/png", "image/tiff"}
VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/x-msvideo", "video/x-matroska"}
MIN_IMAGES_WITHOUT_VIDEO = 5


@router.post("/buildings/{building_id}/captures", response_model=CaptureOut,
             status_code=202)
async def create_capture(
    building_id: int,
    images: list[UploadFile] | None = File(None, description="fotos da fachada"),
    video: UploadFile | None = File(
        None, description="vídeo da fachada (frames extraídos no servidor)"),
    gcp: UploadFile | None = File(None, description="gcp_list.txt (formato ODM)"),
    source: CaptureSource = Form(CaptureSource.phone),
    notes: str | None = Form(None, description="observações (ex.: transcrição Whisper)"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_owned_building(building_id, db, user)
    images = images or []

    # validar TUDO antes de criar a captura — nada de linha órfã em pending
    if video is None and len(images) < MIN_IMAGES_WITHOUT_VIDEO:
        raise HTTPException(
            422, f"envie um vídeo ou pelo menos {MIN_IMAGES_WITHOUT_VIDEO} imagens "
                 "(ideal: 30+ com 70-80% de sobreposição)")
    for f in images:
        if f.content_type not in IMAGE_TYPES:
            raise HTTPException(422, f"tipo de imagem não suportado: {f.content_type}")
    if video is not None and video.content_type not in VIDEO_TYPES:
        raise HTTPException(422, f"tipo de vídeo não suportado: {video.content_type} "
                                 "— use MP4 (H.264)")

    capture = Capture(building_id=building_id, source=source,
                      status=CaptureStatus.pending, image_count=len(images),
                      has_gcp=gcp is not None, has_video=video is not None,
                      notes=notes)
    db.add(capture)
    db.commit()

    # upload em streaming (chunks) — o put_object é bloqueante, então roda no
    # threadpool para não travar o event loop com arquivos grandes
    for i, f in enumerate(images):
        await run_in_threadpool(
            storage.put_stream,
            f"captures/{capture.id}/images/{i:04d}_{f.filename or 'img.jpg'}",
            f.file, f.content_type or "image/jpeg")

    if video is not None:
        await run_in_threadpool(
            storage.put_stream,
            f"captures/{capture.id}/video/{video.filename or 'video.mp4'}",
            video.file, video.content_type or "video/mp4")

    if gcp is not None:
        await run_in_threadpool(
            storage.put_stream, f"captures/{capture.id}/gcp_list.txt",
            gcp.file, "text/plain")

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
