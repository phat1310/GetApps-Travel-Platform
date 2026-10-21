"""Routes GEs Around — chỉ người đã đăng nhập; POST có CSRF (header X-CSRFToken từ meta csrf-token)."""
import threading
import time
from collections import defaultdict, deque

from flask import jsonify, request, current_app
from flask_login import login_required, current_user

from app.ges_around import ges_around_bp, config as C
from app.ges_around.areas import AREAS, AREA_BY_ID
from app.ges_around.engine import search as run_search

_hits = defaultdict(deque)
_hits_lock = threading.Lock()


def _rate_limited(uid):
    limit, window = current_app.config.get("GES_RATE_LIMIT", C.RATE_LIMIT)
    now = time.monotonic()
    with _hits_lock:
        q = _hits[uid]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            return True
        q.append(now)
    return False


def _num(v, lo, hi):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    if v != v or v < lo or v > hi:          # NaN / ngoài khoảng
        return None
    return v


@ges_around_bp.route("/areas", methods=["GET"])
@login_required
def areas():
    resp = jsonify({
        "areas": AREAS,
        "free_minutes": list(C.FREE_MIN_CHOICES),
        "vehicles": [{"id": v, "label": C.VEHICLES[v][0]} for v in C.VEHICLE_ORDER],
        "groups": [{"id": g, "label": C.GROUP_LABEL[g]} for g in C.GROUPS],
        "attribution": C.ATTRIBUTION,
    })
    resp.headers["Cache-Control"] = "private, max-age=3600"
    return resp


@ges_around_bp.route("/search", methods=["POST"])
@login_required
def search():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "Dữ liệu gửi lên không hợp lệ."}), 400

    free = _num(body.get("free_minutes"), *C.FREE_MIN_RANGE)
    if free is None:
        return jsonify({"error": "Thời gian rảnh không hợp lệ."}), 400
    free = int(free)

    needs = body.get("needs")
    if not isinstance(needs, list) or not needs or any(n not in C.GROUPS for n in needs):
        return jsonify({"error": "Hãy chọn ít nhất một nhu cầu (ăn uống / giải trí / tham quan)."}), 400
    needs = [g for g in C.GROUPS if g in set(needs)]

    budget = body.get("budget")
    if budget is not None:
        budget = _num(budget, 0, C.BUDGET_MAX)
        if budget is None:
            return jsonify({"error": "Ngân sách không hợp lệ."}), 400
        budget = int(budget)

    origin = body.get("origin")
    if not isinstance(origin, dict):
        return jsonify({"error": "Thiếu vị trí xuất phát."}), 400
    if origin.get("type") == "area":
        area = AREA_BY_ID.get(origin.get("id")) if isinstance(origin.get("id"), str) else None
        if not area:
            return jsonify({"error": "Khu vực không nằm trong danh sách hỗ trợ."}), 400
        o_lat, o_lon, o_name = area["lat"], area["lng"], area["name"]
    elif origin.get("type") == "gps":
        lat_min, lon_min, lat_max, lon_max = C.REGION_BBOX
        o_lat, o_lon = _num(origin.get("lat"), lat_min, lat_max), _num(origin.get("lng"), lon_min, lon_max)
        if o_lat is None or o_lon is None:
            return jsonify({"error": "Vị trí của bạn nằm ngoài khu vực hỗ trợ (TP.HCM mới, gồm Bình Dương và Bà Rịa – Vũng Tàu)."}), 400
        o_name = "Vị trí hiện tại của bạn"
    else:
        return jsonify({"error": "Kiểu vị trí không hợp lệ."}), 400

    vehicle = body.get("vehicle")
    if vehicle is not None and vehicle not in C.VEHICLES:
        return jsonify({"error": "Phương tiện không hợp lệ."}), 400

    if _rate_limited(current_user.id):
        return jsonify({"error": "Bạn tìm hơi nhanh rồi, thử lại sau ít phút nhé."}), 429

    data = run_search(float(o_lat), float(o_lon), free, needs, budget)
    resp = jsonify({
        "ok": True,
        "origin": {"name": o_name},          # không trả/lưu toạ độ ngoài URL chỉ đường
        "query": {"free_minutes": free, "needs": needs, "budget": budget, "vehicle": vehicle or C.VEHICLE_ORDER[0]},
        "vehicles": data, "vehicle_order": C.VEHICLE_ORDER,
        "group_label": C.GROUP_LABEL,
        "note": "Thời gian di chuyển là ước tính (hồi quy tuyến tính trên số đo Google Maps, chưa tính kẹt xe riêng cho từng lúc). Giá là ước tính theo loại hình.",
        "attribution": C.ATTRIBUTION,
    })
    resp.headers["Cache-Control"] = "no-store"
    return resp
