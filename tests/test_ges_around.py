"""Test GEs Around: mô hình thời gian, validate đầu vào, bảo mật, kết quả tìm kiếm."""
import os

import pytest

from app import create_app
from app.extensions import db
from app.models import User
from app.ges_around import config as C, store
from app.ges_around.engine import travel_minutes, max_radius_km, haversine_km

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "ges_places_mini.csv")


@pytest.fixture
def gapp(tmp_path):
    store.invalidate()
    app = create_app({
        "TESTING": True, "WTF_CSRF_ENABLED": False,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'g.db'}",
        "GES_PLACES_CSV": FIXTURE, "GES_RATE_LIMIT": (1000, 60),
    })
    with app.app_context():
        u = User(username="gesuser", email="ges@example.com", profile_completed=True)
        u.set_password("123456")
        db.session.add(u)
        db.session.commit()
    yield app
    store.invalidate()
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def gclient(gapp):
    c = gapp.test_client()
    r = c.post("/login", data={"username": "gesuser", "password": "123456"}, follow_redirects=False)
    assert r.status_code in (200, 302), r.status_code
    return c


def body(**kw):
    b = {"free_minutes": 120, "origin": {"type": "area", "id": "ben-thanh"}, "needs": ["an_uong"], "budget": None}
    b.update(kw)
    return b


# ---------- mô hình thời gian ----------
def test_travel_model_monotonic_and_ordered():
    for v in C.VEHICLES:
        assert travel_minutes(v, 10) > travel_minutes(v, 5)
    assert travel_minutes("walk", 5) > travel_minutes("bike", 5) > travel_minutes("motorbike", 5)
    assert travel_minutes("bus", 5) > travel_minutes("car", 5)          # bus = car×1.4 + chờ


def test_radius_inverse_of_time():
    for v in C.VEHICLES:
        r = max_radius_km(v, 40)
        if r > 0:
            assert travel_minutes(v, r) == pytest.approx(40, abs=1e-6)


def test_haversine_known_distance():
    # Bến Thành -> Dinh Độc Lập ~ 1.1 km
    d = float(haversine_km(10.7725, 106.6980, 10.7769, 106.6954))
    assert 0.4 < d < 1.5


# ---------- quyền truy cập ----------
def test_requires_login(gapp):
    c = gapp.test_client()
    assert c.post("/ges-around/search", json=body()).status_code in (302, 401)
    assert c.get("/ges-around/areas").status_code in (302, 401)


def test_areas_endpoint(gclient):
    r = gclient.get("/ges-around/areas")
    j = r.get_json()
    assert r.status_code == 200 and len(j["areas"]) >= 30
    assert {a["group"] for a in j["areas"]} >= {"Trung tâm TP.HCM", "Bình Dương", "Bà Rịa – Vũng Tàu"}


# ---------- validate ----------
@pytest.mark.parametrize("patch", [
    {"free_minutes": 5}, {"free_minutes": 99999}, {"free_minutes": "abc"}, {"free_minutes": True},
    {"needs": []}, {"needs": ["hack"]}, {"needs": "an_uong"},
    {"budget": -1}, {"budget": 10**12}, {"budget": "rich"},
    {"origin": {"type": "area", "id": "khong-co"}}, {"origin": {"type": "area", "id": ["x"]}},
    {"origin": {"type": "gps", "lat": 21.0, "lng": 105.8}},          # Hà Nội: ngoài vùng
    {"origin": {"type": "gps", "lat": "10.7", "lng": 106.7}},
    {"origin": {"type": "gps", "lat": float("nan"), "lng": 106.7}},
    {"origin": {"type": "xyz"}}, {"origin": "ben-thanh"},
    {"vehicle": "rocket"},
])
def test_bad_input_rejected(gclient, patch):
    r = gclient.post("/ges-around/search", json=body(**patch))
    assert r.status_code == 400, (patch, r.get_json())


def test_non_json_rejected(gclient):
    assert gclient.post("/ges-around/search", data="x=1").status_code == 400


# ---------- kết quả ----------
def test_search_by_area_returns_nearby_only(gclient):
    j = gclient.post("/ges-around/search", json=body()).get_json()
    assert j["ok"] and set(j["vehicles"]) == set(C.VEHICLES)
    names = [x["name"] for x in j["vehicles"]["motorbike"]["groups"]["an_uong"]]
    assert "Quán Gần" in names and "Quán Xa" not in names
    item = next(x for x in j["vehicles"]["motorbike"]["groups"]["an_uong"] if x["name"] == "Quán Gần")
    assert item["total_min"] <= 120
    assert item["directions"].startswith("https://www.google.com/maps/dir/?api=1")
    assert "travelmode=two-wheeler" in item["directions"]
    assert "coordinates" not in j and "lat" not in j["origin"]


def test_round_trip_rule_respected(gclient):
    for free in (45, 60, 120, 480):
        j = gclient.post("/ges-around/search", json=body(free_minutes=free, needs=["an_uong", "giai_tri", "tham_quan"])).get_json()
        for v in j["vehicles"].values():
            for items in v["groups"].values():
                for it in items:
                    assert it["total_min"] <= free


def test_short_time_returns_empty_not_error(gclient):
    j = gclient.post("/ges-around/search", json=body(free_minutes=20, needs=["giai_tri"])).get_json()
    assert j["ok"] and j["vehicles"]["car"]["groups"]["giai_tri"] == []


