"""AES-256-GCM Embedding Cipher for 512-D Face Templates."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
from typing import Any, Dict, Optional, Tuple

import numpy as np

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore
    _HAS_CRYPTOGRAPHY = True
except ImportError:
    AESGCM = None  # type: ignore
    _HAS_CRYPTOGRAPHY = False


def _derive_32byte_key(raw_key: str) -> bytes:
    """Decode a 32-byte AES-256 key from base64, hex, or UTF-8 string."""
    cleaned = (raw_key or "").strip()
    if not cleaned:
        raise ValueError("EMBEDDING_SECRET_KEY không được để trống.")
    # Try base64
    try:
        decoded = base64.urlsafe_b64decode(cleaned + "=" * (-len(cleaned) % 4))
        if len(decoded) == 32:
            return decoded
    except Exception:
        pass
    # Try hex
    try:
        if len(cleaned) == 64:
            return bytes.fromhex(cleaned)
    except Exception:
        pass
    # Raw 32-byte string or SHA-256 derivation
    raw_bytes = cleaned.encode("utf-8")
    if len(raw_bytes) == 32:
        return raw_bytes
    return hashlib.sha256(raw_bytes).digest()


def _fallback_aead_encrypt(key: bytes, nonce: bytes, plaintext: bytes, aad: bytes) -> bytes:
    """Authenticated stream cipher fallback when cryptography wheel is unavailable offline."""
    stream = bytearray()
    counter = 0
    while len(stream) < len(plaintext):
        block = hashlib.sha256(key + nonce + counter.to_bytes(4, "big")).digest()
        stream.extend(block)
        counter += 1
    ciphertext = bytes(a ^ b for a, b in zip(plaintext, stream[: len(plaintext)]))
    tag = hmac.new(key, nonce + aad + ciphertext, hashlib.sha256).digest()[:16]
    return ciphertext + tag


def _fallback_aead_decrypt(key: bytes, nonce: bytes, blob: bytes, aad: bytes) -> bytes:
    """Verify tag and decrypt fallback AEAD ciphertext."""
    if len(blob) < 16:
        raise ValueError("Dữ liệu mã hóa embedding không hợp lệ (thiếu authentication tag).")
    ciphertext, tag = blob[:-16], blob[-16:]
    expected_tag = hmac.new(key, nonce + aad + ciphertext, hashlib.sha256).digest()[:16]
    if not hmac.compare_digest(tag, expected_tag):
        raise ValueError("Xác thực chữ ký AES-GCM thất bại (khóa sai hoặc dữ liệu bị thay đổi).")
    stream = bytearray()
    counter = 0
    while len(stream) < len(ciphertext):
        block = hashlib.sha256(key + nonce + counter.to_bytes(4, "big")).digest()
        stream.extend(block)
        counter += 1
    return bytes(a ^ b for a, b in zip(ciphertext, stream[: len(ciphertext)]))


class EmbeddingCipher:
    """Encrypts and decrypts L2-normalized 512-D float32 face embeddings using AES-256-GCM."""

    def __init__(
        self,
        secret_key: Optional[str] = None,
        default_key_version: str = "v1",
        l2_tolerance: float = 1e-3,
    ) -> None:
        raw_secret = secret_key if secret_key is not None else os.getenv("EMBEDDING_SECRET_KEY", "")
        if not raw_secret:
            raise ValueError("Thiếu biến môi trường EMBEDDING_SECRET_KEY cho EmbeddingCipher.")
        self._key: bytes = _derive_32byte_key(raw_secret)
        self.default_key_version = default_key_version
        self.l2_tolerance = l2_tolerance

    @staticmethod
    def validate_embedding(
        vector_np: np.ndarray,
        expected_size: int = 512,
        l2_tolerance: float = 1e-3,
    ) -> np.ndarray:
        """Validate 1D 512-element float32 finite L2-normalized embedding vector."""
        if not isinstance(vector_np, np.ndarray):
            vector_np = np.asarray(vector_np, dtype=np.float32)
        if vector_np.ndim != 1 or vector_np.shape[0] != expected_size:
            raise ValueError(
                f"Vector embedding phải là mảng 1D có đúng {expected_size} phần tử, "
                f"nhận được shape={vector_np.shape}."
            )
        if vector_np.dtype != np.float32:
            vector_np = vector_np.astype(np.float32)
        if not np.all(np.isfinite(vector_np)):
            raise ValueError("Vector embedding chứa giá trị NaN hoặc Inf không hợp lệ.")
        norm = float(np.linalg.norm(vector_np))
        if norm <= 0.0:
            raise ValueError("Vector embedding có chuẩn L2 bằng 0.")
        if abs(norm - 1.0) > l2_tolerance:
            raise ValueError(
                f"Vector embedding chưa chuẩn hóa L2 (norm={norm:.6f}, yêu cầu ~1.0 ± {l2_tolerance})."
            )
        return vector_np

    def encrypt_embedding(
        self,
        vector_np: np.ndarray,
        key_version: Optional[str] = None,
    ) -> Tuple[bytes, Dict[str, Any]]:
        """Validate and encrypt a 512-D float32 L2-normalized embedding into (blob, metadata)."""
        validated = self.validate_embedding(vector_np, expected_size=512, l2_tolerance=self.l2_tolerance)
        kv = key_version or self.default_key_version
        nonce = os.urandom(12)
        plaintext = validated.tobytes()
        aad = f"pbl4:embedding:{kv}:float32:512".encode("utf-8")

        if _HAS_CRYPTOGRAPHY and AESGCM is not None:
            aesgcm = AESGCM(self._key)
            blob = aesgcm.encrypt(nonce, plaintext, aad)
            backend = "cryptography"
        else:
            raise RuntimeError("cryptography is required for AES-256-GCM encryption; no fallback encryption is allowed")

        # AESGCM appends the 16-byte authentication tag at the end of ciphertext
        tag_b64 = base64.b64encode(blob[-16:]).decode("ascii")
        metadata: Dict[str, Any] = {
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "tag": tag_b64,
            "alg": "AES-256-GCM",
            "backend": backend,
        }
        return blob, metadata

    def decrypt_embedding(
        self,
        blob: bytes,
        metadata: Dict[str, Any],
        dtype: str = "float32",
        size: int = 512,
        key_version: Optional[str] = None,
    ) -> np.ndarray:
        """Decrypt an encrypted embedding blob back into a 1D (512,) float32 numpy array."""
        if not isinstance(blob, (bytes, bytearray, memoryview)):
            raise ValueError("embedding_blob phải là kiểu bytes.")
        raw_blob = bytes(blob)
        if not metadata or "nonce" not in metadata:
            raise ValueError("encryption_metadata thiếu trường 'nonce'.")
        if metadata.get("alg", "AES-256-GCM") != "AES-256-GCM":
            raise ValueError(f"Thuật toán mã hóa không được hỗ trợ: {metadata.get('alg')}")

        nonce = base64.b64decode(metadata["nonce"])
        kv = key_version or metadata.get("key_version") or self.default_key_version
        aad = f"pbl4:embedding:{kv}:{dtype}:{size}".encode("utf-8")
        backend = metadata.get("backend")

        if backend == "builtin-aead":
            # Read compatibility only for old records. Never create new records in this format.
            plaintext = _fallback_aead_decrypt(self._key, nonce, raw_blob, aad)
        else:
            if not (_HAS_CRYPTOGRAPHY and AESGCM is not None):
                raise RuntimeError("cryptography is required to decrypt AES-256-GCM records")
            aesgcm = AESGCM(self._key)
            plaintext = aesgcm.decrypt(nonce, raw_blob, aad)

        np_dtype = np.dtype(dtype)
        arr = np.frombuffer(plaintext, dtype=np_dtype).copy()
        if arr.shape != (size,):
            raise ValueError(f"Kích thước vector sau giải mã không khớp: {arr.shape} != ({size},)")
        if not np.all(np.isfinite(arr)):
            raise ValueError("Vector sau giải mã chứa giá trị không hữu hạn.")
        return arr
