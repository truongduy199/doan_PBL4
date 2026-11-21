# Quy ước giao diện PBL4

Các route đang sử dụng: `/login`, `/user`, `/admin`. Cả ba dùng CSS trong `dashboard/src/theme.css` và thành phần chung ở `dashboard/src/shared/components/ui.tsx`.

| Thành phần | Quy ước |
| --- | --- |
| Font | Segoe UI / Arial có sẵn trên máy; không tải font ngoài |
| Nền | Xám ấm `#f5f6f3`, bề mặt trắng |
| Màu chính | Xanh trầm `#236b54`; dành cho hành động chính và trạng thái đang chọn |
| Chữ | Nội dung `#24322c`, chữ phụ `#69756e` |
| Viền / Bo góc | Viền mảnh `#dde3dd`, panel 8px, nút 6px |
| Trạng thái | Xanh: khả dụng/hoàn tất; vàng: đang giữ/chờ kiểm tra; xanh lam: đang gửi xe; đỏ: lỗi/cần kiểm tra |
| Dữ liệu chưa có | Hiện “Chưa có dữ liệu” hoặc dấu gạch; không tự suy ra trống, online hoặc thành công |
| Hành động | Một nút chính mỗi khối; chữ ngắn, dùng kiểu câu thông thường |
| Bảng | Cùng kiểu header nhạt, đường phân hàng, chữ 12px; cuộn ngang trên màn hình hẹp |
| Thông báo | Tách lỗi tải dữ liệu, kết quả thao tác và trạng thái thiết bị; không coi đã lưu quyết định là cổng đã mở |

Không dùng gradient trên màn hình nghiệp vụ, emoji làm biểu tượng hành động, tiêu đề viết hoa cả dòng, huy hiệu quảng cáo hay số benchmark mẫu. Trang User tập trung chọn ô, thời hạn giữ và lịch sử. Trang Admin tập trung xe, đặt chỗ, review, thiết bị và nhật ký. Camera/benchmark phụ chưa có dữ liệu không được hiển thị hình hoặc chỉ số giả.

Mô phỏng góc nhìn người lái giữ cảnh tối để đọc đường đi, nhưng dùng cùng font, độ bo góc và cách viết nhãn. Nó không gọi API điều khiển cổng hay sửa dữ liệu. Chỉ mở khi người dùng chọn “Xem đường”; không tự bật sau đặt chỗ.

Bố cục chính đổi từ hai cột thành một cột khi chiều rộng giảm. Nút có trạng thái disabled và focus bàn phím; hộp xác nhận có nhãn, Escape và giới hạn vòng Tab. Trạng thái màu luôn đi kèm chữ.

Bản CDN và bản Vite dùng cùng nguồn giao diện và cùng theme. `spa.py` chỉ ghép bản xem trước; bản Vite được ưu tiên khi có `dashboard/dist`.
