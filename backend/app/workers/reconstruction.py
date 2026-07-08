"""Sessão 3 — Pipeline assíncrono de reconstrução.

Fluxo por captura:
  MinIO (imagens + vídeo + GCP) → frames do vídeo → filtro de nitidez
  → NodeODM → malha 3D → Measure Engine → Measurement no banco
  → artefatos de volta no MinIO

Falhas comuns de fachada (pouca sobreposição, parede sem textura, fotos
borradas) devem terminar em status=failed com mensagem clara — nunca travar
em silêncio.
"""
import shutil
import tempfile
from pathlib import Path

from ..config import settings
from ..database import SessionLocal
from ..measure.engine import measure_mesh
from ..models import Capture, CaptureStatus, Measurement
from ..preprocess import MIN_USABLE_IMAGES, extract_frames, filter_blurry
from .. import storage
from .celery_app import celery


def _find_mesh(assets: Path) -> Path | None:
    for rel in ("odm_texturing/odm_textured_model_geo.obj",
                "odm_meshing/odm_mesh.ply"):
        if (assets / rel).exists():
            return assets / rel
    return None


def _download_video_frames(capture_id: int, workdir: Path, img_dir: Path) -> int:
    """Baixa o vídeo da captura (se houver) e extrai frames para img_dir."""
    video_keys = storage.list_keys(f"captures/{capture_id}/video/")
    if not video_keys:
        return 0
    video_dir = workdir / "video"
    video_dir.mkdir()
    total = 0
    for k in video_keys:
        local = video_dir / Path(k).name
        storage.download_to(k, str(local))
        frames = extract_frames(local, img_dir)
        if not frames:
            raise RuntimeError(
                f"nenhum frame extraído do vídeo {Path(k).name} — arquivo "
                "corrompido ou formato não suportado. Reenvie em MP4 (H.264).")
        total += len(frames)
    return total


@celery.task(name="reconstruction.run", bind=True)
def run_reconstruction(self, capture_id: int) -> None:
    db = SessionLocal()
    capture = db.get(Capture, capture_id)
    if capture is None:
        db.close()
        return
    capture.status = CaptureStatus.processing
    db.commit()

    workdir = Path(tempfile.mkdtemp(prefix=f"structai_cap{capture_id}_"))
    try:
        # 1. baixar imagens do MinIO + extrair frames do vídeo (se houver)
        img_dir = workdir / "images"
        img_dir.mkdir()
        keys = storage.list_keys(f"captures/{capture_id}/images/")
        for k in keys:
            storage.download_to(k, str(img_dir / Path(k).name))
        frame_count = _download_video_frames(capture_id, workdir, img_dir)
        if not keys and not frame_count:
            raise RuntimeError("nenhuma imagem ou vídeo encontrado para esta captura")

        # 2. filtrar borradas (frames ruins quebram a reconstrução)
        images, removed = filter_blurry(sorted(img_dir.iterdir()))
        if len(images) < MIN_USABLE_IMAGES:
            raise RuntimeError(
                f"apenas {len(images)} imagens nítidas ({removed} borradas "
                f"descartadas) — mínimo {MIN_USABLE_IMAGES}. Recapture com mais "
                "sobreposição (70-80%) e melhor estabilidade.")

        files = [str(p) for p in images]

        # 3. GCP → escala métrica (sem ele o m² sai em escala relativa)
        gcp_keys = storage.list_keys(f"captures/{capture_id}/gcp_list.txt")
        if gcp_keys:
            gcp_path = img_dir / "gcp_list.txt"
            storage.download_to(gcp_keys[0], str(gcp_path))
            files.append(str(gcp_path))

        # 4. reconstrução via NodeODM (dependência externa, nunca código copiado)
        from pyodm import Node
        node = Node(settings.nodeodm_host, settings.nodeodm_port)
        task = node.create_task(files, {
            "feature-quality": settings.odm_quality,
            "pc-quality": settings.odm_quality,
            "mesh-octree-depth": 11,
            "dsm": False,
            "skip-orthophoto": True,
        }, name=f"capture-{capture_id}")
        task.wait_for_completion()

        assets = workdir / "assets"
        task.download_assets(str(assets))

        mesh_path = _find_mesh(assets)
        if mesh_path is None:
            raise RuntimeError(
                "ODM terminou sem gerar malha — causas típicas em fachada: "
                "janelas repetidas confundindo o matching, parede lisa sem "
                "textura, ou sobreposição insuficiente entre fotos.")

        # 5. medir e persistir
        result = measure_mesh(mesh_path)
        mesh_key = storage.put_file(
            f"captures/{capture_id}/results/{mesh_path.name}", str(mesh_path))
        pc = assets / "odm_georeferencing/odm_georeferenced_model.laz"
        pc_key = (storage.put_file(f"captures/{capture_id}/results/{pc.name}", str(pc))
                  if pc.exists() else None)

        db.add(Measurement(
            capture_id=capture_id,
            surface_area_m2=result["surface_area_m2"],
            height_m=result["height_m"],
            footprint_perimeter_m=result["footprint_perimeter_m"],
            mesh_key=mesh_key,
            pointcloud_key=pc_key,
            raw={**result, "blurry_removed": removed,
                 "video_frames": frame_count,
                 "gcp_used": bool(gcp_keys)},
        ))
        capture.status = CaptureStatus.completed
        capture.error = None
        db.commit()

    except Exception as exc:  # noqa: BLE001 — status legível > stacktrace mudo
        capture.status = CaptureStatus.failed
        capture.error = str(exc)[:2000]
        db.commit()
        raise
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
        db.close()
