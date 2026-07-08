#!/usr/bin/env python3
"""
StructAI Vision — Sessão 0: Harness de validação de medição.

Script STANDALONE (sem backend, sem banco). Fluxo:
  fotos (ou vídeo) + arquivo GCP  →  NodeODM  →  malha 3D  →  área / altura / perímetro

Uso típico:
  # suba o NodeODM antes:  docker run -d -p 3000:3000 opendronemap/nodeodm
  python validate_measurement.py --images ./fotos_predio_A --gcp ./gcp_list.txt
  python validate_measurement.py --video ./fachada.mp4 --gcp ./gcp_list.txt
  python validate_measurement.py --images ./fotos --fast   # teste rápido, menor qualidade

Formato do arquivo GCP (formato ODM, gcp_list.txt):
  linha 1: header de projeção (ex.: "EPSG:31983" ou "+proj=utm +zone=23 +south ...")
  demais:  geo_x geo_y geo_z pixel_x pixel_y nome_da_imagem.jpg
  IMPORTANTE: não precisam ser coordenadas GPS reais — coordenadas locais medidas
  com trena/laser funcionam, desde que consistentes entre si. É isso que dá escala
  métrica ao modelo. SEM GCP o resultado sai em escala RELATIVA (m² inválido).

Compare SEMPRE o resultado com medição manual (trena/laser) em 2-3 prédios reais
antes de avançar para as próximas sessões.
"""

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
DEFAULT_SHARPNESS = 100.0  # variância do Laplaciano abaixo disso = borrada


# ---------------------------------------------------------------- captura

