"""Kiểm tra + lưu link Google Maps gắn vào bài viết / lịch trình.

Tư duy bảo mật (OWASP — Unvalidated Redirects/XSS): link do người dùng nhập sẽ được render thành
<a href> mà NGƯỜI KHÁC bấm vào. Vì vậy server phải tự kiểm tra, không tin giao diện:
  * Chỉ nhận scheme http/https (chặn javascript:, data:, vbscript:, file:...).
  * Chỉ nhận đúng tên miền Google Maps (chặn phishing / open-redirect kiểu google.com/url?q=evil).
  * Chặn user-info (https://google.com@evil.com), dấu '\\', ký tự điều khiển, tên miền Unicode giả (homograph).
  * Link lưu lại luôn được chuẩn hóa về https, bỏ #fragment.
  * Tên hiển thị: bỏ ký tự điều khiển/định dạng (kể cả U+202E đảo chiều chữ), tối đa 60 ký tự; Jinja tự escape khi render.
  * Số lượng tối đa kiểm tra Ở SERVER (bài viết 2, lịch trình 5).
Lưu ý: link rút gọn maps.app.goo.gl là redirect của chính Google, server không thể biết đích cuối nên chỉ tin tên miền.
"""
import json
import re
from urllib.parse import urlsplit, urlunsplit

POST_LIMIT = 2
PLAN_LIMIT = 5
MAX_URL_LEN = 500
MAX_LABEL_LEN = 60
MAX_RAW_JSON = 8000

# google.com, www.google.com, google.com.vn, google.co.uk, google.fr ...
_GOOGLE_HOST = re.compile(r"^(www\.)?google\.(com|com\.[a-z]{2}|co\.[a-z]{2}|[a-z]{2})$")


def check_map_url(raw):
    """Trả về (url_chuẩn_hóa, None) nếu hợp lệ, ngược lại (None, thông_báo_lỗi)."""
    if not isinstance(raw, str):
        return None, "Link Google Maps không hợp lệ."
    url = raw.strip()
    if not url:
        return None, "Vui lòng dán link Google Maps."
    if len(url) > MAX_URL_LEN:
        return None, f"Link quá dài (tối đa {MAX_URL_LEN} ký tự)."
    if "\\" in url or any(ch.isspace() or not ch.isprintable() for ch in url):
        return None, "Link không được chứa khoảng trắng hoặc ký tự lạ."
    if "://" not in url:
        url = "https://" + url          # cho phép dán "maps.app.goo.gl/abc" không có https://
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return None, "Link Google Maps không hợp lệ."
    if parts.scheme not in ("http", "https"):
        return None, "Chỉ chấp nhận link bắt đầu bằng http hoặc https."
    if "@" in parts.netloc or parts.username or parts.password:
        return None, "Link Google Maps không hợp lệ."
    if port not in (None, 80, 443):
        return None, "Link Google Maps không hợp lệ."

    host = (parts.hostname or "").lower().rstrip(".")
    path = parts.path or ""
    ok = (
        host == "maps.google.com"
        or (host == "maps.app.goo.gl" and len(path.strip("/")) > 0)
        or (host == "goo.gl" and path.startswith("/maps"))
        or (bool(_GOOGLE_HOST.match(host)) and (path == "/maps" or path.startswith("/maps/")))
    )
    if not ok:
        return None, "Chỉ nhận link Google Maps (google.com/maps, maps.app.goo.gl...)."

    clean = urlunsplit(("https", host, path, parts.query, ""))
    if len(clean) > MAX_URL_LEN:
        return None, f"Link quá dài (tối đa {MAX_URL_LEN} ký tự)."
    return clean, None


def clean_label(raw):
    """Trả về (tên_đã_làm_sạch, None) hoặc (None, lỗi). Rỗng là hợp lệ (hiển thị 'Xem trên Google Maps')."""
    if raw is None:
        return "", None
    if not isinstance(raw, str):
        return None, "Tên hiển thị không hợp lệ."
    s = re.sub(r"\s+", " ", raw).strip()
    s = "".join(ch for ch in s if ch.isprintable())      # bỏ ký tự điều khiển / định dạng (U+202E...)
    if len(s) > MAX_LABEL_LEN:
        return None, f"Tên hiển thị tối đa {MAX_LABEL_LEN} ký tự."
    return s, None


