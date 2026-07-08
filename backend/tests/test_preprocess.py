"""Extração de frames de vídeo e filtro de nitidez (app/preprocess.py)."""
import cv2
import numpy as np
import pytest

from app.preprocess import extract_frames, filter_blurry, is_sharp, sharpness


def _write_video(path, n_frames=45, size=64):
    rng = np.random.default_rng(0)
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 30.0, (size, size))
    assert vw.isOpened(), "codec MJPG indisponível no OpenCV do ambiente"
    for _ in range(n_frames):
        vw.write(rng.integers(0, 256, (size, size, 3), dtype=np.uint8))
    vw.release()


def _flat_image(path):
    cv2.imwrite(str(path), np.full((64, 64), 127, dtype=np.uint8))
    return path


def _noisy_image(path):
    rng = np.random.default_rng(0)
    cv2.imwrite(str(path), rng.integers(0, 256, (64, 64), dtype=np.uint8))
    return path


def test_extract_frames_every_n(tmp_path):
    video = tmp_path / "fachada.avi"
    _write_video(video, n_frames=45)
    frames = extract_frames(video, tmp_path / "frames", every_n=15)
    assert len(frames) == 3  # frames 0, 15 e 30
    assert all(p.exists() and p.stat().st_size > 0 for p in frames)


def test_extract_frames_rejects_missing_file(tmp_path):
    with pytest.raises(RuntimeError):
        extract_frames(tmp_path / "nao_existe.mp4", tmp_path / "frames")


def test_sharpness_separates_flat_from_textured(tmp_path):
    flat = _flat_image(tmp_path / "flat.png")
    noisy = _noisy_image(tmp_path / "noisy.png")
    assert sharpness(flat) < 1.0
    assert not is_sharp(flat)
    assert is_sharp(noisy)


def test_filter_blurry(tmp_path):
    flat = _flat_image(tmp_path / "flat.png")
    noisy = _noisy_image(tmp_path / "noisy.png")
    kept, removed = filter_blurry([flat, noisy])
    assert kept == [noisy]
    assert removed == 1
