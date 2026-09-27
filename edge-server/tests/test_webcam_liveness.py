"""Kiem tra webcam demo khong tao embedding khi anti-spoof that bai."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import numpy as np

SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "test_webcam_insightface.py"
SPEC = importlib.util.spec_from_file_location("test_webcam_insightface", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
webcam = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(webcam)


class FakeAdapter:
    def __init__(self, face: object):
        self.app = SimpleNamespace(get=lambda _frame: [face])


def make_face(liveness: object) -> object:
    return SimpleNamespace(
        bbox=np.array([240, 140, 400, 340], dtype=np.float32),
        kps=np.array(
            [[280, 220], [360, 220], [320, 255], [290, 290], [350, 290]],
            dtype=np.float32,
        ),
        normed_embedding=np.ones(512, dtype=np.float32),
        liveness=liveness,
    )


def analyze(face: object):
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    return webcam.analyze_frame(frame, FakeAdapter(face), 80, 0.8)


def test_missing_liveness_fails_closed() -> None:
    _, embedding, status, score = analyze(make_face(None))

    assert embedding is None
    assert score is None
    assert "unavailable" in status


def test_phone_or_photo_classification_blocks_embedding() -> None:
    result = SimpleNamespace(status="ok", is_live=False, live_score=0.12)
    _, embedding, status, score = analyze(make_face(result))

    assert embedding is None
    assert score == 0.12
    assert status.startswith("SPOOF BLOCKED")


def test_input_rejection_fails_closed() -> None:
    result = SimpleNamespace(status="input_rejected", is_live=None, live_score=None)
    _, embedding, status, score = analyze(make_face(result))

    assert embedding is None
    assert score is None
    assert status.startswith("LOCKED")


def test_live_face_returns_embedding() -> None:
    result = SimpleNamespace(status="ok", is_live=True, live_score=0.93)
    _, embedding, status, score = analyze(make_face(result))

    assert embedding is not None
    assert embedding.shape == (512,)
    assert score == 0.93
    assert status.startswith("LIVE")


def test_score_below_local_threshold_fails_closed() -> None:
    # Bao ve ca khi addon bi khoi tao nham voi threshold thap hon app.
    result = SimpleNamespace(status="ok", is_live=True, live_score=0.79)
    _, embedding, status, score = analyze(make_face(result))

    assert embedding is None
    assert score == 0.79
    assert status.startswith("SPOOF BLOCKED")