def test_walk_reaches_less_than_motorbike(gclient):
    j = gclient.post("/ges-around/search", json=body(free_minutes=90, needs=["an_uong", "tham_quan", "giai_tri"])).get_json()
    assert j["vehicles"]["walk"]["total"] <= j["vehicles"]["motorbike"]["total"] <= j["vehicles"]["car"]["total"] + 5


def test_budget_filters_by_estimated_cost(gclient):
    j = gclient.post("/ges-around/search", json=body(budget=30000)).get_json()
    names = [x["name"] for x in j["vehicles"]["motorbike"]["groups"]["an_uong"]]
    assert "Nhà hàng Đắt" not in names and "Quán Gần" in names
    j2 = gclient.post("/ges-around/search", json=body(budget=None)).get_json()
    names2 = [x["name"] for x in j2["vehicles"]["motorbike"]["groups"]["an_uong"]]
    assert "Nhà hàng Đắt" in names2
    it = next(x for x in j2["vehicles"]["motorbike"]["groups"]["an_uong"] if x["name"] == "Nhà hàng Đắt")
    assert it["cost"]["estimated"] is True


def test_unsafe_web_scheme_dropped_and_names_raw(gclient):
    j = gclient.post("/ges-around/search", json=body(needs=["an_uong", "tham_quan"])).get_json()
    g = j["vehicles"]["motorbike"]["groups"]
    dear = next(x for x in g["an_uong"] if x["name"] == "Nhà hàng Đắt")
    assert dear["web"] is None                                   # javascript: bị loại
    near = next(x for x in g["an_uong"] if x["name"] == "Quán Gần")
    assert near["web"] == "https://example.com/a"
    # tên giữ nguyên dạng văn bản (client dùng textContent) — server không tự chèn HTML
    assert any(x["name"].startswith("<img") for x in g["tham_quan"])


def test_gps_inside_region_ok_and_not_stored(gclient, gapp):
    j = gclient.post("/ges-around/search", json=body(origin={"type": "gps", "lat": 10.7731, "lng": 106.6991})).get_json()
    assert j["ok"] and j["origin"]["name"].startswith("Vị trí")
    with gapp.app_context():
        from app.models import User
        cols = {c.name for c in User.__table__.columns}
        assert not ({"lat", "lng", "latitude", "longitude"} & cols)


def test_rate_limit(gapp):
    from app.ges_around import routes
    routes._hits.clear()
    gapp.config["GES_RATE_LIMIT"] = (2, 60)
    c = gapp.test_client()
    c.post("/login", data={"username": "gesuser", "password": "123456"})
    codes = [c.post("/ges-around/search", json=body()).status_code for _ in range(4)]
    assert codes[:2] == [200, 200] and 429 in codes[2:]


def test_seed_is_idempotent(gapp):
    with gapp.app_context():
        from app.models.ges_place import GesPlace
        store.invalidate()
        store.snapshot()
        n1 = GesPlace.query.count()
        assert n1 == 6 and store.seed_if_empty() == 0
        store.invalidate(); store.snapshot()
        assert GesPlace.query.count() == n1


def test_real_dataset_file_valid():
    import csv, gzip
    path = store.DEFAULT_CSV
    assert os.path.exists(path)
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) > 50000
    assert {r["grp"] for r in rows} == set(C.GROUPS)
    lo, lo2, hi, hi2 = C.REGION_BBOX
    assert all(lo <= float(r["lat"]) <= hi and lo2 <= float(r["lon"]) <= hi2 for r in rows)
    assert len({r["id"] for r in rows}) == len(rows)


# ---------- CSRF + giao diện ----------
def test_search_requires_csrf_token(tmp_path):
    import re
    store.invalidate()
    app = create_app({
        "TESTING": False, "WTF_CSRF_ENABLED": True, "SECRET_KEY": "k",
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'c.db'}", "GES_PLACES_CSV": FIXTURE,
    })
    with app.app_context():
        u = User(username="csrfu", email="csrf@example.com", profile_completed=True)
        u.set_password("123456")
        db.session.add(u)
        db.session.commit()
    c = app.test_client()
    tok = re.search(r'name="csrf-token" content="([^"]+)"', c.get("/login").get_data(as_text=True)).group(1)
    c.post("/login", data={"username": "csrfu", "password": "123456", "csrf_token": tok})
    assert c.post("/ges-around/search", json=body()).status_code == 400            # thiếu token
    assert c.post("/ges-around/search", json=body(), headers={"X-CSRFToken": tok}).status_code == 200
    store.invalidate()


def test_fab_only_for_logged_in_users(gapp, gclient):
    anon = gapp.test_client().get("/login").get_data(as_text=True)
    assert 'id="gaFab"' not in anon
    html = gclient.get("/locations/feed").get_data(as_text=True)
    assert 'id="gaFab"' in html and "js/ges-around.js" in html and "css/ges-around.css" in html
    assert "Có thời gian rảnh" not in html          # lời nhắn do JS vẽ, không hard-code trong HTML


def test_static_assets_served(gclient):
    assert gclient.get("/static/js/ges-around.js").status_code == 200
    assert gclient.get("/static/css/ges-around.css").status_code == 200


def test_frontend_never_injects_server_text_as_html():
    """Tên địa điểm từ OSM/Overture là dữ liệu không tin cậy: JS chỉ được dùng innerHTML cho SVG hằng số."""
    js = open(os.path.join(os.path.dirname(__file__), "..", "app", "static", "js", "ges-around.js"), encoding="utf-8").read()
    uses = [l for l in js.splitlines() if "html:" in l and "props[k]" not in l]
    assert uses and all("SVG_" in l or "html: ''" in l for l in uses), uses
    assert "insertAdjacentHTML" not in js and "document.write" not in js
