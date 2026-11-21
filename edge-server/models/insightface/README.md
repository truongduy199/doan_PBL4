# Model khuôn mặt InsightFace

Thư mục triển khai là `edge-server/models/insightface`:

- `models/buffalo_l/det_10g.onnx`: detector SCRFD.
- `models/buffalo_l/w600k_r50.onnx`: nhận dạng ArcFace.
- `addons/liveness.onnx`: model liveness tương thích với đúng bản thư viện/addon của Nam.

Các tệp ONNX chưa có trong repo hiện tại. `scripts/download_insightface_models.py` hiện chỉ là placeholder, không tải model thực tế. Không coi việc chạy script đó là đã cài được model. Nạp các tài nguyên đã được Nam bàn giao và kiểm tra bằng `python edge-server/scripts/verify_model_hashes.py --require-face` từ gốc repo.

Việc có file không chứng minh addon đang suy luận đúng. Cần kiểm tra với khuôn mặt thật, ảnh giả mạo và phiên bản/config tương thích. Model không được tự giả lập Passed khi thiếu dữ liệu. Không commit ảnh mặt, embedding thật hoặc trọng số lớn vào Git.
