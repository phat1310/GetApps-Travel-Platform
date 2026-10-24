"""
Kiểm thử chính sách xác thực và bảo vệ tài nguyên đối với Khách vãng lai (Chưa đăng nhập).
Hệ thống bắt buộc xác thực (@login_required) đối với các trang nghiệp vụ cá nhân,
bảng tin, tạo bài, bình luận... và chuyển hướng 302 về /login hoặc trả về 401 JSON.
"""
import pytest

from app.extensions import db
from app.models import Post, User


@pytest.fixture
def private_post(app, users):
    with app.app_context():
        u = User.query.filter_by(username="testuser1").first()
        p = Post(user_id=u.id, caption="BAI RIENG TU BI MAT", visibility="private")
        db.session.add(p)
        db.session.commit()
        return p.id


def test_guest_feed_redirects_to_login(client):
    """Khách chưa login truy cập /locations/feed bị chuyển hướng 302 về /login."""
    res = client.get("/locations/feed")
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]


def test_logged_in_user_sees_feed(client, users):
    """Người dùng đã đăng nhập truy cập /locations/feed nhận 200 OK và thấy bảng tin."""
    from tests.test_frontend import login_user
    login_user(client)
    res = client.get("/locations/feed")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "Bảng tin" in html


def test_guest_post_access_requires_login(client, users, post, private_post):
    """Khách chưa login truy cập link bài viết bị yêu cầu đăng nhập."""
    assert client.get(f"/locations/p/{post.id}").status_code == 302
    assert client.get(f"/locations/p/{private_post}").status_code == 302
    assert client.get(f"/locations/posts/{post.id}").status_code == 302


def test_guest_public_routes_allow_access(client, users):
    """Các route công khai như /plans và /search cho phép khách tìm kiếm."""
    for url in ("/plans", "/search?q=hue"):
        res = client.get(url)
        assert res.status_code == 200, url
    # Các route nhạy cảm /itineraries/feed yêu cầu login
    assert client.get("/locations/itineraries/feed").status_code == 302


def test_guest_feed_json_returns_unauthorized(client, users, post, private_post):
    """Khách gọi API feed JSON chưa xác thực nhận chuyển hướng 302 hoặc mã 401."""
    res = client.get("/locations/feed?format=json", headers={"Accept": "application/json"})
    assert res.status_code in (302, 401)


@pytest.mark.parametrize("url", ["/notifications", "/settings", "/locations/upload", "/plans/create", "/profile", "/chat/conversations"])
def test_guest_pages_needing_account_redirect_to_login(client, url):
    r = client.get(url)
    assert r.status_code in (302, 404), url
    if r.status_code == 302:
        assert "/login" in r.headers["Location"]


@pytest.mark.parametrize("method,url", [
    ("post", "/locations/posts/1/like"), ("post", "/locations/posts/1/comments"), ("post", "/locations/posts/1/save"),
    ("post", "/locations/posts/1/share"), ("post", "/locations/posts/1/repost"), ("post", "/follow/1"),
    ("post", "/locations/upload"), ("post", "/locations/itineraries"),
])
def test_guest_actions_get_json_401(client, method, url):
    r = getattr(client, method)(url, json={})
    assert r.status_code == 401, url
    j = r.get_json()
    assert j["login_required"] is True and "/login" in j["login_url"]


def test_fetch_style_get_also_json_401(client):
    r = client.get("/notifications", headers={"Sec-Fetch-Mode": "cors"})
    assert r.status_code == 401 and r.get_json()["login_required"] is True


def test_navigation_get_keeps_next_param(client):
    r = client.get("/notifications")
    assert r.status_code == 302 and "next=" in r.headers["Location"]
