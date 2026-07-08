"""Pré-processamento de imagens e vídeo, compartilhado pelas tasks.

Concentra a lógica de nitidez (antes duplicada em workers/reconstruction.py e
scripts/validate_measurement.py) e a extração de frames de vídeo no servidor
(débito D3): vídeo gera muito frame redundante, então extraímos 1 a cada
FRAME_EVERY_N e deixamos o filtro de nitidez descartar os borrados.
"""
from pathlib import Path

import cv2

MIN_SHARPNESS = 100.0   # variância do Laplaciano abaixo disso = borrada
MIN_USABLE_IMAGES = 20
FRAME_EVERY_N = 15


def sharpness(path: str | Path) -> float:
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return 0.0
    return float(cv2.Laplacian(img, cv2.CV_64F).var())


def is_sharp(path: str | Path, threshold: float = MIN_SHARPNESS) -> bool:
    return sharpness(path) >= threshold


def filter_blurry(images: list[Path], threshold: float = MIN_SHARPNESS
                  ) -> tuple[list[Path], int]:
    """Retorna (imagens nítidas, quantidade descartada)."""
    kept = [p for p in images if is_sharp(p, threshold)]
    return kept, len(images) - len(kept)


def extract_frames(video_path: str | Path, out_dir: str | Path,
                   every_n: int = FRAME_EVERY_N) -> list[Path]:
    """Extrai 1 a cada `every_n` frames do vídeo para `out_dir` (JPEG q95)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"não consegui abrir o vídeo: {video_path}")
    frames: list[Path] = []
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i % every_n == 0:
            p = out_dir / f"frame_{i:06d}.jpg"
            cv2.imwrite(str(p), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            frames.append(p)
        i += 1
    cap.release()
    return frames
