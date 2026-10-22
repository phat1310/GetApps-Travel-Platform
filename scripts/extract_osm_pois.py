# -*- coding: utf-8 -*-
"""
Trich xuat dia diem (an uong / giai tri / tham quan) cua HCM moi tu file OSM .pbf
va ve ranh gioi HCM moi (HCM cu + Binh Duong + Ba Ria - Vung Tau).

Cach chay (cmd):
  pip install osmium
  python scripts\\extract_osm_pois.py --pbf app\\data\\data_draw\\vietnam-261020.osm.pbf --out app\\data\\data_draw

Ket qua (trong thu muc --out):
  osm_pois_hcm.parquet     (cac dia diem co ten, nam trong ranh gioi)
  hcm_boundary.geojson     (ranh gioi da gop, don gian hoa)
  osm_extract_report.json  (so lieu thong ke + SHA-256 cua file .pbf)
"""
import argparse, hashlib, json, os, sys, time, unicodedata
from collections import Counter

import osmium
import shapely
import numpy as np
from shapely.geometry import LineString, mapping
from shapely.ops import linemerge, polygonize, unary_union
import pyarrow as pa
import pyarrow.parquet as pq


def fold(s):
    s = unicodedata.normalize("NFD", str(s).lower().replace("đ", "d"))
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


PROVINCE_KEYS = ("ho chi minh", "binh duong", "ba ria", "vung tau")

FOOD_AMENITY = {"restaurant", "cafe", "fast_food", "food_court", "bar", "pub",
                "biergarten", "ice_cream", "juice_bar"}
FOOD_SHOP = {"bakery", "pastry", "confectionery", "coffee", "tea", "deli",
             "beverages", "ice_cream", "chocolate"}
ENT_AMENITY = {"cinema", "theatre", "nightclub", "karaoke_box", "casino",
               "arts_centre", "planetarium", "events_venue", "stripclub", "music_venue"}
ENT_LEISURE = {"water_park", "amusement_arcade", "bowling_alley", "escape_game",
               "miniature_golf", "adult_gaming_centre", "ice_rink", "trampoline_park",
               "dance", "golf_course", "sports_centre", "stadium", "fishing",
               "marina", "resort", "beach_resort"}
ENT_TOURISM = {"theme_park", "zoo", "aquarium"}
SIGHT_TOURISM = {"attraction", "museum", "viewpoint", "gallery"}
SIGHT_LEISURE = {"park", "garden", "nature_reserve"}
SIGHT_NATURAL = {"beach", "waterfall", "peak", "cave_entrance", "hot_spring"}
SIGHT_MANMADE = {"lighthouse", "obelisk"}
SIGHT_AMENITY = {"place_of_worship", "marketplace"}

KEEP = ["name", "name:vi", "name:en", "brand", "operator", "cuisine", "opening_hours",
        "phone", "contact:phone", "website", "contact:website", "contact:facebook",
        "fee", "charge", "addr:housenumber", "addr:street", "addr:subdistrict",
        "addr:district", "addr:city", "addr:province", "religion", "denomination",
        "wikidata", "wikipedia", "description"]


def classify(d):
    a = d.get("amenity"); t = d.get("tourism"); l = d.get("leisure")
    s = d.get("shop"); h = d.get("historic"); n = d.get("natural")
    m = d.get("man_made")
    if a in FOOD_AMENITY: return ("an_uong", "amenity=" + a)
    if s in FOOD_SHOP: return ("an_uong", "shop=" + s)
    if t in ENT_TOURISM: return ("giai_tri", "tourism=" + t)
    if a in ENT_AMENITY: return ("giai_tri", "amenity=" + a)
    if l in ENT_LEISURE: return ("giai_tri", "leisure=" + l)
    if s == "mall": return ("giai_tri", "shop=mall")
    if t in SIGHT_TOURISM: return ("tham_quan", "tourism=" + t)
    if h: return ("tham_quan", "historic=" + h)
    if a in SIGHT_AMENITY: return ("tham_quan", "amenity=" + a)
    if l in SIGHT_LEISURE: return ("tham_quan", "leisure=" + l)
    if n in SIGHT_NATURAL: return ("tham_quan", "natural=" + n)
    if d.get("waterway") == "waterfall": return ("tham_quan", "waterway=waterfall")
    if m in SIGHT_MANMADE: return ("tham_quan", "man_made=" + m)
    return None


