# Nhận diện biển số xe cho bãi đỗ xe thông minh

Thư viện Python nhận ảnh xe hoặc khung hình từ camera, dùng YOLO để tìm biển số và OCR NumPy để đọc ký tự. Mỗi ảnh có thể trả về nhiều biển số. Vùng biển số được cắt trong bộ nhớ và chuyển thẳng sang OCR. Bộ giải mã có quy tắc hậu xử lý cho biển số Việt Nam.

## Cài đặt

Yêu cầu Python 3.10 trở lên. Từ thư mục chứa `pyproject.toml`, tạo môi trường ảo và cài gói. Trên Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install .
```

Trên Linux hoặc macOS, dùng `source .venv/bin/activate` để kích hoạt. Nếu PowerShell chặn lệnh kích hoạt, dùng `.\.venv\Scripts\python.exe -m pip install .` và gọi CLI qua `.\.venv\Scripts\license-plate-reader.exe`.

Sau khi repo được đẩy lên Git, nhóm tích hợp có thể cài trực tiếp vào môi trường Python của ứng dụng. Thay `CHU_TAI_KHOAN` bằng tên tài khoản hoặc tổ chức trên GitHub.

```bash
python -m pip install "git+https://github.com/CHU_TAI_KHOAN/license_plate_yolo_numpy.git"
```

Gói mang theo `best.pt` và `ocr_coco_weights.npz`. Các đường dẫn mặc định được xác định theo vị trí gói đã cài, nên có thể chạy từ thư mục khác.

## Chạy thử với ảnh

```bash
license-plate-reader --image samples/synthetic_plate.png --save results/annotated.png
license-plate-reader --image path/to/car.jpg --conf 0.25 --iou 0.45
```

Lần kiểm thử với `samples/synthetic_plate.png` phát hiện một biển số và đọc được `43A12345`. Đây là ảnh mô phỏng. Xem tất cả tùy chọn bằng `license-plate-reader --help`. Có thể thay trọng số qua `--yolo-weights` và `--ocr-weights`. Lệnh `python main.py --image ...` vẫn chạy từ thư mục repo.

## Tích hợp vào ứng dụng bãi đỗ xe

Khởi tạo `LicensePlateReader` một lần khi ứng dụng hoặc tiến trình xử lý camera khởi động. Hai mô hình sẽ được tái sử dụng qua nhiều lần gọi `predict()`.

```python
from dataclasses import asdict

import numpy as np

from license_plate_yolo_numpy import LicensePlateReader, read_image_bgr

reader = LicensePlateReader(conf=0.25, iou=0.45)


def recognize_frame(frame_bgr: np.ndarray) -> list[dict]:
    return [asdict(plate) for plate in reader.predict(frame_bgr)]


frame = read_image_bgr("path/to/car.jpg")
plates = recognize_frame(frame)
```

Với camera OpenCV, lấy `ok, frame = capture.read()` và gọi `recognize_frame(frame)` khi `ok` là `True`. `predict()` nhận `numpy.ndarray` không rỗng, kiểu `uint8`, kích thước `H × W × 3` và thứ tự kênh BGR. Truyền khung hình từ OpenCV trực tiếp. Nếu nguồn ảnh trả về RGB, chuyển sang BGR trước khi gọi.

Nếu nhiều luồng dùng chung một `reader`, hãy tuần tự hóa các lần gọi `predict()`. OCR lưu dữ liệu trung gian trên đối tượng mô hình trong quá trình suy luận.

### Kết quả trả về

`predict()` trả về `list[PlateResult]`. Một phần tử sau khi chuyển sang JSON có dạng dưới đây. Giá trị chỉ để minh họa.

```json
{
  "bbox": [102, 150, 325, 238],
  "confidence": 0.914,
  "ocr": {
    "raw_text": "43A12345",
    "text": "43A12345",
    "char_count": 8
  }
}
```

| Trường | Ý nghĩa |
| --- | --- |
| `bbox` | Tọa độ pixel `(x1, y1, x2, y2)` theo ảnh gốc. Có thể cắt bằng `frame[y1:y2, x1:x2]`. |
| `confidence` | Điểm tin cậy của YOLO cho vùng biển số. |
| `ocr.text` | Chuỗi ký tự sau hậu xử lý, ví dụ `43A12345`. |
| `ocr.raw_text` | Chuỗi ký tự trước hậu xử lý. |
| `ocr.char_count` | Số ký tự được tách từ vùng biển số. |

Danh sách rỗng `[]` nghĩa là YOLO không tìm thấy vùng biển số hợp lệ. Nếu có vùng biển số nhưng OCR không tách được ký tự, `ocr.text` là `""` và `ocr.char_count` là `0`. `predict()` báo `ValueError` nếu khung hình sai định dạng.

Phần mềm bãi đỗ xe dùng `ocr.text` để tra cứu vé hoặc phiên gửi xe. Khi chuỗi rỗng hoặc không đạt quy tắc kiểm tra biển số của hệ thống, có thể lấy thêm khung hình hoặc chuyển sang xác nhận thủ công trước khi ghi lượt vào/ra. API hiện chưa cung cấp điểm tin cậy cho chuỗi OCR.

## Kiểm thử và tạo gói phân phối

```bash
python -m pip install -e ".[test]"
python -m pytest -q
python -m pip install build
python -m build
```

Bản wheel và bản mã nguồn được tạo trong `dist/`. Cài wheel vào ứng dụng khác bằng lệnh sau nếu muốn phân phối qua tệp.

```bash
python -m pip install dist/license_plate_yolo_numpy-0.1.0-py3-none-any.whl
```

Các bài kiểm thử tự động dùng OCR thật và mô phỏng đầu ra YOLO để kiểm tra việc cắt ảnh, nhận nhiều biển số và chạy CLI. Xem [kết quả kiểm thử](TEST_RESULTS.md). Độ chính xác với camera thực tế cần được đo trên ảnh ở các góc chụp và điều kiện ánh sáng tại bãi xe.

## Đưa lên GitHub

Chạy các lệnh sau trong thư mục chứa `pyproject.toml` nếu dự án chưa được khởi tạo Git. Tạo repo trống và thay `CHU_TAI_KHOAN` bằng tài khoản hoặc tổ chức sở hữu repo.

```bash
git init -b main
git add .
git commit -m "Package license plate recognition for integration"
git remote add origin https://github.com/CHU_TAI_KHOAN/license_plate_yolo_numpy.git
git push -u origin main
```

### Giấy phép

Repo hiện chưa có tệp `LICENSE`. Trước khi công khai hoặc cấp quyền tái sử dụng, hãy xác nhận quyền phân phối mã nguồn và hai tệp trọng số. Xem điều khoản của Ultralytics cho cách tích hợp YOLO vào ứng dụng bãi đỗ xe. [Giấy phép Ultralytics](https://www.ultralytics.com/license)
