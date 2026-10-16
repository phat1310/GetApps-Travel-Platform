"""GEOCHECK — so toạ độ trong link Google Maps với tỉnh/thành người dùng đã chọn (chỉ CẢNH BÁO, không chặn).

Ý tưởng: link Google Maps thường chứa toạ độ ( .../@16.04,108.22,17z  |  !3d16.04!4d108.22  |  ?q=16.04,108.22 ).
Lấy toạ độ → so với KHUNG (bounding box) gần đúng của tỉnh/thành đã chọn. Lệch xa → nhắc người dùng + lưu cờ để kiểm duyệt.

Giới hạn (nói thẳng): khung chữ nhật chỉ GẦN ĐÚNG ranh giới thật (bộ dữ liệu hành chính đang dùng không kèm đa giác),
nên có "đệm" dung sai: bài viết 15 km, lịch trình nhiều tỉnh 80 km. Cảnh báo là gợi ý, không phải phán quyết.

Link rút gọn (maps.app.goo.gl): chỉ theo chuyển hướng theo cách an toàn (SSRF): chỉ tên miền Google Maps, tối đa 4 bước,
timeout ngắn, chặn IP nội bộ/loopback/link-local, không đọc nội dung trang.
"""
import http.client
import ipaddress
import math
import re
import socket
import threading
import time
from urllib.parse import urlsplit, urljoin, parse_qs, unquote

from app.locations.maplinks import check_map_url

TOL_POST_KM = 15
TOL_PLAN_KM = 80
MAX_HOPS = 4
HOP_TIMEOUT = 3
TOTAL_BUDGET = 7

# mã tỉnh (trong vn_places.json) -> các khung (lat_min, lat_max, lon_min, lon_max), gồm cả đảo xa bờ
BOXES = {
    "01": [(20.55, 21.40, 105.28, 106.03)],
    "04": [(22.35, 23.12, 105.45, 106.80)],
    "08": [(21.35, 23.40, 104.35, 105.95)],
    "11": [(20.95, 22.40, 102.10, 103.65)],
    "12": [(21.70, 22.80, 102.35, 103.85)],
    "14": [(20.65, 22.05, 103.20, 105.00)],
    "15": [(21.20, 22.90, 103.40, 105.10)],
    "19": [(21.20, 22.75, 105.30, 106.20)],
    "20": [(21.20, 22.30, 106.20, 107.40)],
    "22": [(20.60, 21.70, 106.40, 108.10)],
    "24": [(20.95, 21.70, 105.80, 107.00)],
    "25": [(20.35, 21.75, 104.60, 105.70)],
    "31": [(20.40, 21.20, 106.00, 107.20), (20.10, 20.20, 107.65, 107.80)],
    "33": [(20.20, 21.00, 105.80, 106.70)],
    "37": [(19.90, 20.70, 105.50, 106.60)],
    "38": [(19.15, 20.60, 104.35, 106.10)],
    "40": [(18.55, 20.00, 103.85, 105.80)],
    "42": [(17.95, 18.85, 105.10, 106.50)],
    "44": [(16.30, 18.10, 105.60, 107.40)],
    "46": [(15.95, 16.80, 107.00, 108.20)],
    "48": [(14.70, 16.30, 107.20, 108.90), (15.70, 17.20, 111.00, 113.00)],       # + Hoàng Sa
    "51": [(13.80, 15.50, 107.30, 109.20)],
    "52": [(12.90, 14.80, 107.40, 109.50)],
    "56": [(11.30, 12.90, 108.60, 109.50), (6.00, 12.00, 111.00, 115.50)],        # + Trường Sa
    "66": [(12.20, 13.65, 107.40, 109.50)],
    "68": [(10.40, 12.70, 107.10, 109.10)],
    "75": [(10.70, 12.30, 106.30, 107.60)],
    "79": [(10.10, 11.60, 106.30, 107.60), (8.55, 8.90, 106.40, 106.85)],         # + Côn Đảo
    "80": [(10.20, 12.00, 105.50, 106.70)],
    "82": [(10.00, 10.95, 105.00, 105.95), (10.15, 10.62, 105.70, 106.78)],   # Đồng Tháp cũ + Tiền Giang cũ
    "86": [(9.30, 10.50, 105.70, 106.90)],
    "91": [(9.20, 10.95, 103.30, 105.50)],                                         # gồm Phú Quốc, Hà Tiên
    "92": [(9.20, 10.20, 105.30, 106.40)],
    "96": [(8.50, 9.60, 104.70, 105.90)],
}
VN_BOX = (5.5, 24.0, 101.5, 118.0)

