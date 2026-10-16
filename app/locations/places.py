"""PLACES — danh mục hành chính Việt Nam (tỉnh/thành → phường/xã/đặc khu) dùng cho mọi ô "Địa điểm".

Nguồn dữ liệu: app/data/vn_places.json (thanglequoc/vietnamese-provinces-database, MIT, 34 tỉnh/thành, 3.321 phường/xã).
Nguyên tắc:
  * Người dùng CHỌN địa điểm theo mã (code) — server không tin chữ gõ tay.
  * Nhãn lưu và hiển thị theo thứ tự lớn → nhỏ: "Thành phố Hồ Chí Minh, Phường Bến Thành".
  * Chỗ cụ thể (quán, homestay…) để liên kết Google Maps lo.
"""
import json
import os
import re
import time
import threading
import unicodedata
from difflib import SequenceMatcher

_DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "vn_places.json")
_lock = threading.Lock()
_DB = None

BAD_PLACE_MSG = "Địa điểm chưa hợp lệ. Hãy chọn từ danh sách gợi ý (tỉnh/thành, phường/xã)."


def norm(text):
    """Bỏ dấu, đ→d, bỏ mọi khoảng trắng/ký tự lạ, viết thường — 'Đà  Lạt' == 'dalat'."""
    s = unicodedata.normalize("NFD", str(text or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("đ", "d").replace("Đ", "D").lower()
    return re.sub(r"[^a-z0-9]", "", s)


def _load():
    global _DB
    if _DB is not None:
        return _DB
    with _lock:
        if _DB is not None:
            return _DB
        with open(_DATA_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        prov, ward = {}, {}
        for p in raw["provinces"]:
            prov[p["code"]] = {"code": p["code"], "kind": "province", "name": p["name"], "full": p["full"],
                               "label": p["full"], "province": p["code"], "nn": norm(p["name"]), "nf": norm(p["full"])}
            for w in p["wards"]:
                code, name, full = w
                ward[code] = {"code": code, "kind": "ward", "name": name, "full": full,
                              "label": p["full"] + ", " + full, "province": p["code"],
                              "nn": norm(name), "nf": norm(full)}
        by_prov = {c: [] for c in prov}
        for w in ward.values():
            by_prov[w["province"]].append(w)
        for lst in by_prov.values():
            lst.sort(key=lambda w: w["name"])
        name_idx = {}
        for p in prov.values():
            name_idx.setdefault(p["nn"], p["code"])
            name_idx.setdefault(p["nf"], p["code"])
        alias_idx = {}
        pname = {p["name"]: p["code"] for p in prov.values()}
        for a, target in raw["aliases"].items():
            if target in pname and norm(a) not in name_idx:
                alias_idx[norm(a)] = {"alias": a, "province": pname[target]}
        ward_name_idx = {}
        for w in ward.values():
            for k in {w["nn"], w["nf"]}:
                ward_name_idx.setdefault(k, []).append(w["code"])
        _DB = {"meta": {k: raw[k] for k in ("version", "decree", "generated", "source")},
               "prov": prov, "ward": ward, "by_prov": by_prov, "name_idx": name_idx,
               "alias_idx": alias_idx, "ward_name_idx": ward_name_idx}
    return _DB


def meta():
    return _load()["meta"]


def get(code):
    """Thông tin 1 đơn vị theo mã, hoặc None."""
    db = _load()
    code = str(code or "").strip()
    return db["prov"].get(code) or db["ward"].get(code)


def public(item, extra=None):
    d = {"code": item["code"], "kind": item["kind"], "name": item["name"], "full": item["full"], "label": item["label"]}
    if item["kind"] == "ward":
        p = _load()["prov"][item["province"]]
        d["province_code"], d["province"] = p["code"], p["full"]
    if extra:
        d.update(extra)
    return d


def provinces():
    db = _load()
    return sorted(db["prov"].values(), key=lambda p: p["name"])


def wards_of(province_code, q=""):
    db = _load()
    lst = db["by_prov"].get(str(province_code), [])
    qn = norm(q)
    if qn:
        lst = [w for w in lst if qn in w["nn"] or qn in w["nf"]]
    return lst


def find_province(text, allow_alias=True):
    """Tên tỉnh (có/không dấu, tên đầy đủ, tên cũ, địa danh du lịch) → (province_item, alias_text|None)."""
    db = _load()
    k = norm(text)
    if not k:
        return None, None
    c = db["name_idx"].get(k)
    if c:
        return db["prov"][c], None
    a = db["alias_idx"].get(k) if allow_alias else None
    if a:
        return db["prov"][a["province"]], a["alias"]
    return None, None


def _split_hint(q):
    """'Quán Gió, Đà Lạt' → (phần còn lại, tỉnh, alias). Thử phần cuối rồi phần đầu."""
    parts = [p.strip() for p in re.split(r"[,;]", q) if p.strip()]
    if len(parts) < 2:
        return q.strip(), None, None
    for allow in (False, True):                           # ưu tiên tên tỉnh thật, rồi mới tới tên cũ/địa danh
        for idx in (-1, 0):
            prov, alias = find_province(parts[idx], allow)
            if prov:
                rest = [p for i, p in enumerate(parts) if i != (len(parts) - 1 if idx == -1 else 0)]
                return ", ".join(rest), prov, alias
    return q.strip(), None, None


def search(q, province=None, limit=8):
    """Gợi ý theo chữ gõ. Trả list dict (đã sắp xếp). Gõ đúng tên → 1 dòng; gõ gần giống → nhiều dòng."""
    db = _load()
    limit = max(1, min(int(limit or 8), 30))
    q = (q or "").strip()[:80]
    prov = db["prov"].get(str(province)) if province else None
    note = None
    rest = q
    if not prov:
        rest, hp, alias = _split_hint(q)
        if hp:
            prov = hp
            note = "Gán vào " + hp["full"]
    qn = norm(rest)
    if not qn:
        if prov:
            return [public(prov, {"note": note})] if note else [public(w) for w in db["by_prov"][prov["code"]][:limit]]
        return [public(p) for p in provinces()[:limit]]

    scored = []
    exact = False
    # 1) tỉnh / thành (+ tên cũ, địa danh du lịch)
    if not prov:
        for p in db["prov"].values():
            s = _score(qn, p["nn"], p["nf"])
            if s:
                scored.append((s, p["name"], public(p)))
        for k, a in db["alias_idx"].items():
            s = _score(qn, k, k)
            if s:
                p = db["prov"][a["province"]]
                scored.append((min(s, 95), a["alias"], public(p, {"via": a["alias"], "note": "%s thuộc %s" % (a["alias"], p["full"])})))
    # 2) phường / xã
    pool = db["by_prov"][prov["code"]] if prov else db["ward"].values()
    for w in pool:
        s = _score(qn, w["nn"], w["nf"])
        if s:
            scored.append((s, w["name"], public(w)))
    if not scored and len(qn) >= 4 and not note:          # gõ sai chính tả nhẹ → so khớp mờ
        for w in list(pool) + ([] if prov else list(db["prov"].values())):
            r = max(SequenceMatcher(None, qn, w["nn"]).ratio(), SequenceMatcher(None, qn, w["nf"]).ratio())
            if r >= 0.85:
                scored.append((int(r * 50), w["name"], public(w)))
    scored.sort(key=lambda t: (-t[0], t[1]))
    if scored and scored[0][0] >= 100:                   # trùng đúng tên → chỉ giữ những dòng trùng đúng
        scored = [t for t in scored if t[0] >= 95]   # giữ cả tên cũ/địa danh (điểm 95)
    seen, out = set(), []
    for s, _n, item in scored:
        if item["code"] in seen:
            continue
        seen.add(item["code"])
        out.append(item)
        if len(out) >= limit:
            break
    if not out and prov:                                  # có tỉnh nhưng không khớp phường: xếp luôn vào tỉnh
        out = [public(prov, {"note": note or "Gán vào " + prov["full"]})]
    elif note and out:
        for o in out:
            o.setdefault("note", note)
    return out


def _score(qn, nn, nf):
    if qn == nn or qn == nf:
        return 100
    if nn.startswith(qn) or nf.startswith(qn):
        return 80
    if qn in nn or qn in nf:
        return 60
    return 0


def resolve_text(text):
    """Chữ gõ/đã chọn → mã đơn vị, hoặc None nếu không nhận ra (nghiêm ngặt, không đoán)."""
    db = _load()
    text = (text or "").strip()
    if not text or len(text) > 160:
        return None
    parts = [p.strip() for p in re.split(r"[,;]", text) if p.strip()]
    # nhãn đầy đủ "Tỉnh, Phường"
    if len(parts) >= 2:
        for allow, (pi, wi) in ((a, o) for a in (False, True) for o in ((0, 1), (1, 0))):
            prov, _ = find_province(parts[pi], allow)
            if prov:
                hit = [c for c in db["ward_name_idx"].get(norm(parts[wi]), []) if db["ward"][c]["province"] == prov["code"]]
                if len(hit) == 1:
                    return hit[0]
                return prov["code"]                       # tỉnh rõ ràng, phần còn lại để Google Maps lo
        return None
    prov, _ = find_province(text)
    if prov:
        return prov["code"]
    hit = db["ward_name_idx"].get(norm(text), [])
    return hit[0] if len(hit) == 1 else None


# ---------------------------------------------------------------- Location rows

def location_for_code(code):
    """Trả về hàng Location ứng với mã (tạo nếu chưa có, kèm hàng tỉnh làm cha)."""
    from sqlalchemy.exc import IntegrityError
    from app.extensions import db
    from app.models import Location

    info = get(code)
    if not info:
        return None
    loc = Location.query.filter_by(code=info["code"]).first()
    if loc:
        return loc
    parent_id = None
    if info["kind"] == "ward":
        parent = location_for_code(info["province"])
        parent_id = parent.id if parent else None
    try:
        loc = Location(name=info["label"], slug="vn-" + info["code"], kind=info["kind"],
                       code=info["code"], parent_id=parent_id)
        db.session.add(loc)
        db.session.commit()
        return loc
    except IntegrityError:
        db.session.rollback()
        return Location.query.filter_by(code=info["code"]).first()


def resolve_location(text, code=None, keep=()):
    """Dùng ở mọi nơi nhận địa điểm từ người dùng.
    Trả (Location|None, lỗi|None). Rỗng → (None, None). `keep`: các Location cũ được giữ nguyên nếu chữ không đổi
    (bài/lịch trình cũ chưa có mã vẫn sửa được)."""
    text = (text or "").strip()
    code = (code or "").strip()
    if not text and not code:
        return None, None
    if code:
        info = get(code)
        if not info:
            return None, BAD_PLACE_MSG
        return location_for_code(code), None
    for k in keep:
        if k is not None and text == (k.name or ""):
            return k, None
    c = resolve_text(text)
    if not c:
        return None, BAD_PLACE_MSG
    return location_for_code(c), None


# ---------------------------------------------------------------- rate limit nhẹ cho API gợi ý
_hits = {}


def rate_ok(key, limit=120, window=60):
    now = time.time()
    with _lock:
        lst = [t for t in _hits.get(key, []) if now - t < window]
        if len(lst) >= limit:
            _hits[key] = lst
            return False
        lst.append(now)
        _hits[key] = lst
        if len(_hits) > 5000:
            for k in [k for k, v in _hits.items() if not v or now - v[-1] > window]:
                _hits.pop(k, None)
    return True
