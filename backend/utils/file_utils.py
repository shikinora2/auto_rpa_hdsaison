"""
File Utilities
Cung cấp các hàm ghi/đọc file an toàn:
  - atomic_write_json: Ghi JSON atomic (tạm -> replace) để tránh corrupt khi crash
  - safe_read_json: Đọc JSON với fallback an toàn
"""
import os
import json
import tempfile
from pathlib import Path
from typing import Any


def atomic_write_json(path: Path | str, data: Any, encoding: str = "utf-8") -> bool:
    """
    Ghi dữ liệu JSON vào file theo cách atomic:
      1. Ghi vào file tạm (.tmp) cùng thư mục
      2. Dùng os.replace() để đổi tên — thao tác này atomic trên OS
    Đảm bảo file không bao giờ bị hỏng dở do crash giữa chừng.

    Args:
        path: Đường dẫn file đích
        data: Dữ liệu cần ghi (serializable sang JSON)
        encoding: Encoding (mặc định utf-8)

    Returns:
        True nếu thành công, False nếu lỗi
    """
    path = Path(path)
    try:
        # Đảm bảo thư mục cha tồn tại
        path.parent.mkdir(parents=True, exist_ok=True)

        # Tạo file tạm cùng thư mục để os.replace() hoạt động atomic
        # (os.replace() chỉ atomic khi src và dst cùng filesystem)
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=path.parent,
            prefix=path.stem + "_",
            suffix=".tmp"
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding=encoding) as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())  # Đảm bảo dữ liệu được flush xuống disk

            # Atomic replace với retry — trên Windows os.replace() có thể bị
            # WinError 5 (Access Denied) nếu file đích đang bị thread khác lock
            import time as _time
            for attempt in range(5):
                try:
                    os.replace(tmp_path, path)
                    return True
                except PermissionError:
                    if attempt < 4:
                        _time.sleep(0.02 * (attempt + 1))  # 20ms, 40ms, 60ms, 80ms
                    else:
                        raise  # Re-raise ở lần thử cuối

        except Exception:
            # Dọn dẹp file tạm nếu ghi lỗi
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    except Exception as e:
        print(f"[file_utils] Lỗi khi ghi file {path}: {e}")
        return False


def safe_read_json(path: Path | str, default: Any = None) -> Any:
    """
    Đọc file JSON an toàn với fallback.
    Trả về `default` nếu file không tồn tại hoặc JSON bị hỏng.

    Args:
        path: Đường dẫn file cần đọc
        default: Giá trị trả về khi lỗi (mặc định None)

    Returns:
        Dữ liệu đã parse hoặc default
    """
    path = Path(path)
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"[file_utils] File JSON bị hỏng {path}: {e}")
        return default
    except Exception as e:
        print(f"[file_utils] Lỗi khi đọc file {path}: {e}")
        return default
