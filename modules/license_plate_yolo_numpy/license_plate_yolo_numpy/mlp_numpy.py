import numpy as np

CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
CHAR_TO_IDX = {ch: i for i, ch in enumerate(CHARS)}
IDX_TO_CHAR = {i: ch for i, ch in enumerate(CHARS)}

class NumpyMLP:
    def __init__(self, input_size=784, hidden_size=160, num_classes=36):
        # Kích thước vector đặc trưng tổng hợp:
        # 784 (Pixel) + 49 (Zoning 7x7) + 392 (HOG 7x7x8 hướng) + 168 (Ray-casting 4 hướng) = 1393
        feat_dim = 1393
        h1_dim = 320
        h2_dim = hidden_size

        # Khởi tạo He Initialization
        self.W1 = np.random.randn(feat_dim, h1_dim) * np.sqrt(2.0 / feat_dim)
        self.b1 = np.zeros((1, h1_dim))

        self.W2 = np.random.randn(h1_dim, h2_dim) * np.sqrt(2.0 / h1_dim)
        self.b2 = np.zeros((1, h2_dim))

        self.W3 = np.random.randn(h2_dim, num_classes) * np.sqrt(2.0 / h2_dim)
        self.b3 = np.zeros((1, num_classes))

        # Khởi tạo bộ nhớ cho thuật toán tối ưu Adam (m_t và v_t)
        self.t = 0
        self.params = ['W1', 'b1', 'W2', 'b2', 'W3', 'b3']
        self.m_adam = {k: np.zeros_like(getattr(self, k)) for k in self.params}
        self.v_adam = {k: np.zeros_like(getattr(self, k)) for k in self.params}

    def extract_features(self, X):
        """
        Trích xuất đặc trưng bất biến bằng NumPy thuần:
        1. Điểm ảnh chuẩn hóa (784 chiều)
        2. Lưới mật độ Zoning 7x7 (49 chiều) - chống lệch tâm
        3. Biểu đồ hướng đạo hàm HOG 7x7 ô x 8 góc (392 chiều) - bất biến độ dày nét
        4. Ray-casting Profiles 4 hướng & Projection (168 chiều) - bắt khe hở bụng chữ
        """
        m = X.shape[0]
        imgs = X.reshape(m, 28, 28)

        # 1. Đặc trưng Zoning 7x7 (Gộp trung bình mỗi ô 4x4 pixel)
        zoning_7x7 = imgs.reshape(m, 7, 4, 7, 4).mean(axis=(2, 4)).reshape(m, 49) * 1.5

        # 2. Đặc trưng HOG (Histogram of Oriented Gradients) 8 hướng góc trên lưới 7x7
        gx = np.zeros_like(imgs)
        gy = np.zeros_like(imgs)
        gx[:, :, 1:-1] = imgs[:, :, 2:] - imgs[:, :, :-2]
        gy[:, 1:-1, :] = imgs[:, 2:, :] - imgs[:, :-2, :]

        mag = np.sqrt(gx ** 2 + gy ** 2 + 1e-8)
        # Quy đổi góc [-pi, pi] về [0, 8) tương ứng 8 bin hướng
        angle = np.arctan2(gy, gx) + np.pi
        bins = np.floor(angle / (2.0 * np.pi / 8.0)).astype(np.int32) % 8

        hog_cells = np.zeros((m, 7, 7, 8), dtype=np.float32)
        for b in range(8):
            weighted_mag = np.where(bins == b, mag, 0.0)
            hog_cells[:, :, :, b] = weighted_mag.reshape(m, 7, 4, 7, 4).sum(axis=(2, 4))

        # Chuẩn hóa L2 theo từng ô 4x4 để chống lóa sáng / thay đổi tương phản
        cell_norm = np.sqrt(np.sum(hog_cells ** 2, axis=3, keepdims=True) + 1e-6)
        hog_feats = (hog_cells / cell_norm).reshape(m, 392) * 1.5

        # 3. Ray-casting Profile 4 hướng (Trái, Phải, Trên, Dưới)
        mask = (imgs > 0.35)
        has_row = np.any(mask, axis=2)
        left_prof = np.where(has_row, np.argmax(mask, axis=2) / 28.0, 1.0)
        right_prof = np.where(has_row, np.argmax(mask[:, :, ::-1], axis=2) / 28.0, 1.0)

        has_col = np.any(mask, axis=1)
        top_prof = np.where(has_col, np.argmax(mask, axis=1) / 28.0, 1.0)
        bot_prof = np.where(has_col, np.argmax(mask[:, ::-1, :], axis=1) / 28.0, 1.0)

        h_proj = np.mean(imgs, axis=2)
        v_proj = np.mean(imgs, axis=1)
        profile_feats = np.hstack([left_prof, right_prof, top_prof, bot_prof, h_proj, v_proj]) * 1.8

        return np.hstack([X, zoning_7x7, hog_feats, profile_feats])

    def relu(self, Z):
        return np.maximum(0, Z)

    def softmax(self, Z):
        exp_Z = np.exp(Z - np.max(Z, axis=1, keepdims=True))
        return exp_Z / np.sum(exp_Z, axis=1, keepdims=True)

    def forward(self, X, training=False, dropout_rate=0.15):
        """
        Khi gọi từ main.py (suy luận), training mặc định = False nên Dropout tự động tắt.
        Khi gọi từ train.py, bật training=True để chống học vẹt.
        """
        self.F = self.extract_features(X)
        self.Z1 = np.dot(self.F, self.W1) + self.b1
        self.A1 = self.relu(self.Z1)

        if training and dropout_rate > 0:
            self.mask1 = (np.random.rand(*self.A1.shape) >= dropout_rate) / (1.0 - dropout_rate)
            self.A1 *= self.mask1
        else:
            self.mask1 = np.ones_like(self.A1)

        self.Z2 = np.dot(self.A1, self.W2) + self.b2
        self.A2 = self.relu(self.Z2)

        if training and dropout_rate > 0:
            self.mask2 = (np.random.rand(*self.A2.shape) >= dropout_rate) / (1.0 - dropout_rate)
            self.A2 *= self.mask2
        else:
            self.mask2 = np.ones_like(self.A2)

        self.Z3 = np.dot(self.A2, self.W3) + self.b3
        self.A3 = self.softmax(self.Z3)
        return self.A3

    def compute_loss(self, Y_target, sample_weights=None):
        m = Y_target.shape[0]
        log_probs = -np.sum(Y_target * np.log(self.A3 + 1e-8), axis=1)
        if sample_weights is not None:
            log_probs = log_probs * sample_weights
        return np.sum(log_probs) / m

    def backward(self, X, Y_target, learning_rate=0.0015, sample_weights=None, weight_decay=1e-4):
        """
        Lan truyền ngược kết hợp thuật toán tối ưu Adam (Adaptive Moment Estimation)
        """
        m = X.shape[0]
        dZ3 = self.A3 - Y_target
        if sample_weights is not None:
            dZ3 = dZ3 * sample_weights[:, None]

        # Đạo hàm tầng 3
        dW3 = np.dot(self.A2.T, dZ3) / m + weight_decay * self.W3
        db3 = np.sum(dZ3, axis=0, keepdims=True) / m

        # Đạo hàm tầng 2
        dA2 = np.dot(dZ3, self.W3.T) * self.mask2
        dZ2 = dA2 * (self.Z2 > 0)
        dW2 = np.dot(self.A1.T, dZ2) / m + weight_decay * self.W2
        db2 = np.sum(dZ2, axis=0, keepdims=True) / m

        # Đạo hàm tầng 1
        dA1 = np.dot(dZ2, self.W2.T) * self.mask1
        dZ1 = dA1 * (self.Z1 > 0)
        dW1 = np.dot(self.F.T, dZ1) / m + weight_decay * self.W1
        db1 = np.sum(dZ1, axis=0, keepdims=True) / m

        grads = {'W1': dW1, 'b1': db1, 'W2': dW2, 'b2': db2, 'W3': dW3, 'b3': db3}

        # Cập nhật bằng thuật toán Adam
        self.t += 1
        beta1, beta2, eps = 0.9, 0.999, 1e-8
        for k in self.params:
            g = grads[k]
            self.m_adam[k] = beta1 * self.m_adam[k] + (1.0 - beta1) * g
            self.v_adam[k] = beta2 * self.v_adam[k] + (1.0 - beta2) * (g ** 2)

            m_hat = self.m_adam[k] / (1.0 - beta1 ** self.t)
            v_hat = self.v_adam[k] / (1.0 - beta2 ** self.t)

            param_val = getattr(self, k)
            setattr(self, k, param_val - learning_rate * m_hat / (np.sqrt(v_hat) + eps))

    def predict(self, X):
        probs = self.forward(X, training=False)
        return np.argmax(probs, axis=1), np.max(probs, axis=1)

    def save_weights(self, filepath="weights/ocr_candidate_weights.npz"):
        np.savez(filepath, W1=self.W1, b1=self.b1, W2=self.W2, b2=self.b2, W3=self.W3, b3=self.b3)
        print(f"Đã lưu trọng số tối ưu tại: {filepath}")

    def load_weights(self, filepath="weights/ocr_coco_weights.npz"):
        data = np.load(filepath)
        self.W1, self.b1 = data["W1"], data["b1"]
        self.W2, self.b2 = data["W2"], data["b2"]
        self.W3, self.b3 = data["W3"], data["b3"]
        print(f"Đã nạp trọng số mô hình từ: {filepath}")
