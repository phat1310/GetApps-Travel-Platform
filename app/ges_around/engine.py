"""Lõi tính toán GEs Around: mô hình thời gian (hồi quy tuyến tính) + lọc địa điểm + xếp hạng."""
import math
from urllib.parse import urlencode

import numpy as np

from app.ges_around import config as C
from app.ges_around.store import snapshot

EARTH_R = 6371.0088


def haversine_km(lat1, lon1, lat2, lon2):
    """Khoảng cách đường chim bay (km); lat2/lon2 có thể là mảng numpy."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi, dl = p2 - p1, np.radians(lon2) - math.radians(lon1)
    h = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * EARTH_R * np.arcsin(np.sqrt(h))


def travel_minutes(vehicle, d_km):
    """Thời gian di chuyển một chiều (phút) = SAFETY × (a·d + b). d_km: số hoặc mảng numpy."""
    _, a, b, _ = C.VEHICLES[vehicle]
    return C.SAFETY * (a * d_km + b)


def max_radius_km(vehicle, one_way_min):
    """Bán kính tối đa (km) để thời gian một chiều ≤ one_way_min — dùng làm bounding box tiền lọc."""
    _, a, b, _ = C.VEHICLES[vehicle]
    r = (one_way_min / C.SAFETY - b) / a
    return max(r, 0.0)


def kind_key(kind):
    return (kind.split("=", 1)[1] if "=" in kind else kind).strip().lower()


def kind_label(kind):
    k = kind_key(kind)
    return C.KIND_LABEL.get(k) or (k.replace("_", " ").capitalize() if k else "Địa điểm")


def est_cost(kind, grp, pmin, pmax):
    """(thấp, cao, là_ước_tính). Ưu tiên giá thật trong DB nếu có."""
    if pmin is not None and pmax is not None:
        return pmin, pmax, False
    lo, hi = C.COST_BY_KIND.get(kind_key(kind)) or C.COST_BY_GROUP[grp]
    return lo, hi, True


def safe_url(u):
    return u if isinstance(u, str) and u[:8].lower().startswith(("http://", "https://")) else None


def directions_url(vehicle, o_lat, o_lon, d_lat, d_lon):
    q = {"api": 1, "origin": f"{o_lat:.6f},{o_lon:.6f}", "destination": f"{d_lat:.6f},{d_lon:.6f}",
         "travelmode": C.VEHICLES[vehicle][3]}
    return "https://www.google.com/maps/dir/?" + urlencode(q)


def search(o_lat, o_lon, free_min, needs, budget, vehicles=None):
    """Trả về {vehicle: {"label":..., "groups": {grp: [item,...]}, "total": n}} cho từng phương tiện."""
    snap = snapshot()
    out = {}
    quota = max(1, C.MAX_PER_GROUP_TOTAL // max(1, len(needs)))
    lat_all, lon_all, grp_all = snap["lat"], snap["lon"], snap["grp"]
    for v in (vehicles or C.VEHICLE_ORDER):
        groups = {}
        for g in needs:
            one_way = (free_min - C.DWELL_MIN[g]) / 2.0
            res = []
            if one_way > 0 and snap["n"]:
                r_km = max_radius_km(v, one_way)
                dlat = r_km / 111.0
                dlon = r_km / (111.0 * max(math.cos(math.radians(o_lat)), 0.2))
                m = (grp_all == g) & (np.abs(lat_all - o_lat) <= dlat) & (np.abs(lon_all - o_lon) <= dlon)
                idx = np.nonzero(m)[0]
                if idx.size:
                    d = haversine_km(o_lat, o_lon, lat_all[idx], lon_all[idx])
                    t = travel_minutes(v, d)
                    ok = t <= one_way
                    idx, d, t = idx[ok], d[ok], t[ok]
                    cand = []
                    for k, i in enumerate(idx):
                        lo, hi, est = est_cost(snap["kind"][i], g, snap["pmin"][i], snap["pmax"][i])
                        if budget is not None and lo > budget:
                            continue
                        cand.append((-int(snap["pop"][i]), float(t[k]), int(i), float(d[k]), lo, hi, est))
                    cand.sort()
                    for _, tk, i, dk, lo, hi, est in cand[:quota]:
                        res.append({
                            "id": snap["id"][i], "name": snap["name"][i], "grp": g,
                            "kind": kind_label(snap["kind"][i]),
                            "travel_min": int(math.ceil(tk)), "total_min": int(math.ceil(2 * tk + C.DWELL_MIN[g])),
                            "dist_km": round(dk, 1),
                            "cost": {"min": lo, "max": hi, "estimated": est},
                            "addr": snap["addr"][i] or "", "hours": snap["hours"][i] or "",
                            "web": safe_url(snap["web"][i]),
                            "source": "OpenStreetMap" if snap["src"][i] == "osm" else ("Overture Maps" if snap["src"][i] == "overture" else "GEs"),
                            "directions": directions_url(v, o_lat, o_lon, float(lat_all[i]), float(lon_all[i])),
                        })
            groups[g] = res
        out[v] = {"label": C.VEHICLES[v][0], "groups": groups, "total": sum(len(x) for x in groups.values())}
    return out
