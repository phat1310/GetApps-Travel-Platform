"""Ảnh nền cho khung thông tin ở trang cá nhân (và thẻ hồ sơ ở bảng tin).

An toàn:
- KHÔNG tin đuôi file / Content-Type do client gửi: kiểm tra NỘI DUNG thật (magic bytes), chỉ nhận JPEG / PNG / WebP (không SVG, không GIF).
- Có Pillow: mở thật bằng Pillow, xoay theo EXIF rồi MÃ HÓA LẠI thành JPEG -> bỏ sạch metadata (vị trí GPS...), mã độc nhúng trong file
  (polyglot), và giới hạn kích thước ảnh để chống "decompression bomb".
- Tên file do server tự sinh (ngẫu nhiên), lưu trong static/uploads/backgrounds/; xóa file chỉ khi đường dẫn đúng khuôn mẫu đó.
"""
import io
import os
import re
import secrets

from flask import current_app

MAX_BG_BYTES = 5 * 1024 * 1024          # 5MB
MAX_PIXELS = 40_000_000                 # chặn ảnh khổng lồ (decompression bomb)
MAX_SIDE = 2400                         # cạnh dài tối đa sau khi xử lý
MIN_W, MIN_H = 400, 150                 # nhỏ hơn sẽ bị vỡ khi phủ kín khung
URL_PREFIX = "/static/uploads/backgrounds/"
_NAME_RE = re.compile(r"^bg_\d+_[0-9a-f]{12}\.(jpg|png|webp)$")
_ORIG_RE = re.compile(r"^bgo_\d+_[0-9a-f]{12}\.(jpg|png|webp)$")   # ảnh GỐC (chưa cắt) đi kèm ảnh nền, để lần sau căn chỉnh lại
_EXTS = ("jpg", "png", "webp")


class BgError(ValueError):
    """Lỗi người dùng nhìn thấy được (đã là câu tiếng Việt)."""


def is_safe_bg_url(url):
    """True chỉ khi URL đúng khuôn mẫu do server sinh (không có '..', dấu nháy, scheme lạ...). Dùng trước khi in vào CSS/HTML."""
    return bool(url) and url.startswith(URL_PREFIX) and _NAME_RE.match(url[len(URL_PREFIX):]) is not None


def sniff_image_type(head):
    """'jpg' | 'png' | 'webp' | None — theo magic bytes."""
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return None


def _process(data, kind):
    """Trả về (bytes, ext). Có Pillow thì mã hóa lại; không có thì giữ nguyên bytes đã kiểm tra magic."""
    try:
        from PIL import Image, ImageOps
    except ImportError:                                  # môi trường chưa cài Pillow: vẫn an toàn ở mức magic bytes + giới hạn dung lượng
        return data, kind
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        img = Image.open(io.BytesIO(data))
        if img.format not in ("JPEG", "PNG", "WEBP"):
            raise BgError("Chỉ nhận ảnh JPG, PNG hoặc WebP.")
        w, h = img.size
        if w * h > MAX_PIXELS:
            raise BgError("Ảnh quá lớn (độ phân giải), hãy chọn ảnh nhỏ hơn.")
        img.load()
    except BgError:
        raise
    except Exception:                                    # file hỏng / giả ảnh / bom giải nén
        raise BgError("Không đọc được ảnh này. Hãy chọn một file ảnh JPG, PNG hoặc WebP hợp lệ.")
    img = ImageOps.exif_transpose(img)
    w, h = img.size
    if w < MIN_W or h < MIN_H:
        raise BgError(f"Ảnh quá nhỏ (tối thiểu {MIN_W}×{MIN_H}px) nên sẽ bị vỡ khi phủ kín khung.")
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        base = Image.new("RGB", img.size, (255, 255, 255))
        base.paste(img, mask=img.split()[-1])
        img = base
    elif img.mode != "RGB":
        img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=85, optimize=True)     # không copy EXIF/ICC -> sạch metadata
    return out.getvalue(), "jpg"


def _folder():
    return os.path.join(current_app.root_path, "static", "uploads", "backgrounds")


def original_url_for(url):
    """URL ảnh gốc đi kèm ảnh nền `url` (cùng mã ngẫu nhiên, tiền tố bgo_), hoặc None nếu không có / URL không hợp lệ."""
    if not is_safe_bg_url(url):
        return None
    stem = url[len(URL_PREFIX):].rsplit(".", 1)[0][len("bg_"):]
    for ext in _EXTS:
        name = f"bgo_{stem}.{ext}"
        if _ORIG_RE.match(name) and os.path.isfile(os.path.join(_folder(), name)):
            return URL_PREFIX + name
    return None


def save_original(file_storage, bg_url):
    """Lưu ảnh gốc (đã kiểm tra + mã hóa lại như ảnh nền) cạnh ảnh nền `bg_url`. Lỗi -> bỏ qua êm (ảnh gốc chỉ là tiện ích)."""
    if not is_safe_bg_url(bg_url) or file_storage is None:
        return None
    try:
        data = file_storage.stream.read(MAX_BG_BYTES + 1)
        if not data or len(data) > MAX_BG_BYTES:
            return None
        kind = sniff_image_type(data[:16])
        if kind is None:
            return None
        data, ext = _process(data, kind)
        stem = bg_url[len(URL_PREFIX):].rsplit(".", 1)[0][len("bg_"):]
        name = f"bgo_{stem}.{ext}"
        if not _ORIG_RE.match(name):
            return None
        os.makedirs(_folder(), exist_ok=True)
        with open(os.path.join(_folder(), name), "wb") as fh:
            fh.write(data)
        return URL_PREFIX + name
    except Exception:
        return None


def save_background(file_storage, user_id):
    """Kiểm tra + lưu ảnh nền, trả về URL tĩnh ('/static/uploads/backgrounds/...'). Ném BgError nếu không hợp lệ."""
    stream = file_storage.stream
    data = stream.read(MAX_BG_BYTES + 1)
    if not data:
        raise BgError("File rỗng.")
    if len(data) > MAX_BG_BYTES:
        raise BgError("Ảnh vượt quá 5MB.")
    kind = sniff_image_type(data[:16])
    if kind is None:
        raise BgError("Chỉ nhận ảnh JPG, PNG hoặc WebP (kiểm tra theo nội dung file, không theo đuôi tên).")
    data, ext = _process(data, kind)
    name = f"bg_{int(user_id)}_{secrets.token_hex(6)}.{ext}"
    folder = os.path.join(current_app.root_path, "static", "uploads", "backgrounds")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, name), "wb") as fh:
        fh.write(data)
    return URL_PREFIX + name


def remove_background_file(url):
    """Xóa file ảnh nền cũ. Chỉ xóa khi URL đúng khuôn mẫu do mình sinh ra (chặn path traversal / đường dẫn lạ trong DB)."""
    if not url or not url.startswith(URL_PREFIX):
        return
    name = url[len(URL_PREFIX):]
    if not _NAME_RE.match(name):
        return
    victims = [name]
    stem = name.rsplit(".", 1)[0][len("bg_"):]
    victims += [f"bgo_{stem}.{e}" for e in _EXTS]          # xóa luôn ảnh gốc đi kèm
    for v in victims:
        if not (_NAME_RE.match(v) or _ORIG_RE.match(v)):
            continue
        full = os.path.join(_folder(), v)
        try:
            if os.path.isfile(full):
                os.remove(full)
        except OSError:
            pass
