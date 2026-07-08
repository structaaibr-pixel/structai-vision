"""Sessão 3 — Pipeline assíncrono de reconstrução.

Fluxo por captura:
  MinIO (imagens + GCP) → filtro de nitidez → NodeODM → malha 3D
  → Measure Engine → Measurement no banco → artefatos de volta no MinIO

Falhas comuns de fachada (pouca sobreposição, parede sem textura, fotos
borradas) devem terminar em status=failed com mensagem clara — nunca travar
em silêncio.
"""
import shutil
import tempfile
from pathlib import Path

import cv2

from ..config import settings
from ..database import SessionLocal
from ..measure.engine import measure_mesh
from ..models import Capture, CaptureStatus, Measurement
from .. import storage
from .celery_app import celery

MIN_SHARPNESS = 100.0
MIN_USABLE_IMAGES = 20


def _is_sharp(path: Path) -> bool:
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    return img is not None and cv2.Laplacian(img, cv2.CV_64F).var() >= MIN_SHARPNESS


def _find_mesh(assets: Path) -> Path | None:
    for rel in ("odm_texturing/odm_textured_model_geo.obj",
                "odm_meshing/odm_mesh.ply"):
        if (assets / rel).exists():
            return assets / rel
    return None


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
        # 1. baixar imagens do MinIO
        img_dir = workdir / "images"
        img_dir.mkdir()
        keys = storage.list_keys(f"captures/{capture_id}/images/")
        if not keys:
            raise RuntimeError("nenhuma imagem encontrada para esta captura")
        for k in keys:
            storage.download_to(k, str(img_dir / Path(k).name))

        # 2. filtrar borradas (frames ruins quebram a reconstrução)
        images = [p for p in sorted(img_dir.iterdir()) if _is_sharp(p)]
        removed = len(keys) - len(images)
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
