"""Kịch bản kiểm thử đồng bộ thời gian thực hai chiều giữa Edge Server, Firebase và Dashboard.

Cách chạy:
    python edge-server/scripts/test_realtime_sync.py
"""

import os
import sys
import time
from pathlib import Path

EDGE_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = EDGE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from smart_parking.infrastructure.firebase.firebase_client import FirebaseClient
from smart_parking.infrastructure.firebase.review_listener import ReviewListener

DATABASE_URL = os.environ.get(
    "FIREBASE_DATABASE_URL",
    "https://smart-parking-pbl4-default-rtdb.firebaseio.com"
)


def on_review_decision(request_id: str, status: str, data: dict):
    print("\n" + "=" * 60)
    if status == "APPROVED":
        print(f"🎉 [REALTIME THÀNH CÔNG] Nhận được quyết định CHẤP THUẬN từ Dashboard!")
        print(f"   - Mã yêu cầu: {request_id}")
        print(f"   - Biển số xe: {data.get('plate_number')}")
        print(f"   - Hành động Edge Server: Gửi lệnh Serial 'OPEN_GATE' xuống ESP32 để mở barie!")
    else:
        print(f"🚫 [REALTIME] Nhận được quyết định TỪ CHỐI từ Dashboard!")
        print(f"   - Mã yêu cầu: {request_id}")
        print(f"   - Hành động Edge Server: Barie giữ nguyên đóng.")
    print("=" * 60 + "\n")


def main():
    print("=" * 60)
    print("KHỞI ĐỘNG KIỂM THỬ ĐỒNG BỘ THỜI GIAN THỰC (REALTIME SYNC)")
    print(f"Target Database URL: {DATABASE_URL}")
    print("=" * 60)

    client = FirebaseClient(database_url=DATABASE_URL)
    listener = ReviewListener(database_url=DATABASE_URL, poll_interval=1.0)
    listener.start(on_decision=on_review_decision)

    try:
        # BƯỚC 1: Khởi tạo 4 ô đỗ
        print("\n[Bước 1] Khởi tạo trạng thái 4 ô đỗ trên Firebase...")
        client.sync_slot("A1", "OCCUPIED", current_plate="43A-123.45")
        client.sync_slot("A2", "FREE")
        client.sync_slot("B1", "FREE")
        client.sync_slot("B2", "FREE")
        print("  -> Đã cập nhật: A1 (CÓ XE), A2 (TRỐNG), B1 (TRỐNG), B2 (TRỐNG)")
        print("  -> Bạn hãy mở Dashboard quan sát: Ô A1 màu xanh, 3 ô còn lại màu xanh lá.")

        time.sleep(3)

        # BƯỚC 2: Xe tới cổng vào -> Gán ô B1
        print("\n[Bước 2] Xe 92B-678.90 tới cổng vào -> Edge Server cấp ô B1 (ASSIGNED)...")
        client.sync_slot("B1", "ASSIGNED", current_plate="92B-678.90")
        client.sync_session("SES-002", "92B-678.90", "B1", "ENTRY_PENDING")
        client.log_event("ENTRY", "Xe 92B-678.90 qua cổng vào", "Đã cấp ô đỗ B1. Xe đang di chuyển tới ô.")
        print("  -> Đã đồng bộ lên Firebase! Quan sát Dashboard: Ô B1 đổi sang màu VÀNG (ĐÃ GÁN).")

        time.sleep(4)

        # BƯỚC 3: Xe vào ô B1 an toàn -> Cập nhật OCCUPIED
        print("\n[Bước 3] Camera toàn cảnh xác nhận xe đã đỗ đúng ô B1...")
        client.sync_slot("B1", "OCCUPIED", current_plate="92B-678.90")
        client.sync_session("SES-002", "92B-678.90", "B1", "ACTIVE")
        client.log_event("SLOT", "Cập nhật ô B1: CÓ XE", "Xe đã đỗ an toàn vào ô B1.")
        print("  -> Đã đồng bộ lên Firebase! Quan sát Dashboard: Ô B1 chuyển sang màu XANH DƯƠNG (CÓ XE).")

        time.sleep(3)

        # BƯỚC 4: Xe ra cổng có ngoại lệ khuôn mặt -> Tạo review request
        print("\n[Bước 4] Xe 43A-123.45 ra cổng: Khuôn mặt có Cosine Score = 0.58 (Vùng bất định)...")
        print("  -> Edge Server tạo yêu cầu duyệt thủ công 'REQ-0920-01' trên Firebase...")
        client.create_review_request(
            request_id="REQ-0920-01",
            session_id="SES-001",
            plate_number="43A-123.45",
            reason_code="ERR_FACE_UNCERTAIN",
            similarity_score=0.58,
        )
        print("  -> Đã tạo yêu cầu! Hãy chuyển sang Web Dashboard:")
        print("     Bạn sẽ thấy hộp thoại duyệt ngoại lệ hiện lên kèm điểm 0.58.")
        print("     👉 Hãy bấm nút [✓ Chấp Thuận Mở Cổng] hoặc [✕ Từ Chối] trên Dashboard để xem kết quả phản hồi thời gian thực!")

        print("\n[ĐANG CHỜ TÍN HIỆU TỪ DASHBOARD...] (Nhấn Ctrl+C để dừng)")
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nĐã dừng chương trình kiểm thử.")
    finally:
        listener.stop()


if __name__ == "__main__":
    main()