def extract_frames(video_path: Path, out_dir: Path, every_n: int = 15) -> list[Path]:
    """Extrai 1 a cada `every_n` frames do vídeo (vídeo gera muito frame redundante)."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        sys.exit(f"[erro] não consegui abrir o vídeo: {video_path}")
    frames, i = [], 0
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
    print(f"[captura] {len(frames)} frames extraídos de {i} totais ({video_path.name})")
    return frames


def sharpness(path: Path) -> float:
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return 0.0
    return float(cv2.Laplacian(img, cv2.CV_64F).var())


def filter_blurry(images: list[Path], threshold: float) -> list[Path]:
    """Remove imagens borradas — frames ruins quebram a reconstrução."""
    kept = [p for p in images if sharpness(p) >= threshold]
    removed = len(images) - len(kept)
    print(f"[filtro] {removed} imagem(ns) borrada(s) descartada(s), {len(kept)} mantidas")
    if len(kept) < 20:
        print("[aviso] menos de 20 imagens úteis — reconstrução de fachada tende a "
              "falhar. Capture mais fotos com 70-80% de sobreposição.")
    return kept


# ---------------------------------------------------------------- reconstrução

def run_odm(images: list[Path], gcp: Path | None, node_url: str, fast: bool) -> Path:
    """Envia as imagens ao NodeODM e baixa os resultados. Retorna o dir de assets."""
    from pyodm import Node  # import tardio: falha clara se pyodm não instalado
    from urllib.parse import urlparse

    u = urlparse(node_url if "//" in node_url else f"http://{node_url}")
    node = Node(u.hostname or "localhost", u.port or 3000)

    files = [str(p) for p in images]
    if gcp:
        # ODM reconhece o GCP pelo nome do arquivo na lista de upload
        tmp_gcp = images[0].parent / "gcp_list.txt"
        if gcp.resolve() != tmp_gcp.resolve():
            shutil.copy(gcp, tmp_gcp)
        files.append(str(tmp_gcp))
        print(f"[odm] GCP incluído: {gcp}")
    else:
        print("[AVISO] sem GCP → modelo em escala RELATIVA. Os números de área/altura "
              "abaixo NÃO são metros reais. Use --gcp para medição de verdade.")

    quality = "medium" if fast else "high"
    options = {
        "feature-quality": quality,
        "pc-quality": quality,
        "mesh-octree-depth": 11,
        "dsm": False,
        "skip-orthophoto": True,  # fachada: a malha importa, não o orto nadir
    }
    print(f"[odm] enviando {len(images)} imagens para {node_url} "
          f"(qualidade={quality})… isso pode levar de minutos a horas.")
    task = node.create_task(files, options, name="structai-validation")
    task.wait_for_completion(status_callback=lambda info: print(
        f"[odm] progresso: {info.progress}%", end="\r"))
    print()

    out = Path(tempfile.mkdtemp(prefix="structai_odm_"))
    task.download_assets(str(out))
    print(f"[odm] resultados em: {out}")
    return out


def find_mesh(assets: Path) -> Path:
    for rel in ("odm_texturing/odm_textured_model_geo.obj",
                "odm_meshing/odm_mesh.ply"):
        p = assets / rel
        if p.exists():
            return p
    sys.exit(f"[erro] nenhuma malha encontrada em {assets} — a reconstrução falhou? "
             "Causas comuns: pouca sobreposição, fachada sem textura, fotos borradas.")


# ---------------------------------------------------------------- medição

def measure(mesh_path: Path) -> dict:
    """Medidas BRUTAS da malha. Área líquida (descontando janelas) é a Sessão 4-5."""
    import trimesh
    from shapely.geometry import MultiPoint

    mesh = trimesh.load(str(mesh_path), force="mesh")
    v = np.asarray(mesh.vertices)
    xy = v[:, :2]
    if len(xy) > 200_000:  # hull não precisa de todos os pontos
        xy = xy[np.random.default_rng(0).choice(len(xy), 200_000, replace=False)]
    hull = MultiPoint([tuple(p) for p in xy]).convex_hull
    return {
        "surface_area_m2": float(mesh.area),
        "height_m": float(v[:, 2].max() - v[:, 2].min()),
        "footprint_perimeter_m": float(hull.length),
        "vertices": int(len(mesh.vertices)),
        "mesh": str(mesh_path),
    }


# ---------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--images", type=Path, help="diretório com as fotos")
    src.add_argument("--video", type=Path, help="vídeo da fachada (frames serão extraídos)")
    ap.add_argument("--gcp", type=Path, help="arquivo GCP no formato ODM (dá escala métrica)")
    ap.add_argument("--node-url", default="http://localhost:3000",
                    help="URL do NodeODM (default: %(default)s)")
    ap.add_argument("--min-sharpness", type=float, default=DEFAULT_SHARPNESS,
                    help="limiar de nitidez p/ descartar borradas (default: %(default)s)")
    ap.add_argument("--every-n", type=int, default=15,
                    help="com --video, extrai 1 a cada N frames (default: %(default)s)")
    ap.add_argument("--fast", action="store_true",
                    help="qualidade média (smoke test, não usar p/ validação final)")
    args = ap.parse_args()

    if args.gcp and not args.gcp.exists():
        sys.exit(f"[erro] arquivo GCP não encontrado: {args.gcp}")

    if args.video:
        workdir = Path(tempfile.mkdtemp(prefix="structai_frames_"))
        images = extract_frames(args.video, workdir, args.every_n)
    else:
        if not args.images.is_dir():
            sys.exit(f"[erro] diretório não encontrado: {args.images}")
        images = sorted(p for p in args.images.iterdir()
                        if p.suffix.lower() in IMAGE_EXTS)
        print(f"[captura] {len(images)} imagens em {args.images}")

    images = filter_blurry(images, args.min_sharpness)
    if not images:
        sys.exit("[erro] nenhuma imagem utilizável.")

    assets = run_odm(images, args.gcp, args.node_url, args.fast)
    result = measure(find_mesh(assets))

    print("\n===== RESULTADO (medidas brutas da malha) =====")
    print(f"  Área de superfície : {result['surface_area_m2']:>12,.2f} m²")
    print(f"  Altura (extensão Z): {result['height_m']:>12,.2f} m")
    print(f"  Perímetro da base  : {result['footprint_perimeter_m']:>12,.2f} m")
    print(f"  Vértices da malha  : {result['vertices']:>12,}")
    if not args.gcp:
        print("  ** SEM GCP: valores em escala relativa, NÃO são metros. **")
    print("================================================")
    print("Próximo passo: compare com a medição manual (trena/laser) do mesmo prédio.")
    print("Erro aceitável definido com o comercial? Só então avance à Sessão 1.")


if __name__ == "__main__":
    main()
