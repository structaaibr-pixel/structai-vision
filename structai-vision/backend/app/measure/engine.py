"""StructAI Measure Engine — v0 (medidas brutas da malha).

Retorna área de SUPERFÍCIE total, altura e perímetro da base. A área LÍQUIDA
(descontando janelas/portas detectadas por YOLO/SAM2) entra nas Sessões 4-5.
"""
from pathlib import Path

import numpy as np


def measure_mesh(mesh_path: str | Path) -> dict:
    import trimesh
    from shapely.geometry import MultiPoint

    mesh = trimesh.load(str(mesh_path), force="mesh")
    v = np.asarray(mesh.vertices)
    if len(v) == 0:
        raise ValueError("malha vazia — reconstrução provavelmente falhou")

    xy = v[:, :2]
    if len(xy) > 200_000:
        xy = xy[np.random.default_rng(0).choice(len(xy), 200_000, replace=False)]
    hull = MultiPoint([tuple(p) for p in xy]).convex_hull

    return {
        "surface_area_m2": float(mesh.area),
        "height_m": float(v[:, 2].max() - v[:, 2].min()),
        "footprint_perimeter_m": float(hull.length),
        "vertices": int(len(mesh.vertices)),
        "faces": int(len(mesh.faces)),
    }