def best_name(d):
    return d.get("name") or d.get("name:vi") or d.get("name:en")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def approx_area_km2(geom):
    minx, miny, maxx, maxy = geom.bounds
    lat0 = (miny + maxy) / 2.0
    k = 111.32 * np.cos(np.radians(lat0)) * 110.57
    return geom.area * k


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pbf", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    t0 = time.time()
    report = {"pbf": os.path.basename(args.pbf), "pbf_bytes": os.path.getsize(args.pbf),
              "osmium_version": getattr(osmium, "__version__", "?"),
              "run_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    print("[0/4] Tinh SHA-256 ...", flush=True)
    report["sha256"] = sha256_file(args.pbf)
    print("      ", report["sha256"], flush=True)

    # ---- Pass 1: quan he (ranh gioi tinh + dia diem dang quan he) ----
    print("[1/4] Doc cac quan he (ranh gioi, cong vien lon...) ...", flush=True)
    admin4 = []
    prov_rel = {}
    poi_rel = {}
    wanted_ways = set()
    for o in osmium.FileProcessor(args.pbf, osmium.osm.RELATION):
        if len(o.tags) == 0:
            continue
        ttype = o.tags.get("type")
        if ttype == "boundary" and o.tags.get("boundary") == "administrative" and o.tags.get("admin_level") == "4":
            name = o.tags.get("name", "")
            admin4.append({"id": o.id, "name": name})
            fn = fold(name)
            if any(k in fn for k in PROVINCE_KEYS):
                ways = [m.ref for m in o.members if m.type == "w" and m.role in ("outer", "inner", "")]
                prov_rel[o.id] = {"name": name, "ways": ways}
                wanted_ways.update(ways)
        elif ttype in ("multipolygon", "site"):
            d = {t.k: t.v for t in o.tags}
            c = classify(d)
            if c and best_name(d):
                ways = [m.ref for m in o.members if m.type == "w"]
                if ways:
                    poi_rel[o.id] = {"tags": d, "cls": c, "ways": ways}
                    wanted_ways.update(ways)
    prov_rel_ways = set(w for r in prov_rel.values() for w in r["ways"])
    report["admin_level_4_relations"] = admin4
    report["province_relations_used"] = {str(k): v["name"] for k, v in prov_rel.items()}
    print("      Tim thay %d quan he cap tinh, dung %d; %d dia diem dang quan he" %
          (len(admin4), len(prov_rel), len(poi_rel)), flush=True)

    # ---- Pass 2: node + way (co toa do) ----
    print("[2/4] Doc node va way (buoc nay lau nhat, vai phut) ...", flush=True)
    pois = []
    way_pts = {}      # way id -> (sumlon, sumlat, n) cho dia diem dang quan he
    bound_pts = {}    # way id -> [(lon,lat), ...] cho ranh gioi
    cnt = 0
    for o in osmium.FileProcessor(args.pbf, osmium.osm.NODE | osmium.osm.WAY).with_locations():
        cnt += 1
        if cnt % 20000000 == 0:
            print("      ... %d doi tuong" % cnt, flush=True)
        if isinstance(o, osmium.osm.Node):
            if len(o.tags) == 0:
                continue
            d = {t.k: t.v for t in o.tags}
            c = classify(d)
            if c is None or not best_name(d):
                continue
            if not o.location.valid():
                continue
            pois.append(("n", o.id, o.location.lon, o.location.lat, d, c))
        else:
            need_geom = o.id in wanted_ways
            has_tags = len(o.tags) > 0
            if not need_geom and not has_tags:
                continue
            d = None; c = None
            if has_tags:
                d = {t.k: t.v for t in o.tags}
                c = classify(d)
                if c is not None and not best_name(d):
                    c = None
            if not need_geom and c is None:
                continue
            pts = [(n.location.lon, n.location.lat) for n in o.nodes if n.location.valid()]
            if not pts:
                continue
            if o.id in prov_rel_ways:
                bound_pts[o.id] = pts
            sx = sum(p[0] for p in pts); sy = sum(p[1] for p in pts); k = len(pts)
            if need_geom:
                way_pts[o.id] = (sx, sy, k)
            if c is not None:
                pois.append(("w", o.id, sx / k, sy / k, d, c))
    for rid, r in poi_rel.items():
        sx = sy = k = 0
        for w in r["ways"]:
            if w in way_pts:
                a, b, n = way_pts[w]
                sx += a; sy += b; k += n
        if k:
            pois.append(("r", rid, sx / k, sy / k, r["tags"], r["cls"]))
    print("      %d dia diem tho (co ten)" % len(pois), flush=True)

    # ---- Ranh gioi ----
    print("[3/4] Dung ranh gioi HCM moi ...", flush=True)
    polys = {}
    for rid, r in prov_rel.items():
        lines = [LineString(bound_pts[w]) for w in r["ways"] if w in bound_pts and len(bound_pts[w]) >= 2]
        if not lines:
            continue
        merged = linemerge(lines)
        pl = list(polygonize(merged))
        if pl:
            polys[rid] = unary_union(pl)
    report["boundary_areas_km2"] = {prov_rel[r]["name"] + " (" + str(r) + ")": round(approx_area_km2(g), 1)
                                    for r, g in polys.items()}
    if polys:
        region = unary_union(list(polys.values()))
        report["region_bbox"] = [round(x, 4) for x in region.bounds]
        report["region_area_km2"] = round(approx_area_km2(region), 1)
        with open(os.path.join(args.out, "hcm_boundary.geojson"), "w", encoding="utf-8") as f:
            json.dump({"type": "Feature", "properties": {"name": "HCM moi (gop 3 tinh/thanh)"},
                       "geometry": mapping(region.simplify(0.0005))}, f)
    else:
        region = None
        print("      CANH BAO: khong dung duoc ranh gioi; se giu moi diem.", flush=True)
    report["boundary_ok"] = region is not None

    # ---- Loc va ghi ----
    print("[4/4] Loc theo ranh gioi va ghi file ...", flush=True)
    lon = np.array([p[2] for p in pois]); lat = np.array([p[3] for p in pois])
    if region is not None and len(pois):
        inside = shapely.contains_xy(region, lon, lat)
    else:
        inside = np.ones(len(pois), dtype=bool)
    report["pois_total_named"] = len(pois)
    report["pois_inside_region"] = int(inside.sum())
    cols = {k: [] for k in ["osm_type", "osm_id", "name", "group", "kind", "lon", "lat"] +
            [k.replace(":", "_") for k in KEEP if k not in ("name",)]}
    for i, (t, oid, x, y, d, c) in enumerate(pois):
        if not inside[i]:
            continue
        cols["osm_type"].append(t); cols["osm_id"].append(int(oid))
        cols["name"].append(best_name(d)); cols["group"].append(c[0]); cols["kind"].append(c[1])
        cols["lon"].append(float(x)); cols["lat"].append(float(y))
        for k in KEEP:
            if k == "name":
                continue
            cols[k.replace(":", "_")].append(d.get(k))
    table = pa.table(cols)
    pq.write_table(table, os.path.join(args.out, "osm_pois_hcm.parquet"))
    g = Counter(cols["group"]); kd = Counter(cols["kind"])
    report["count_by_group"] = dict(g)
    report["count_by_kind_top40"] = dict(kd.most_common(40))
    n = max(len(cols["name"]), 1)
    report["pct_with_opening_hours"] = round(100 * sum(1 for v in cols["opening_hours"] if v) / n, 1)
    report["pct_with_phone"] = round(100 * sum(1 for a, b in zip(cols["phone"], cols["contact_phone"]) if a or b) / n, 1)
    report["pct_with_website"] = round(100 * sum(1 for a, b in zip(cols["website"], cols["contact_website"]) if a or b) / n, 1)
    report["pct_with_fee_info"] = round(100 * sum(1 for a, b in zip(cols["fee"], cols["charge"]) if a or b) / n, 1)
    report["seconds"] = round(time.time() - t0, 1)
    with open(os.path.join(args.out, "osm_extract_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("XONG. Cac file da ghi vao:", args.out, flush=True)
    print(json.dumps({k: report[k] for k in ("pois_total_named", "pois_inside_region", "count_by_group", "region_area_km2") if k in report},
                     ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
