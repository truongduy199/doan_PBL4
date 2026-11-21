"""Quy tắc hậu xử lý ký tự lấy từ main(1).py (giữ nguyên thuật toán)."""

import cv2
import numpy as np
from .mlp_numpy import CHARS, IDX_TO_CHAR


def analyze_holes_and_walls(char_img):
    """
    Phân tích cấu trúc lỗ rỗng (Topology) và mật độ lõi trung tâm trên ảnh 28x28.
    Chống nhiễu họa tiết sóng chìm trên nền biển số.
    """
    # Không dùng MORPH_CLOSE quá mạnh để tránh nối liền 2 vách của số 0 hẹp ngang
    contours, hierarchy = cv2.findContours(char_img, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)

    hole_centers_y = []
    hole_areas = []
    if hierarchy is not None:
        for i, cnt in enumerate(contours):
            if hierarchy[0][i][3] != -1:  # Contour con (Lỗ rỗng khép kín)
                area = cv2.contourArea(cnt)
                x, y, w, h = cv2.boundingRect(cnt)
                # Lọc bỏ các lỗ nhiễu li ti (< 5px) do vân sóng chìm trên mặt biển số
                if area >= 5.0 and w >= 2 and h >= 3:
                    hole_centers_y.append(y + h / 2.0)
                    hole_areas.append(area)

    # Kiểm tra đúng LÕI TRUNG TÂM (cột 11..17, hàng 12..16) để không chạm vào 2 vách dọc dày của số 0
    center_core = np.mean(char_img[12:16, 11:17] > 0)   # Số 0: ~0.0 | Số 8, 6, 9, 5: > 0.45
    upper_right = np.mean(char_img[7:13, 17:23] > 0)    # Vách phải nửa trên
    lower_left = np.mean(char_img[15:21, 5:11] > 0)     # Vách trái nửa dưới
    lower_right = np.mean(char_img[15:21, 17:23] > 0)   # Vách phải nửa dưới

    return hole_centers_y, hole_areas, center_core, upper_right, lower_left, lower_right

def refine_digit_by_topology(char_img, pred_digit, digit_probs):
    """
    Phân biệt chính xác nhóm chữ số có vòng cong {0, 5, 6, 8, 9}.
    """
    if pred_digit not in {'0', '5', '6', '8', '9'}:
        return pred_digit

    hole_cy, hole_areas, center_core, upper_right, lower_left, lower_right = analyze_holes_and_walls(char_img)
    num_holes = len(hole_cy)

    # QUY TẮC 1 (Ưu tiên số 0): Nếu lõi trung tâm hoàn toàn rỗng (không có thanh ngang cắt qua giữa bụng)
    # và cả vách phải trên lẫn vách trái dưới đều kín -> Chắc chắn là số 0 (không thể là 8, 6, 9, 5)!
    if center_core < 0.22 and upper_right > 0.30 and lower_left > 0.30:
        return '0'

    # QUY TẮC 2: Có 2 lỗ rỗng thực sự rõ ràng (1 trên, 1 dưới) VÀ có thanh ngang ở tâm -> Số 8
    if num_holes >= 2 and center_core >= 0.35:
        if min(hole_cy) < 13.5 and max(hole_cy) > 14.5:
            return '8'

    # QUY TẮC 3: Có đúng 1 lỗ rỗng
    if num_holes == 1:
        cy = hole_cy[0]
        # Nếu lỗ rỗng nằm ở vùng trung tâm (11.0 <= cy <= 17.0) và lõi tâm rỗng -> Số 0
        if 11.0 <= cy <= 17.0 and center_core < 0.35:
            return '0'
        # Lỗ rỗng nằm lệch hẳn xuống nửa dưới -> Số 6
        if cy > 14.2:
            if upper_right > 0.45 and center_core > 0.50 and digit_probs[8] > digit_probs[6]:
                return '8'
            return '6'
        # Lỗ rỗng nằm lệch hẳn lên nửa trên -> Số 9
        if cy < 13.8:
            if lower_left > 0.45 and center_core > 0.50 and digit_probs[8] > digit_probs[9]:
                return '8'
            return '9'

    # QUY TẮC 4: Nếu MLP đang phân vân giữa 0 và 8, dùng mật độ lõi tâm (center_core) để quyết định
    if pred_digit in {'0', '8'}:
        return '8' if center_core >= 0.40 else '0'

    # QUY TẮC 5: Trường hợp bị hở lỗ rỗng (num_holes == 0)
    if num_holes == 0 and center_core >= 0.25 and lower_right >= 0.22:
        if upper_right < 0.20 and lower_left >= 0.25:
            return '6'
        if lower_left < 0.20 and upper_right >= 0.25:
            return '9'
        if upper_right < 0.20 and lower_left < 0.20:
            return '5'

    return pred_digit

def decode_plate_characters(char_items, probs):
    n = len(char_items)
    banned_vn_letters = {'I', 'O', 'Q'}
    raw_chars = []
    final_chars = []

    for i, ((char_img, (x, y, w, h)), p) in enumerate(zip(char_items, probs)):
        raw_top_idx = int(np.argmax(p))
        raw_ch = IDX_TO_CHAR[raw_top_idx]
        raw_chars.append(raw_ch)

        # Vị trí thứ 3 (i == 2) bắt buộc là CHỮ CÁI
        is_letter_pos = (n >= 7 and i == 2)

        if is_letter_pos:
            letter_probs = p[10:].copy()
            letter_probs[CHARS.index('S') - 10] += p[5] * 0.8
            letter_probs[CHARS.index('B') - 10] += p[8] * 0.8
            letter_probs[CHARS.index('G') - 10] += p[6] * 0.8
            letter_probs[CHARS.index('D') - 10] += p[0] * 0.8
            letter_probs[CHARS.index('Z') - 10] += p[2] * 0.8
            for b_ch in banned_vn_letters:
                letter_probs[CHARS.index(b_ch) - 10] = 0.0
            best_letter_idx = 10 + int(np.argmax(letter_probs))
            final_chars.append(IDX_TO_CHAR[best_letter_idx])

        # Vị trí thứ 4 trên biển 9 ký tự (i == 3): Cho phép cả Chữ và Số (VD: 38P1 hoặc 29SH)
        elif n == 9 and i == 3:
            adj_p = p.copy()
            adj_p[0] += adj_p[CHARS.index('O')] + adj_p[CHARS.index('Q')]
            adj_p[1] += adj_p[CHARS.index('I')]
            for b_ch in banned_vn_letters:
                adj_p[CHARS.index(b_ch)] = 0.0
            final_chars.append(IDX_TO_CHAR[int(np.argmax(adj_p))])

        # Các vị trí CHỮ SỐ còn lại: Tôn trọng hoàn toàn xác suất chữ số của MLP
        else:
            digit_probs = p[:10].copy()
            digit_probs[0] += p[CHARS.index('O')] + p[CHARS.index('D')] + p[CHARS.index('Q')]
            digit_probs[1] += p[CHARS.index('I')]
            best_digit = str(int(np.argmax(digit_probs)))
            final_chars.append(best_digit)

    return "".join(raw_chars), "".join(final_chars)

