import io
from app.models import Post, Location, Photo
from app.extensions import db


def login_user(client, username="testuser1", password="123456"):
    return client.post(
        "/login",
        json={
            "username": username,
            "password": password
        }
    )


def test_root_index_redirect(client):
    """GET / chuyển hướng sang /locations/feed."""
    res = client.get("/")
    assert res.status_code == 302
    assert "/locations/feed" in res.headers["Location"]


def test_feed_unauthenticated(client):
    """Khách (chưa login) truy cập bảng tin bị chuyển hướng về /login."""
    res = client.get("/locations/feed")
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]


def test_feed_authenticated_html(client, users, post):
    """Đã login truy cập /locations/feed render HTML 200 OK kèm dữ liệu bài viết."""
    login_user(client)
    res = client.get("/locations/feed", headers={"Accept": "text/html"})
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Bảng tin" in html
    assert "GEs" in html
    assert "Test post" in html


def test_feed_json_api(client, users, post):
    """Gọi /locations/feed?format=json trả về định dạng JSON hợp lệ."""
    login_user(client)
    res = client.get("/locations/feed?format=json")
    assert res.status_code == 200
    data = res.get_json()
    assert "feed" in data
    assert len(data["feed"]) >= 1
    assert data["feed"][0]["caption"] == "Test post"


def test_upload_page_get(client):
    """GET /locations/upload chuyển hướng sang Feed kèm tham số mở hộp tạo bài (compose=post)."""
    login_user(client)
    res = client.get("/locations/upload")
    assert res.status_code == 302
    assert "compose=post" in res.headers["Location"]



def test_upload_post_form_submit(client):
    """POST /locations/upload với file ảnh tạo bài viết thành công."""
    login_user(client)
    data = {
        "images": (io.BytesIO(b"fake image data"), "trip.jpg"),
        "caption": "Chuyến đi Đà Lạt tuyệt vời #dalat",
        "location_name": "Đà Lạt"
    }
    res = client.post(
        "/locations/upload",
        data=data,
        content_type="multipart/form-data"
    )
    assert res.status_code in [201, 302]

    with client.application.app_context():
        new_post = Post.query.filter_by(caption="Chuyến đi Đà Lạt tuyệt vời #dalat").first()
        assert new_post is not None
        assert Photo.query.filter_by(post_id=new_post.id).count() >= 1


def test_location_autocomplete_aliases(client):
    """Kiểm tra cả 2 route tìm kiếm địa điểm /locations/search và /locations/locations/search."""
    login_user(client)

    with client.application.app_context():
        loc = Location(name="Hồ Tuyền Lâm", slug="ho-tuyen-lam")
        db.session.add(loc)
        db.session.commit()

    # Thử route /locations/search
    res1 = client.get("/locations/search?q=tuyen")
    assert res1.status_code == 200
    assert any("Tuyền Lâm" in l["name"] for l in res1.get_json()["locations"])

    # Thử route /locations/locations/search
    res2 = client.get("/locations/locations/search?q=tuyen")
    assert res2.status_code == 200
    assert any("Tuyền Lâm" in l["name"] for l in res2.get_json()["locations"])
