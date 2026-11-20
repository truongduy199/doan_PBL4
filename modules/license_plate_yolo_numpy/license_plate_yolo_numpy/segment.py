import cv2
import numpy as np

def pad_and_resize(char_img, target_size=28):
    """
    Chuẩn hóa kích thước 20x20 đặt vào tâm khung 28x28.
    """
    coords = cv2.findNonZero(char_img)
    if coords is not None:
        x, y, w, h = cv2.boundingRect(coords)
        char_img = char_img[y:y + h, x:x + w]

    h, w = char_img.shape
    if h == 0 or w == 0:
        return np.zeros((target_size, target_size), dtype=np.uint8)

    inner_size = 20
    scale = inner_size / float(max(h, w))
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))

    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
    resized_char = cv2.resize(char_img, (new_w, new_h), interpolation=interp)

    canvas = np.zeros((target_size, target_size), dtype=np.uint8)
    y_offset = (target_size - new_h) // 2
    x_offset = (target_size - new_w) // 2
    canvas[y_offset:y_offset + new_h, x_offset:x_offset + new_w] = resized_char

    _, canvas = cv2.threshold(canvas, 85, 255, cv2.THRESH_BINARY)

    kernel = np.ones((2, 2), np.uint8)
    canvas = cv2.morphologyEx(canvas, cv2.MORPH_CLOSE, kernel, iterations=1)
    return canvas

def filter_main_character_cluster(boxes):
    """
    Gom cụm các ký tự thuộc cùng một biển số (hỗ trợ cả biển thật và biển in mô hình có 2 dòng cách xa nhau).
    """
    n = len(boxes)
    if n <= 1:
        return boxes

    adj = {i: [] for i in range(n)}
    for i in range(n):
        x1, y1, w1, h1 = boxes[i]
        cx1, cy1 = x1 + w1 / 2.0, y1 + h1 / 2.0
        for j in range(i + 1, n):
            x2, y2, w2, h2 = boxes[j]
            cx2, cy2 = x2 + w2 / 2.0, y2 + h2 / 2.0

            h_ratio = min(h1, h2) / float(max(h1, h2))
            max_h = max(h1, h2)
            dx = abs(cx1 - cx2)
            dy = abs(cy1 - cy2)

            # Nới rộng dy <= 3.0 * max_h và h_ratio >= 0.60 để nối dòng trên (36A) với dòng dưới (999.99)
            if h_ratio >= 0.60 and dx <= 3.2 * max_h and dy <= 3.0 * max_h:
                adj[i].append(j)
                adj[j].append(i)

    visited = set()
    best_cluster = []
    for i in range(n):
        if i not in visited:
            comp = []
            queue = [i]
            visited.add(i)
            while queue:
                curr = queue.pop(0)
                comp.append(curr)
                for nxt in adj[curr]:
                    if nxt not in visited:
                        visited.add(nxt)
                        queue.append(nxt)
            if len(comp) > len(best_cluster):
                best_cluster = comp

    cluster_boxes = [boxes[i] for i in best_cluster]
    med_h = np.median([b[3] for b in cluster_boxes])
    # Cho phép dòng trên và dòng dưới chênh lệch chiều cao từ 0.65 đến 1.35 lần trung vị
    refined_boxes = [
        b for b in cluster_boxes
        if (0.65 * med_h <= b[3] <= 1.35 * med_h) and (b[2] <= 1.05 * b[3])
    ]
    return refined_boxes

