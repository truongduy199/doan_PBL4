"""Verify tracked model bytes against the locally observed SHA256 baseline.

This is an integrity check, not a model-accuracy or provenance certification.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[2]

def verify_hashes(require_face: bool = False) -> int:
    manifest = json.loads((ROOT / "contracts/models.sha256.json").read_text(encoding="utf-8-sig"))
    failures = 0
    for entry in manifest["models"]:
        path = ROOT / entry["path"]
        valid = path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]
        print(f"{'PASS' if valid else 'FAIL'} SHA256 {entry['path']}")
        failures += not valid
    weights = ROOT / "modules/license_plate_yolo_numpy/license_plate_yolo_numpy/weights"
    pt = weights / "best.pt"
    if pt.is_file():
        try:
            with zipfile.ZipFile(pt) as archive:
                if archive.testzip() is not None:
                    raise ValueError("bad ZIP entry CRC")
            print("PASS YOLO checkpoint archive CRC (inference not run)")
        except (zipfile.BadZipFile, ValueError):
            print("FAIL YOLO archive integrity")
            failures += 1
    try:
        import numpy as np
        file = weights / "ocr_coco_weights.npz"
        with np.load(file, allow_pickle=False) as arrays:
            expected = {"W1": (1393, 320), "b1": (1, 320), "W2": (320, 160), "b2": (1, 160), "W3": (160, 36), "b3": (1, 36)}
            if set(arrays.files) != set(expected) or not all(arrays[key].shape == shape and np.isfinite(arrays[key]).all() for key, shape in expected.items()):
                raise ValueError("unexpected shapes or nonfinite weights")
        source = weights.parent / "mlp_numpy.py"
        spec = importlib.util.spec_from_file_location("pbl4_ocr_integrity", source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        model = module.NumpyMLP()
        model.load_weights(str(file))
        output = model.forward(np.zeros((2, 784), dtype=np.float32))
        if output.shape != (2, 36) or not np.isfinite(output).all() or not np.allclose(output.sum(axis=1), 1):
            raise ValueError("invalid MLP output")
        print("PASS OCR NumPy real-weight forward: 2 inputs -> 36 classes (not an accuracy test)")
    except (ImportError, ValueError, OSError) as exc:
        print(f"FAIL OCR weight/forward check: {type(exc).__name__}")
        failures += 1
    face = ROOT / "edge-server/models/insightface"
    detector = (face / "models/buffalo_l/det_10g.onnx").is_file()
    recognition = (face / "models/buffalo_l/w600k_r50.onnx").is_file()
    liveness = (face / "addons/liveness.onnx").is_file()
    print(f"Face assets: detector={detector}, recognition={recognition}, liveness={liveness}; face inference not run")
    if require_face and not (detector and recognition and liveness):
        failures += 1
    print(f"Integrity issues: {failures}. Accuracy, liveness and real-camera performance need independent evaluation.")
    return int(failures > 0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-face", action="store_true")
    raise SystemExit(verify_hashes(parser.parse_args().require_face))
