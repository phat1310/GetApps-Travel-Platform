"""Chế độ KHÁCH: xem bảng tin / bài viết / lịch trình / tìm kiếm không cần đăng nhập;
đăng bài, thông báo, tin nhắn, cài đặt, thích, bình luận... vẫn bắt đăng nhập."""
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


def test_guest_feed_shows_public_posts_and_guest_card(client, users, post, private_post):
    html = client.get("/locations/feed").get_data(as_text=True)
    assert "Test post" in html
    assert "BAI RIENG TU BI MAT" not in html                   # bài riêng tư không lộ ra cho khách
    assert "Góc cá nhân chưa hoạt động" in html and "Kích hoạt ngay" in html
    assert "st-guest-login" in html and "st-guest-reg" in html  # nút Đăng nhập / Đăng ký thay avatar
    assert 'class="st-top-avatar"' not in html and "Gợi ý kết nối" not in html


def test_guest_gates_on_restricted_buttons(client):
    html = client.get("/locations/feed").get_data(as_text=True)
    for what in ("đăng bài", "xem thông báo", "nhắn tin", "cài đặt"):
        assert f'data-login-gate="{what}"' in html
    assert 'id="gaFab"' not in html                             # GEs Around chỉ cho người đã đăng nhập


def test_logged_in_user_sees_avatar_not_guest_ui(client, users):
    from tests.test_frontend import login_user
    login_user(client)
    html = client.get("/locations/feed").get_data(as_text=True)
    assert 'class="st-top-avatar"' in html and 'class="st-guest-btn st-guest-login"' not in html and "data-login-gate" not in html
    assert "Góc cá nhân chưa hoạt động" not in html


def test_guest_can_view_public_post_not_private(client, users, post, private_post):
    assert client.get(f"/locations/p/{post.id}").status_code == 200
    assert client.get(f"/locations/p/{private_post}").status_code == 404
    assert client.get(f"/locations/posts/{post.id}").status_code == 200
    assert client.get(f"/locations/posts/{private_post}").status_code == 403
    assert client.get(f"/locations/posts/{post.id}/comments").status_code == 200
    assert client.get(f"/locations/posts/{private_post}/comments").status_code == 403


def test_guest_browse_search_plans_itineraries(client, users):
    for url in ("/plans", "/search?q=hue", "/explore", "/locations/itineraries/feed", "/locations/search?q=hue"):
        assert client.get(url).status_code == 200, url
    assert client.get("/locations/itineraries/999999").status_code == 404


def test_guest_feed_json_has_only_public(client, users, post, private_post):
    j = client.get("/locations/feed?format=json").get_json()
    caps = [p.get("caption") for p in j["feed"]]
    assert "Test post" in caps and "BAI RIENG TU BI MAT" not in caps


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
