"""Regression checks for database boundaries and biometric encryption."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import numpy as np
from cryptography.exceptions import InvalidTag

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from smart_parking.infrastructure.security import embedding_cipher as crypto


class DatabaseSecurityTests(unittest.TestCase):
    def setUp(self):
        self.cipher = crypto.EmbeddingCipher("MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
        self.vector = np.ones(512, dtype=np.float32) / np.sqrt(512)

    def test_aes_record_cannot_be_written_without_cryptography(self):
        with patch.object(crypto, "_HAS_CRYPTOGRAPHY", False):
            with self.assertRaisesRegex(RuntimeError, "no fallback"):
                self.cipher.encrypt_embedding(self.vector)

    def test_corrupted_encrypted_record_is_rejected(self):
        blob, metadata = self.cipher.encrypt_embedding(self.vector)
        corrupted = bytearray(blob)
        corrupted[15] ^= 1
        with self.assertRaises(InvalidTag):
            self.cipher.decrypt_embedding(bytes(corrupted), metadata)

    def test_aes_record_does_not_fall_back_to_a_different_algorithm(self):
        blob, metadata = self.cipher.encrypt_embedding(self.vector)
        self.assertEqual(metadata["backend"], "cryptography")
        with patch.object(crypto, "_HAS_CRYPTOGRAPHY", False):
            with self.assertRaisesRegex(RuntimeError, "AES-256-GCM"):
                self.cipher.decrypt_embedding(blob, metadata)

if __name__ == "__main__":
    unittest.main()
