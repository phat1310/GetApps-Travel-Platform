"""Kho dữ liệu GEs Around: seed bảng ges_places từ CSV nén + snapshot numpy trong bộ nhớ để tìm nhanh.

- Seed LAZY (lần tìm kiếm đầu tiên khi bảng trống) để không làm chậm khởi động app / bộ test; idempotent
  (bảng đã có dữ liệu thì bỏ qua; nhiều worker chạy cùng lúc thì dòng trùng id bị bỏ qua).
- Snapshot: mảng numpy lat/lon/... nạp 1 lần từ DB, dùng chung cho mọi request (có khoá).
"""
import csv
import gzip
import os
import threading

import numpy as np
from flask import current_app
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.ges_place import GesPlace

_lock = threading.Lock()
_snap = {"key": None, "data": None}
DEFAULT_CSV = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "ges_places.csv.gz")


def _csv_path():
    return current_app.config.get("GES_PLACES_CSV") or DEFAULT_CSV


def _open_csv(path):
    if path.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", newline="")
    return open(path, "r", encoding="utf-8", newline="")


def seed_if_empty():
    """Nạp CSV vào bảng ges_places nếu bảng đang trống. Trả về số dòng đã thêm."""
    if db.session.execute(select(func.count()).select_from(GesPlace)).scalar():
        return 0
    path = _csv_path()
    if not os.path.exists(path):
        current_app.logger.warning("GEs Around: không thấy file dữ liệu %s", path)
        return 0
    added, batch = 0, []

    def flush():
        nonlocal added, batch
        if not batch:
            return
        try:
            db.session.execute(GesPlace.__table__.insert(), batch)
            db.session.commit()
            added += len(batch)
        except IntegrityError:           # worker khác đã seed xong
            db.session.rollback()
        batch = []

    with _open_csv(path) as f:
        for r in csv.DictReader(f):
            try:
                row = dict(
                    id=r["id"][:24], name=r["name"][:200], grp=r["grp"], kind=(r.get("kind") or "")[:80],
                    lat=float(r["lat"]), lon=float(r["lon"]), src=(r.get("src") or "osm")[:10],
                    brand=(r.get("brand") or None), addr=(r.get("addr") or None),
                    hours=(r.get("hours") or None) and r["hours"][:200],
                    web=(r.get("web") or None) and r["web"][:300],
                    pop=int(r.get("pop") or 0), price_min=None, price_max=None,
                )
            except (KeyError, ValueError):
                continue
            batch.append(row)
            if len(batch) >= 5000:
                flush()
    flush()
    invalidate()
    return added


def invalidate():
    with _lock:
        _snap["key"] = None
        _snap["data"] = None


def snapshot():
    """Trả về dict các mảng đã nạp từ DB (cache theo URI database)."""
    key = str(db.engine.url)
    with _lock:
        if _snap["key"] == key and _snap["data"] is not None:
            return _snap["data"]
    seed_if_empty()
    rows = db.session.execute(select(
        GesPlace.id, GesPlace.name, GesPlace.grp, GesPlace.kind, GesPlace.lat, GesPlace.lon, GesPlace.src,
        GesPlace.addr, GesPlace.hours, GesPlace.web, GesPlace.pop, GesPlace.price_min, GesPlace.price_max,
    )).all()
    data = {
        "n": len(rows),
        "id": [r[0] for r in rows], "name": [r[1] for r in rows], "grp": np.array([r[2] for r in rows], dtype="U12"),
        "kind": [r[3] for r in rows],
        "lat": np.array([r[4] for r in rows], dtype=np.float64), "lon": np.array([r[5] for r in rows], dtype=np.float64),
        "src": [r[6] for r in rows], "addr": [r[7] for r in rows], "hours": [r[8] for r in rows],
        "web": [r[9] for r in rows], "pop": np.array([r[10] for r in rows], dtype=np.int8),
        "pmin": [r[11] for r in rows], "pmax": [r[12] for r in rows],
    }
    with _lock:
        _snap["key"], _snap["data"] = key, data
    return data