# ---------------------------------------------------------------- 1. lấy toạ độ từ URL
_NUM = r"(-?\d{1,3}\.\d+)"
_RE_3D4D = re.compile(r"!3d" + _NUM + r"!4d" + _NUM)
_RE_AT = re.compile(r"@" + _NUM + r"," + _NUM)
_RE_PAIR = re.compile(r"^\s*" + _NUM + r"\s*,\s*\+?" + _NUM + r"\s*$")
_RE_PATH = re.compile(r"/(?:place|search|dir)/" + _NUM + r",\+?" + _NUM)


def _ok(lat, lon):
    return -90 <= lat <= 90 and -180 <= lon <= 180


def parse_coords(url):
    """URL Google Maps → (lat, lon) hoặc None. Ưu tiên toạ độ ĐỊA ĐIỂM (!3d!4d) hơn tâm khung nhìn (@)."""
    if not isinstance(url, str) or len(url) > 1000:
        return None
    u = unquote(url)
    for rx in (_RE_3D4D, _RE_PATH, _RE_AT):
        m = rx.search(u)
        if m:
            lat, lon = float(m.group(1)), float(m.group(2))
            if _ok(lat, lon):
                return lat, lon
    try:
        qs = parse_qs(urlsplit(url).query)
    except ValueError:
        return None
    for k in ("q", "query", "ll", "center", "destination", "daddr"):
        for v in qs.get(k, []):
            m = _RE_PAIR.match(v)
            if m and _ok(float(m.group(1)), float(m.group(2))):
                return float(m.group(1)), float(m.group(2))
    return None


# ---------------------------------------------------------------- 2. link rút gọn: theo chuyển hướng an toàn
_SHORT_HOSTS = {"maps.app.goo.gl", "goo.gl"}
_cache = {}
_cache_lock = threading.Lock()


def is_short(url):
    try:
        return (urlsplit(url).hostname or "").lower() in _SHORT_HOSTS
    except ValueError:
        return False


def _public_host(host):
    """Mọi IP của tên miền phải là IP công cộng (chặn 127.0.0.1, 10.x, 169.254.x, ::1…)."""
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError:
        return False
    if not infos:
        return False
    for info in infos:
        try:
            if not ipaddress.ip_address(info[4][0].split("%")[0]).is_global:
                return False
        except ValueError:
            return False
    return True


