# Vị trí hai camera

Camera biển số trên `s3_plate_ctrl` nhìn hai vị trí dừng IN/OUT. Camera mặt trên `s3_face_cam` nhìn khuôn mặt tài xế ở hai vị trí đó. Không có camera toàn cảnh để đếm xe trong ô; bốn IR cung cấp trạng thái vật lý của ô.

Đánh dấu rõ vị trí dừng để mỗi lượt có một xe, một biển và một mặt rõ. Chụp frame 640×480 thực tế tại mỗi vị trí; đo vùng biển và mặt, rồi cấu hình các biến `PLATE_ROI_IN`, `PLATE_ROI_OUT`, `FACE_ROI_IN`, `FACE_ROI_OUT` trên backend. Nếu bố trí không cho một camera nhìn rõ cả hai vị trí, cần sửa vị trí lắp hoặc phạm vi mô hình trước khi chốt ROI; không suy ra tọa độ từ Wokwi.

Backend nhận `ROI_IN`/`ROI_OUT` như nhãn của làn và crop theo tọa độ cấu hình. Không tái sử dụng ảnh lượt trước. Cần thử ngoài sáng, thiếu sáng, nghiêng đầu, biển bị lóa và hai cổng đến gần nhau. Chưa có số đo độ chính xác/FPS/độ trễ từ phần cứng trong lần bàn giao phần mềm này.