def parse_map_links(raw, limit):
    """raw: chuỗi JSON (từ form) hoặc list (từ JSON API). Trả về (list[{'url','label'}], None) hoặc (None, lỗi)."""
    if raw is None or raw == "" or raw == []:
        return [], None
    if isinstance(raw, str):
        if len(raw) > MAX_RAW_JSON:
            return None, "Dữ liệu địa chỉ quá lớn."
        try:
            raw = json.loads(raw)
        except ValueError:
            return None, "Dữ liệu địa chỉ không hợp lệ."
    if not isinstance(raw, list):
        return None, "Dữ liệu địa chỉ không hợp lệ."
    if len(raw) > limit:
        return None, f"Chỉ được gắn tối đa {limit} địa chỉ Google Maps."

    out, seen = [], set()
    for item in raw:
        if not isinstance(item, dict):
            return None, "Dữ liệu địa chỉ không hợp lệ."
        url, err = check_map_url(item.get("url"))
        if err:
            return None, err
        label, err = clean_label(item.get("label"))
        if err:
            return None, err
        if url in seen:
            continue
        seen.add(url)
        out.append({"url": url, "label": label})
    return out, None


def attach_map_links(links, *, post=None, itinerary=None, locations=None):
    """Tạo các dòng MapLink cho 1 bài viết HOẶC 1 lịch trình (gọi sau db.session.flush() để có id).
    `locations`: các Location đã chọn (chính + phụ) để so toạ độ với tỉnh; lệch xa → lưu cờ mismatch cho kiểm duyệt
    (KHÔNG chặn đăng). Lỗi khi kiểm tra không bao giờ làm hỏng việc lưu."""
    from app.extensions import db
    from app.models.map_link import MapLink
    assert (post is None) != (itinerary is None)
    checked = {}
    if locations and links:
        try:
            from app.locations import geocheck
            for r in geocheck.check_links(links, locations, "post" if post is not None else "plan"):
                checked[r["url"]] = r
        except Exception:
            checked = {}
    for i, item in enumerate(links):
        r = checked.get(item["url"]) or {}
        db.session.add(MapLink(
            url=item["url"],
            label=item["label"],
            position=i,
            post_id=post.id if post is not None else None,
            itinerary_id=itinerary.id if itinerary is not None else None,
            lat=r.get("lat"), lon=r.get("lon"),
            mismatch=(1 if r.get("status") == "far" else (0 if r.get("status") == "ok" else None)),
            mismatch_km=r.get("km"),
        ))


def visible_links(owner):
    """Danh sách MapLink hiển thị được (đã kiểm tra lại URL) của post/itinerary — dùng cho template/JSON."""
    return [m for m in (getattr(owner, "map_links", None) or []) if m.safe_url]


# ---------- Dùng cho chặng / khách sạn trong form Đăng lịch trình ----------
_BAD_CHARS = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u202a-\u202e\u2066-\u2069\u200b-\u200f]")
_LOOKS_LIKE_LINK = re.compile(r"^(https?://|www\.|maps\.app\.goo\.gl|goo\.gl/|(www\.)?google\.)", re.I)


def clean_text(raw, max_len, keep_newlines=False):
    """Bỏ ký tự điều khiển / đảo chiều chữ (U+202E...), gọn khoảng trắng, cắt đúng độ dài cột."""
    s = _BAD_CHARS.sub("", str(raw or ""))
    if keep_newlines:
        s = s.replace("\r\n", "\n").strip()
    else:
        s = re.sub(r"\s+", " ", s).strip()
    return s[:max_len]


def looks_like_link(raw):
    return bool(_LOOKS_LIKE_LINK.match((raw or "").strip()))


def check_web_url(raw):
    """Link đặt phòng (Agoda, Booking...): chỉ http/https, có tên miền, không user-info/khoảng trắng. -> (url|None, lỗi|None)"""
    url = (raw or "").strip()
    if not url:
        return None, None
    if len(url) > MAX_URL_LEN:
        return None, f"Link quá dài (tối đa {MAX_URL_LEN} ký tự)."
    if "\\" in url or any(ch.isspace() or not ch.isprintable() for ch in url):
        return None, "Link không được chứa khoảng trắng hoặc ký tự lạ."
    if "://" not in url:
        url = "https://" + url
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return None, "Link không hợp lệ."
    host = (parts.hostname or "").lower()
    if parts.scheme not in ("http", "https") or not host or "." not in host:
        return None, "Chỉ chấp nhận link bắt đầu bằng http hoặc https."
    if "@" in parts.netloc or port not in (None, 80, 443):
        return None, "Link không hợp lệ."
    try:
        host.encode("ascii")
    except UnicodeEncodeError:
        return None, "Tên miền chứa ký tự lạ."
    clean = urlunsplit(("https", host, parts.path or "", parts.query, ""))
    if len(clean) > MAX_URL_LEN:
        return None, f"Link quá dài (tối đa {MAX_URL_LEN} ký tự)."
    return clean, None
