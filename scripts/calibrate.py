#!/usr/bin/env python3
"""
StructAI Vision — Calibração de medição (Gate 0-A: datasets públicos).

Decisão de projeto (jul/2026, ver docs/calibracao.md): para não travar o
desenvolvimento, o pipeline é calibrado primeiro com datasets públicos
confiáveis que incluem GCPs topográficos medidos em campo por terceiros
(registro em calibration_datasets.json). A validação com prédios reais +
trena/laser (Gate 0-B) continua obrigatória antes de usar os números
comercialmente — e os dados adquiridos no canteiro entram neste MESMO
harness via --images/--gcp/--truth, alimentando a melhoria contínua.

Uso:
  # suba o NodeODM antes:  docker run -d -p 3000:3000 opendronemap/nodeodm
  python calibrate.py --list
  python calibrate.py --dataset copr            # baixa, reconstrói, avalia
  python calibrate.py --dataset copr --fast     # smoke test (qualidade média)

  # dados próprios de campo (canteiro), com medidas manuais de referência:
  python calibrate.py --name predio_alfa --images ./fotos --gcp ./gcp_list.txt \
      --truth ./truth_predio_alfa.json

Formato do truth.json (referência manual, trena/laser — use o que tiver):
  {"height_m": 12.5, "surface_area_m2": 480.0, "footprint_perimeter_m": 46.0,
   "tolerance_pct": 5.0}

Critérios de aprovação (ajustáveis por flag):
  - RMS 3D dos resíduos de GCP ≤ --max-rms (padrão 0.05 m) — mede se a escala
    métrica do modelo bate com os pontos de controle topográficos;
  - cada medida presente no truth.json com erro ≤ tolerance_pct.

O relatório completo sai em docs/calibracao/relatorios/{nome}_{data}.json.
"""
import argparse
import json
import math
import shutil
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_measurement import (  # noqa: E402
    DEFAULT_SHARPNESS, IMAGE_EXTS, filter_blurry, find_mesh, measure, run_odm,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = Path(__file__).resolve().with_name("calibration_datasets.json")
REPORTS_DIR = REPO_ROOT / "docs" / "calibracao" / "relatorios"
DEFAULT_CACHE = Path.home() / ".cache" / "structai" / "calibracao"
DEFAULT_MAX_RMS_M = 0.05
TRUTH_METRICS = ("surface_area_m2", "height_m", "footprint_perimeter_m")


# ------------------------------------------------------------- lógica pura
# (testada em backend/tests/test_calibration.py — sem ODM, sem rede)

def load_registry(path: Path = REGISTRY_PATH) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data["datasets"]


def gcp_errors_from_geojson(geojson: dict) -> dict | None:
    """Resíduos de GCP do ODM (ground_control_points.geojson) → estatísticas.

    Cada feature traz error_x/error_y/error_z em metros: a diferença entre a
    coordenada topográfica medida em campo e a posição reconstruída. O RMS 3D
    é a métrica padrão de acurácia fotogramétrica.
    """
    points = []
    for feat in geojson.get("features", []):
        p = feat.get("properties", {})
        if not all(k in p for k in ("error_x", "error_y", "error_z")):
            continue
        e3d = math.sqrt(p["error_x"] ** 2 + p["error_y"] ** 2 + p["error_z"] ** 2)
        points.append({
            "id": p.get("id") or p.get("name"),
            "error_x_m": p["error_x"], "error_y_m": p["error_y"],
            "error_z_m": p["error_z"], "error_3d_m": e3d,
        })
    if not points:
        return None
    rms = math.sqrt(sum(pt["error_3d_m"] ** 2 for pt in points) / len(points))
    return {
        "count": len(points),
        "rms_3d_m": rms,
        "max_3d_m": max(pt["error_3d_m"] for pt in points),
        "points": points,
    }


def compare_with_truth(measured: dict, truth: dict) -> list[dict]:
    """Compara as medidas do pipeline com a referência manual (trena/laser)."""
    tolerance = float(truth.get("tolerance_pct", 5.0))
    rows = []
    for metric in TRUTH_METRICS:
        if metric not in truth:
            continue
        expected = float(truth[metric])
        got = float(measured[metric])
        error_pct = abs(got - expected) / expected * 100.0
        rows.append({
            "metric": metric, "expected": expected, "measured": got,
            "error_pct": error_pct, "tolerance_pct": tolerance,
            "ok": error_pct <= tolerance,
        })
    return rows


def evaluate(gcp_stats: dict | None, truth_rows: list[dict],
             max_rms_m: float = DEFAULT_MAX_RMS_M) -> tuple[bool, list[str]]:
    """Veredito APROVADO/REPROVADO + lista de problemas legíveis (pt-BR)."""
    problems = []
    if gcp_stats is None:
        problems.append(
            "sem resíduos de GCP no resultado — o ODM não gerou "
            "ground_control_points.geojson (GCP recusado ou não associado às "
            "imagens). Sem isso não há garantia de escala métrica.")
    elif gcp_stats["rms_3d_m"] > max_rms_m:
        problems.append(
            f"RMS 3D dos GCPs = {gcp_stats['rms_3d_m']:.3f} m, acima do limite "
            f"de {max_rms_m:.3f} m — escala/georreferenciamento fora do aceitável.")
    for row in truth_rows:
        if not row["ok"]:
            problems.append(
                f"{row['metric']}: medido {row['measured']:.2f} vs referência "
                f"{row['expected']:.2f} (erro {row['error_pct']:.1f}% > "
                f"tolerância {row['tolerance_pct']:.1f}%).")
    return (not problems, problems)


# ------------------------------------------------------------------- I/O

def _download(url: str, dest: Path) -> None:
    req = urllib.request.Request(
        url, headers={"User-Agent": "structai-vision-calibration"})
    with urllib.request.urlopen(req) as resp, open(dest, "wb") as out:  # noqa: S310
        shutil.copyfileobj(resp, out)


def download_dataset(entry: dict, cache_dir: Path) -> Path:
    target = cache_dir / entry["name"]
    if target.exists() and any(target.iterdir()):
        print(f"[cache] usando download anterior em {target}")
        return target
    target.mkdir(parents=True, exist_ok=True)
    zip_path = cache_dir / f"{entry['name']}.zip"
    print(f"[download] {entry['url']}\n           licença: {entry['license']}")
    try:
        _download(entry["url"], zip_path)
    except Exception as exc:
        shutil.rmtree(target, ignore_errors=True)
        sys.exit(f"[erro] download falhou ({exc}) — confira a rede e se a URL "
                 f"abre no navegador: {entry['url']}")
    print(f"[download] extraindo {zip_path.name}…")
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(target)
    zip_path.unlink()
    return target


def locate_inputs(root: Path) -> tuple[list[Path], Path | None]:
    """Encontra as fotos e o gcp_list.txt em qualquer nível do dataset.

    Usa apenas o diretório com MAIS imagens: repositórios de dataset costumam
    ter thumbnails/ortofotos soltos na raiz (ex.: copr.png) que contaminariam
    a reconstrução se entrassem junto.
    """
    by_dir: dict[Path, list[Path]] = {}
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
            by_dir.setdefault(p.parent, []).append(p)
    images = sorted(max(by_dir.values(), key=len)) if by_dir else []
    gcp = next(iter(root.rglob("gcp_list.txt")), None)
    return images, gcp


def find_gcp_geojson(assets: Path) -> dict | None:
    for p in (assets / "odm_georeferencing" / "ground_control_points.geojson",
              *assets.rglob("ground_control_points.geojson")):
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    return None


def write_report(report: dict) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = REPORTS_DIR / f"{report['name']}_{stamp}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                    encoding="utf-8")
    return path


# ------------------------------------------------------------------- main

def run_calibration(name: str, images: list[Path], gcp: Path | None,
                    truth: dict | None, node_url: str, fast: bool,
                    max_rms_m: float, meta: dict | None = None) -> bool:
    if gcp is None:
        print("[AVISO] sem GCP → sem escala métrica: a calibração perde o sentido. "
              "Prosseguindo apenas para smoke test do pipeline.")
    kept = filter_blurry(images, threshold=DEFAULT_SHARPNESS)
    if not kept:
        sys.exit("[erro] nenhuma imagem nítida utilizável.")

    assets = run_odm(kept, gcp, node_url, fast)
    measured = measure(find_mesh(assets))
    gcp_stats = find_gcp_geojson(assets)
    gcp_stats = gcp_errors_from_geojson(gcp_stats) if gcp_stats else None
    truth_rows = compare_with_truth(measured, truth) if truth else []
    approved, problems = evaluate(gcp_stats, truth_rows, max_rms_m)

    report = {
        "name": name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": meta or {"type": "field"},
        "odm_quality": "medium" if fast else "high",
        "images_used": len(kept),
        "images_discarded": len(images) - len(kept),
        "measures": measured,
        "gcp_residuals": gcp_stats,
        "truth_comparison": truth_rows,
        "max_rms_m": max_rms_m,
        "approved": approved,
        "problems": problems,
    }
    path = write_report(report)

    print("\n===== CALIBRAÇÃO =====")
    if gcp_stats:
        print(f"  GCPs avaliados     : {gcp_stats['count']}")
        print(f"  RMS 3D             : {gcp_stats['rms_3d_m']:.3f} m "
              f"(limite {max_rms_m:.3f} m)")
        print(f"  Pior ponto         : {gcp_stats['max_3d_m']:.3f} m")
    for row in truth_rows:
        status = "ok" if row["ok"] else "FORA DA TOLERÂNCIA"
        print(f"  {row['metric']:<22}: {row['measured']:.2f} vs "
              f"{row['expected']:.2f} (erro {row['error_pct']:.1f}%) — {status}")
    print(f"  Veredito           : {'APROVADO ✅' if approved else 'REPROVADO ❌'}")
    for p in problems:
        print(f"    - {p}")
    print(f"  Relatório          : {path}")
    print("======================")
    if fast:
        print("[nota] rodado com --fast (qualidade média): use SEM --fast para o "
              "relatório oficial de calibração.")
    return approved


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true",
                    help="lista os datasets do registro e sai")
    ap.add_argument("--dataset", help="nome de um dataset público do registro")
    ap.add_argument("--name", help="nome de uma calibração com dados próprios")
    ap.add_argument("--images", type=Path, help="diretório de fotos (dados próprios)")
    ap.add_argument("--gcp", type=Path, help="gcp_list.txt (dados próprios)")
    ap.add_argument("--truth", type=Path,
                    help="truth.json com medidas manuais de referência")
    ap.add_argument("--node-url", default="http://localhost:3000")
    ap.add_argument("--cache", type=Path, default=DEFAULT_CACHE,
                    help="diretório de cache dos downloads (default: %(default)s)")
    ap.add_argument("--max-rms", type=float, default=DEFAULT_MAX_RMS_M,
                    help="limite do RMS 3D dos GCPs em metros (default: %(default)s)")
    ap.add_argument("--fast", action="store_true",
                    help="qualidade média — só para smoke test")
    args = ap.parse_args()

    registry = load_registry()

    if args.list:
        for d in registry:
            print(f"  {d['name']:<12} {d['description']}")
            print(f"  {'':<12} licença: {d['license']} — {d['notes']}")
        return

    truth = json.loads(args.truth.read_text(encoding="utf-8")) if args.truth else None

    if args.dataset:
        entry = next((d for d in registry if d["name"] == args.dataset), None)
        if entry is None:
            sys.exit(f"[erro] dataset '{args.dataset}' não está no registro "
                     f"(use --list). Disponíveis: {[d['name'] for d in registry]}")
        root = download_dataset(entry, args.cache)
        images, gcp = locate_inputs(root)
        if not images:
            sys.exit(f"[erro] nenhuma imagem encontrada em {root}")
        print(f"[dataset] {len(images)} imagens, GCP: {'sim' if gcp else 'NÃO'}")
        ok = run_calibration(entry["name"], images, gcp, truth, args.node_url,
                             args.fast, args.max_rms, meta=entry)
    elif args.images:
        if not args.images.is_dir():
            sys.exit(f"[erro] diretório não encontrado: {args.images}")
        images = sorted(p for p in args.images.iterdir()
                        if p.suffix.lower() in IMAGE_EXTS)
        name = args.name or args.images.name
        ok = run_calibration(name, images, args.gcp, truth, args.node_url,
                             args.fast, args.max_rms)
    else:
        ap.error("use --list, --dataset NOME ou --images DIR (dados próprios)")

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
