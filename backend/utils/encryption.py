"""
Encryption Utilities
Cung cấp mã hóa/giải mã đối xứng dùng Fernet (AES-128-CBC + HMAC).

Cách sử dụng:
  1. Sinh key một lần: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  2. Đặt vào .env:  ENCRYPTION_KEY=<key vừa sinh>
  3. Gọi encrypt_value() trước khi lưu, decrypt_value() sau khi đọc.

Nếu không có ENCRYPTION_KEY trong env:
  - Sử dụng key dự phòng tạo từ máy (dựa theo hostname), kèm cảnh báo.
  - Dữ liệu vẫn được mã hóa nhưng mức bảo mật thấp hơn.
"""
import os
import base64
import hashlib
import warnings
from functools import lru_cache

try:
    from cryptography.fernet import Fernet, InvalidToken
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False
    warnings.warn(
        "[encryption] Thư viện 'cryptography' chưa được cài đặt. "
        "Chạy: pip install cryptography>=42.0.0",
        RuntimeWarning,
        stacklevel=2
    )


# Prefix để phân biệt giá trị đã mã hóa với plain text (dùng cho migrate)
_ENCRYPTED_PREFIX = "enc:"


@lru_cache(maxsize=1)
def _get_fernet() -> "Fernet | None":
    """
    Khởi tạo Fernet instance (singleton, cache bằng lru_cache).
    Ưu tiên lấy key từ ENCRYPTION_KEY env var.
    Fallback: sinh key từ hostname (cảnh báo bảo mật thấp hơn).
    """
    if not _CRYPTO_AVAILABLE:
        return None

    raw_key = os.environ.get("ENCRYPTION_KEY", "").strip()

    if raw_key:
        try:
            # Validate key format (Fernet key phải là URL-safe base64, 32 bytes)
            return Fernet(raw_key.encode())
        except Exception:
            pass

    # Fallback: tạo key ổn định từ hostname
    warnings.warn(
        "[encryption] ⚠️  ENCRYPTION_KEY không có trong .env! "
        "Đang dùng key dự phòng — bảo mật THẤP. "
        "Hãy sinh key và đặt vào backend/.env:\n"
        "  python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"",
        RuntimeWarning,
        stacklevel=3
    )
    import socket
    hostname = socket.gethostname().encode()
    seed = hashlib.sha256(hostname + b"auto_rpa_hdsaison_fallback_v1").digest()
    fernet_key = base64.urlsafe_b64encode(seed)
    return Fernet(fernet_key)


def encrypt_value(plain_text: str) -> str:
    """
    Mã hóa chuỗi và trả về dạng "enc:<base64_ciphertext>".
    Nếu crypto không có sẵn hoặc lỗi, trả về plain text gốc (không crash).

    Args:
        plain_text: Chuỗi cần mã hóa

    Returns:
        Chuỗi đã mã hóa với prefix "enc:", hoặc plain text nếu lỗi
    """
    if not plain_text:
        return plain_text

    # Không mã hóa lại nếu đã encrypt rồi
    if plain_text.startswith(_ENCRYPTED_PREFIX):
        return plain_text

    fernet = _get_fernet()
    if fernet is None:
        return plain_text  # Fallback: trả về plain text

    try:
        cipher = fernet.encrypt(plain_text.encode("utf-8"))
        return _ENCRYPTED_PREFIX + cipher.decode("utf-8")
    except Exception as e:
        print(f"[encryption] Lỗi mã hóa: {e}")
        return plain_text


def decrypt_value(cipher_text: str) -> str:
    """
    Giải mã chuỗi được tạo bởi encrypt_value().
    Tự động xử lý cả plain text (chưa mã hóa — dùng cho migrate).

    Args:
        cipher_text: Chuỗi cần giải mã (có hoặc không có prefix "enc:")

    Returns:
        Chuỗi gốc sau khi giải mã
    """
    if not cipher_text:
        return cipher_text

    # Plain text chưa mã hóa (dữ liệu cũ — auto migrate)
    if not cipher_text.startswith(_ENCRYPTED_PREFIX):
        return cipher_text

    fernet = _get_fernet()
    if fernet is None:
        # Crypto không có, trả về chuỗi bỏ prefix (best effort)
        return cipher_text[len(_ENCRYPTED_PREFIX):]

    try:
        raw = cipher_text[len(_ENCRYPTED_PREFIX):]
        return fernet.decrypt(raw.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        print("[encryption] ⚠️  Token không hợp lệ — key đã thay đổi hoặc dữ liệu bị hỏng.")
        return ""
    except Exception as e:
        print(f"[encryption] Lỗi giải mã: {e}")
        return ""


def is_encrypted(value: str) -> bool:
    """Kiểm tra xem chuỗi đã được mã hóa chưa."""
    return bool(value) and value.startswith(_ENCRYPTED_PREFIX)