def extract_local_char_mask(blur_gray, x, y, w, h):
    plate_h, plate_w = blur_gray.shape
    pad = max(2, int(round(min(w, h) * 0.12)))
    y0, y1 = max(0, y - pad), min(plate_h, y + h + pad)
    x0, x1 = max(0, x - pad), min(plate_w, x + w + pad)

    local_patch = blur_gray[y0:y1, x0:x1]
    _, local_thresh = cv2.threshold(local_patch, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    roi_local = local_thresh[(y - y0):(y - y0 + h), (x - x0):(x - x0 + w)]
    return roi_local

def segment_characters(plate_img):
    gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    plate_h, plate_w = thresh.shape
    plate_area = plate_h * plate_w
    candidate_boxes = []

    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        aspect_ratio = w / float(h)
        char_area = w * h
        height_ratio = h / float(plate_h)

        # Mở rộng aspect_ratio lên 1.05 để bắt tốt chữ 'A', 'M', 'W' in đậm trên biển mô hình
        if not (0.10 <= aspect_ratio <= 1.05 and 0.08 <= height_ratio <= 0.90 and (plate_area * 0.0008) < char_area < (plate_area * 0.25)):
            continue

        roi_thresh = thresh[y:y + h, x:x + w]
        fill_ratio = np.mean(roi_thresh > 0)
        if not (0.12 <= fill_ratio <= 0.85):
            continue

        pad = max(2, int(round(h * 0.08)))
        y0, y1 = max(0, y - pad), min(plate_h, y + h + pad)
        x0, x1 = max(0, x - pad), min(plate_w, x + w + pad)
        exp_thresh = thresh[y0:y1, x0:x1]

        border_mask = np.ones(exp_thresh.shape, dtype=bool)
        border_mask[(y - y0):(y - y0 + h), (x - x0):(x - x0 + w)] = False
        border_pixels = exp_thresh[border_mask]

        if len(border_pixels) > 0 and np.mean(border_pixels == 0) < 0.55:
            continue

        exp_gray = gray[y0:y1, x0:x1]
        bg_pixels = exp_gray[exp_thresh == 0]
        fg_pixels = exp_gray[exp_thresh > 0]
        if len(bg_pixels) == 0 or len(fg_pixels) == 0 or (np.mean(bg_pixels) - np.mean(fg_pixels) < 25):
            continue

        candidate_boxes.append((x, y, w, h))

    valid_boxes = []
    for i, (x1, y1, w1, h1) in enumerate(candidate_boxes):
        is_redundant = False
        area1 = w1 * h1
        for j, (x2, y2, w2, h2) in enumerate(candidate_boxes):
            if i == j:
                continue
            ix1, iy1 = max(x1, x2), max(y1, y2)
            ix2, iy2 = min(x1 + w1, x2 + w2), min(y1 + h1, y2 + h2)
            if ix2 > ix1 and iy2 > iy1:
                inter_area = (ix2 - ix1) * (iy2 - iy1)
                if inter_area / float(area1) > 0.65 and (w2 * h2) > area1:
                    is_redundant = True
                    break
        if not is_redundant:
            valid_boxes.append((x1, y1, w1, h1))

    if not valid_boxes:
        return [], thresh

    valid_boxes = filter_main_character_cluster(valid_boxes)
    if not valid_boxes:
        return [], thresh

    centers_y = [y + h / 2.0 for (x, y, w, h) in valid_boxes]
    min_cy, max_cy = min(centers_y), max(centers_y)
    avg_h = np.mean([h for (_, _, _, h) in valid_boxes])

    if (max_cy - min_cy) > (0.55 * avg_h):
        mid_y = (min_cy + max_cy) / 2.0
        top_row = [box for box in valid_boxes if (box[1] + box[3] / 2.0) < mid_y]
        bottom_row = [box for box in valid_boxes if (box[1] + box[3] / 2.0) >= mid_y]

        top_row.sort(key=lambda b: b[0])
        bottom_row.sort(key=lambda b: b[0])
        sorted_boxes = top_row + bottom_row
    else:
        sorted_boxes = sorted(valid_boxes, key=lambda b: b[0])

    char_images = []
    vis_thresh = thresh.copy()
    for (x, y, w, h) in sorted_boxes:
        roi_local = extract_local_char_mask(blur, x, y, w, h)
        vis_thresh[y:y + h, x:x + w] = roi_local
        char_28x28 = pad_and_resize(roi_local, target_size=28)
        char_images.append((char_28x28, (x, y, w, h)))

    return char_images, vis_thresh