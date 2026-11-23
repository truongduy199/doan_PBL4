"""Kiểm thử không yêu cầu ultralytics (dùng bộ phát hiện giả lập)."""
import sys
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

from license_plate_yolo_numpy import LicensePlateReader, OCRResult, read_image_bgr, save_annotated
from license_plate_yolo_numpy.ocr_numpy import NumpyPlateOCR
from license_plate_yolo_numpy.pipeline import DEFAULT_OCR_WEIGHTS, DEFAULT_YOLO_WEIGHTS


ROOT = Path(__file__).resolve().parents[1]


class TensorMock:
    def __init__(self, value):
        self._value = np.asarray(value, dtype=float)

    def __getitem__(self, index):
        return TensorMock(self._value[index])

    def cpu(self):
        return self

    def numpy(self):
        return self._value

    def item(self):
        return float(self._value)


class BoxMock:
    def __init__(self, xyxy, conf=0.9):
        self.xyxy = TensorMock([xyxy])
        self.conf = TensorMock([conf])


class DetectorMock:
    def __init__(self, boxes):
        self.boxes = boxes
        self.predict_calls = 0

    def predict(self, source, conf, iou, verbose):
        assert isinstance(source, np.ndarray) and source.shape[2] == 3
        self.predict_calls += 1
        return [SimpleNamespace(boxes=self.boxes)]


class OCRSpy:
    def __init__(self):
        self.images = []

    def recognize_bgr(self, plate_bgr):
        self.images.append(plate_bgr.copy())
        return OCRResult(raw_text="ABC", text="43A12345", char_count=8)


def test_explicit_detector_size_keeps_crop_in_original_image_coordinates():
    class Detector:
        def predict(self, source, conf, iou, verbose, imgsz):
            assert imgsz == 1280
            return [SimpleNamespace(boxes=[BoxMock([40, 30, 100, 80])])]
    frame = np.zeros((120, 160, 3), dtype=np.uint8)
    frame[30:80, 40:100] = (10, 20, 30)
    ocr = OCRSpy()
    result = LicensePlateReader(detector=Detector(), ocr=ocr, detector_imgsz=1280).predict(frame)
    assert result[0].bbox == (40, 30, 100, 80)
    assert np.array_equal(ocr.images[0], frame[30:80, 40:100])


def test_crop_bgr_clip_multiple_and_order():
    img = np.zeros((90, 140, 3), dtype=np.uint8)
    img[10:30, 4:54] = (5, 10, 200)  # BGR khác RGB để bắt lỗi đổi màu
    img[40:75, 65:130] = (200, 10, 5)
    detector = DetectorMock([BoxMock([65, 40, 150, 90], 0.7), BoxMock([4, 10, 54, 30], 0.8)])
    ocr = OCRSpy()
    reader = LicensePlateReader(detector=detector, ocr=ocr)
    plates = reader.predict(img)
    assert [p.bbox for p in plates] == [(4, 10, 54, 30), (65, 40, 140, 90)]
    assert [p.ocr.text for p in plates] == ["43A12345", "43A12345"]
    assert ocr.images[0][0, 0].tolist() == [5, 10, 200]
    assert ocr.images[1][0, 0].tolist() == [200, 10, 5]
    assert np.array_equal(ocr.images[0], img[10:30, 4:54])
    assert detector.predict_calls == 1
    assert reader.ocr is ocr
    assert reader.detector is detector


def test_invalid_boxes_and_no_detection():
    img = np.zeros((50, 50, 3), dtype=np.uint8)
    detector = DetectorMock([BoxMock([60, 60, 70, 70]), BoxMock([20, 20, 20, 30])])
    assert LicensePlateReader(detector=detector, ocr=OCRSpy()).predict(img) == []
    assert LicensePlateReader(detector=DetectorMock([]), ocr=OCRSpy()).predict(img) == []


def test_real_ocr_weights_on_synthetic_bgr_image():
    ocr = NumpyPlateOCR(DEFAULT_OCR_WEIGHTS)
    full_bgr = read_image_bgr(ROOT / "samples/synthetic_plate.png")
    assert full_bgr.dtype == np.uint8 and full_bgr.shape[2] == 3
    plate_crop_bgr = full_bgr[48:171, 35:395].copy()
    result = ocr.recognize_bgr(plate_crop_bgr)
    assert isinstance(result, OCRResult)
    assert isinstance(result.text, str)
    assert len(result.text) == result.char_count
    assert len(result.raw_text) == result.char_count
    assert result.char_count > 0


def test_full_pipeline_with_real_ocr_and_fake_detector(tmp_path):
    image = read_image_bgr(ROOT / "samples/synthetic_plate.png")
    model = NumpyPlateOCR(DEFAULT_OCR_WEIGHTS)
    detector = DetectorMock([BoxMock([35, 48, 395, 171], 0.95)])
    reader = LicensePlateReader(detector=detector, ocr=model)
    results = reader.predict(image)
    assert len(results) == 1 and results[0].ocr.char_count > 0
    assert results[0].bbox == (35, 48, 395, 171)
    result_path = tmp_path / "kết_quả.png"
    save_annotated(image, results, result_path)
    assert cv2.imdecode(np.fromfile(str(result_path), np.uint8), cv2.IMREAD_COLOR) is not None


def test_main_cli_with_mocked_yolo_and_real_weights(monkeypatch, capsys, tmp_path):
    """Dùng CLI của gói với trọng số OCR thật và YOLO giả lập."""
    from types import ModuleType

    from license_plate_yolo_numpy import cli
    from license_plate_yolo_numpy.mlp_numpy import NumpyMLP

    load_stats = {"yolo": 0, "ocr": 0}
    real_load = NumpyMLP.load_weights

    def track_load(self, path):
        load_stats["ocr"] += 1
        return real_load(self, path)

    monkeypatch.setattr(NumpyMLP, "load_weights", track_load)

    class FakeYOLO:
        def __init__(self, path):
            assert Path(path) == DEFAULT_YOLO_WEIGHTS
            assert Path(path).is_file()
            load_stats["yolo"] += 1

        def predict(self, source, conf, iou, verbose):
            assert source.shape == (220, 430, 3)
            return [SimpleNamespace(boxes=[
                BoxMock([35, 48, 395, 171], 0.91),
                BoxMock([35, 48, 395, 171], 0.85),
            ])]

    fake_ultralytics = ModuleType("ultralytics")
    fake_ultralytics.YOLO = FakeYOLO
    monkeypatch.setitem(sys.modules, "ultralytics", fake_ultralytics)

    output = tmp_path / "annotated.png"
    code = cli.main([
        "--image", str(ROOT / "samples/synthetic_plate.png"),
        "--save", str(output),
    ])
    log = capsys.readouterr().out
    assert code == 0
    assert "Số biển số phát hiện: 2" in log
    assert log.count("Bounding box (x1,y1,x2,y2): (35, 48, 395, 171)") == 2
    assert log.count("OCR: 43A12345") == 2
    assert load_stats == {"yolo": 1, "ocr": 1}
    assert output.is_file()
