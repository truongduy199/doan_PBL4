# InsightFace Models Directory

Thư mục chứa model pack InsightFace phục vụ suy luận offline trên CPU.
- Pack chính: `models/buffalo_l/` (SCRFD det, 2d106det, w600k_r50/glintr34 arcface recog)
- Addon: `addons/liveness.onnx` (nếu dùng kiểm tra độ sống khuôn mặt)

Sử dụng script `edge-server/scripts/download_insightface_models.py` để tải tự động.
Không commit các file .onnx / .zip vào git.