import pytest
from app.models import User
from app.extensions import db


def login_user(client, username="testuser1", password="123456"):
    return client.post(
        "/login",
        json={
            "username": username,
            "password": password
        }
    )


def test_login_page_get(client):
    """GET /login hiển thị giao diện đăng nhập 200 OK."""
    res = client.get("/login")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Chào mừng trở lại" in html
    assert "login-form" in html
    assert "username" in html


def test_register_page_get(client):
    """GET /register hiển thị giao diện đăng ký 200 OK."""
    res = client.get("/register")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Tạo tài khoản GETAPPS" in html
    assert "register-form" in html
    assert "email" in html


def test_login_form_post_success(client):
    """POST /login qua form thành công chuyển hướng về /locations/feed."""
    res = client.post(
        "/login",
        data={
            "username": "testuser1",
            "password": "123456",
            "remember_me": False
        },
        headers={"Accept": "text/html"}
    )
    assert res.status_code == 302
    assert "/locations/feed" in res.headers["Location"]


def test_login_form_post_invalid_credentials(client):
    """POST /login sai mật khẩu trả về 401 kèm thông báo lỗi."""
    res = client.post(
        "/login",
        data={
            "username": "testuser1",
            "password": "wrongpassword",
            "remember_me": False
        },
        headers={"Accept": "text/html"}
    )
    assert res.status_code == 401
    html = res.data.decode("utf-8")
    assert "không chính xác" in html


def test_register_form_post_success(client):
    """POST /register qua form tạo tài khoản mới thành công."""
    res = client.post(
        "/register",
        data={
            "username": "newtraveler",
            "email": "newtraveler@example.com",
            "password": "password123",
            "confirm_password": "password123",
            "role": "traveler",
            "agree_terms": "y"
        },
        headers={"Accept": "text/html"}
    )
    assert res.status_code == 302

    with client.application.app_context():
        user = User.query.filter_by(username="newtraveler").first()
        assert user is not None
        assert user.role == "traveler"


def test_profile_page_get(client, users, post):
    """GET /profile hiển thị trang cá nhân người dùng."""
    login_user(client, "testuser1")
    res = client.get("/profile")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "testuser1" in html
    assert "Bài viết" in html
    assert "Chỉnh sửa hồ sơ" in html


def test_profile_edit_post(client, users):
    """POST /profile/edit cập nhật thành công tiểu sử và số điện thoại."""
    login_user(client, "testuser1")
    res = client.post(
        "/profile/edit",
        data={
            "bio": "Đam mê khám phá các cung đường phượt Việt Nam",
            "phone_number": "0912345678",
            "role": "creator"
        }
    )
    assert res.status_code == 302

    with client.application.app_context():
        u = User.query.filter_by(username="testuser1").first()
        assert u.bio == "Đam mê khám phá các cung đường phượt Việt Nam"
        assert u.phone_number == "0912345678"
        assert u.role == "creator"


def test_logout_get_redirect(client):
    """GET /logout đăng xuất và chuyển hướng về /login."""
    login_user(client, "testuser1")
    res = client.get("/logout", headers={"Accept": "text/html"})
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]
