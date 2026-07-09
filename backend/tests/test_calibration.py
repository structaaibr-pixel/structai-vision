"""Lógica pura do harness de calibração (scripts/calibrate.py).

A reconstrução em si roda fora do CI (NodeODM + horas de CPU); aqui cobrimos
o que decide o veredito: resíduos de GCP, comparação com referência manual e
o registro de datasets.
"""
import math
import zipfile

import pytest

import calibrate


def _geojson(errors):
    return {"features": [
        {"properties": {"id": f"gcp{i}", "error_x": ex, "error_y": ey, "error_z": ez}}
        for i, (ex, ey, ez) in enumerate(errors)
    ]}


def test_gcp_errors_rms():
    stats = calibrate.gcp_errors_from_geojson(_geojson([(0.03, 0.04, 0.0),
                                                        (0.0, 0.0, 0.05)]))
    assert stats["count"] == 2
    # ambos os pontos têm erro 3D = 0.05 → RMS = 0.05
    assert stats["rms_3d_m"] == pytest.approx(0.05)
    assert stats["max_3d_m"] == pytest.approx(0.05)


def test_gcp_errors_ignores_features_without_error():
    geojson = {"features": [{"properties": {"id": "sem_erro"}}]}
    assert calibrate.gcp_errors_from_geojson(geojson) is None
    assert calibrate.gcp_errors_from_geojson({"features": []}) is None


def test_compare_with_truth():
    measured = {"surface_area_m2": 105.0, "height_m": 10.0,
                "footprint_perimeter_m": 40.0}
    truth = {"surface_area_m2": 100.0, "height_m": 10.2, "tolerance_pct": 5.0}
    rows = calibrate.compare_with_truth(measured, truth)
    by_metric = {r["metric"]: r for r in rows}
    assert set(by_metric) == {"surface_area_m2", "height_m"}  # só o que há no truth
    assert by_metric["surface_area_m2"]["error_pct"] == pytest.approx(5.0)
    assert by_metric["surface_area_m2"]["ok"] is True  # no limite ainda passa
    assert by_metric["height_m"]["ok"] is True


def test_evaluate_approves_within_limits():
    stats = calibrate.gcp_errors_from_geojson(_geojson([(0.01, 0.01, 0.01)]))
    ok, problems = calibrate.evaluate(stats, [], max_rms_m=0.05)
    assert ok and problems == []


def test_evaluate_fails_on_high_rms():
    stats = calibrate.gcp_errors_from_geojson(_geojson([(0.2, 0.2, 0.2)]))
    ok, problems = calibrate.evaluate(stats, [], max_rms_m=0.05)
    assert not ok
    assert "RMS 3D" in problems[0]


def test_evaluate_fails_without_gcp_residuals():
    ok, problems = calibrate.evaluate(None, [], max_rms_m=0.05)
    assert not ok
    assert "escala métrica" in problems[0]


def test_evaluate_fails_on_truth_out_of_tolerance():
    rows = calibrate.compare_with_truth(
        {"surface_area_m2": 120.0, "height_m": 10.0, "footprint_perimeter_m": 1.0},
        {"surface_area_m2": 100.0, "tolerance_pct": 5.0})
    stats = calibrate.gcp_errors_from_geojson(_geojson([(0.01, 0.0, 0.0)]))
    ok, problems = calibrate.evaluate(stats, rows, max_rms_m=0.05)
    assert not ok
    assert any("surface_area_m2" in p for p in problems)


def test_registry_entries_are_complete():
    datasets = calibrate.load_registry()
    assert len(datasets) >= 2
    for d in datasets:
        assert d["type"] == "public"
        assert d["url"].startswith("https://")
        for field in ("name", "description", "license", "source", "notes"):
            assert d.get(field), f"campo {field} vazio no dataset {d.get('name')}"


def test_download_dataset_extracts_and_locates(tmp_path):
    # zip sintético servido via file:// — valida extração + descoberta de inputs
    src = tmp_path / "src" / "images"
    src.mkdir(parents=True)
    for i in range(3):
        (src / f"f{i}.jpg").write_bytes(b"fake")
    (src.parent / "gcp_list.txt").write_text("EPSG:31983\n")
    # thumbnail solto na raiz (como o copr.png do dataset copr): NÃO pode
    # entrar na lista de fotos da reconstrução
    (src.parent / "thumbnail.png").write_bytes(b"fake")
    zip_path = tmp_path / "ds.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for p in (tmp_path / "src").rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(tmp_path))

    entry = {"name": "fake_ds", "url": zip_path.as_uri(), "license": "teste"}
    root = calibrate.download_dataset(entry, tmp_path / "cache")
    images, gcp = calibrate.locate_inputs(root)
    assert len(images) == 3
    assert all(p.parent.name == "images" for p in images)
    assert gcp is not None and gcp.name == "gcp_list.txt"


def test_rms_math_reference():
    # sanidade: RMS de erros distintos (0.03 e 0.06)
    stats = calibrate.gcp_errors_from_geojson(_geojson([(0.03, 0.0, 0.0),
                                                        (0.0, 0.06, 0.0)]))
    expected = math.sqrt((0.03 ** 2 + 0.06 ** 2) / 2)
    assert stats["rms_3d_m"] == pytest.approx(expected)