def _fetch_redirect(url):
    """1 bước: (status, location|None). Không đọc nội dung trang. Có thể thay thế khi test."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not _public_host(host):
        return None, None
    conn = http.client.HTTPSConnection(host, timeout=HOP_TIMEOUT)
    try:
        path = (parts.path or "/") + (("?" + parts.query) if parts.query else "")
        conn.request("GET", path, headers={"User-Agent": "Mozilla/5.0 (compatible; GEsLinkCheck/1.0)", "Accept": "text/html"})
        r = conn.getresponse()
        return r.status, r.getheader("Location")
    except (OSError, http.client.HTTPException):
        return None, None
    finally:
        conn.close()


def resolve_short(url):
    """Theo chuyển hướng của link rút gọn tới khi có toạ độ. Trả (lat, lon) hoặc None. Không bao giờ ném lỗi."""
    with _cache_lock:
        if url in _cache:
            return _cache[url]
    found, cur, deadline = None, url, time.time() + TOTAL_BUDGET
    try:
        for _ in range(MAX_HOPS + 1):
            clean, err = check_map_url(cur)         # mỗi bước phải vẫn là link Google Maps hợp lệ (kiểm TRƯỚC khi tin toạ độ)
            if err or time.time() > deadline:
                break
            c = parse_coords(clean)
            if c:
                found = c
                break
            status, loc = _fetch_redirect(clean)
            if status not in (301, 302, 303, 307, 308) or not loc:
                break
            cur = urljoin(clean, loc)
    except Exception:                               # an toàn: lỗi mạng không được làm hỏng việc đăng bài
        found = None
    with _cache_lock:
        if len(_cache) > 500:
            _cache.clear()
        _cache[url] = found
    return found


def coords_for(url):
    c = parse_coords(url)
    if c or not is_short(url):
        return c
    return resolve_short(url)


# ---------------------------------------------------------------- 3. so khớp với tỉnh
def _km(lat1, lon1, lat2, lon2):
    return math.hypot((lat2 - lat1) * 111.0, (lon2 - lon1) * 111.0 * math.cos(math.radians((lat1 + lat2) / 2)))


def distance_to_province_km(lat, lon, pcode):
    """Khoảng cách (km) từ điểm tới khung tỉnh gần nhất; 0 nếu nằm trong. None nếu chưa có khung của tỉnh."""
    boxes = BOXES.get(str(pcode))
    if not boxes:
        return None
    best = None
    for a, b, c, d in boxes:
        nlat, nlon = min(max(lat, a), b), min(max(lon, c), d)
        k = _km(lat, lon, nlat, nlon)
        best = k if best is None else min(best, k)
    return best


def province_code_of(location):
    """Location (đã chọn từ danh mục) → mã tỉnh; địa điểm cũ gõ tay thì thử nhận diện theo chữ, không được thì None."""
    import app.locations.places as places
    if location is None:
        return None
    if location.code:
        info = places.get(location.code)
        return info["province"] if info else None
    c = places.resolve_text(location.name)
    info = places.get(c) if c else None
    return info["province"] if info else None


def check_links(links, locations, kind="post"):
    """links: [{'url','label'}]; locations: [Location] (chính + phụ). Trả list kết quả theo từng link:
    {url, label, lat, lon, status: 'ok'|'far'|'skip', km, province}. Chỉ 'far' mới cần cảnh báo."""
    import app.locations.places as places
    tol = TOL_PLAN_KM if kind == "plan" else TOL_POST_KM
    pcodes = [p for p in (province_code_of(l) for l in locations if l is not None) if p]
    out = []
    for it in links:
        url = it.get("url") if isinstance(it, dict) else it
        res = {"url": url, "label": (it.get("label") if isinstance(it, dict) else "") or "", "lat": None, "lon": None,
               "status": "skip", "km": None, "province": None}
        out.append(res)
        if not pcodes:
            continue                                   # chưa chọn địa điểm → không có gì để so
        c = coords_for(url)
        if not c:
            continue                                   # link không có toạ độ → bỏ qua
        res["lat"], res["lon"] = c
        dists = [(distance_to_province_km(c[0], c[1], p), p) for p in pcodes]
        dists = [(d, p) for d, p in dists if d is not None]
        if not dists:
            continue
        d, p = min(dists)
        res["km"] = round(d, 1)
        res["province"] = places.get(p)["full"]
        res["status"] = "far" if d > tol else "ok"
    return out


def warning_text(results):
    far = [r for r in results if r["status"] == "far"]
    if not far:
        return None
    r = far[0]
    who = ("Link “%s”" % r["label"]) if r["label"] else "Một link Google Maps"
    more = (" (và %d link khác)" % (len(far) - 1)) if len(far) > 1 else ""
    return "%s%s có vẻ nằm cách %s khoảng %d km. Bạn kiểm tra lại link hoặc địa điểm đã chọn nhé — vẫn đăng được nếu đúng ý bạn." % (
        who, more, r["province"], round(r["km"]))
