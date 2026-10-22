"""
Tests for Rate Limiting (Flask-Limiter) & DDoS / Brute-force Protection.
Kiểm thử các kịch bản:
- Bình thường: request hợp lệ thành công (200 / 302)
- Brute-force / Spam POST /login: vượt quá giới hạn -> trả về 429 Too Many Requests
- API / JSON 429: trả về JSON có cấu trúc rõ ràng kèm thông báo lỗi
- Trình duyệt HTML 429: render giao diện 429.html thân thiện
- Spam gửi OTP /resend-otp: bị chặn với 429
- Kịch bản mô phỏng DDoS burst: các request dồn dập bị chặn với 429
"""

import pytest
from app import create_app
from app.extensions import db, limiter
from app.models import User


@pytest.fixture
def rate_limit_app(tmp_path):
    """Tạo app test với RATELIMIT_ENABLED = True và storage riêng biệt để test rate limit."""
    db_path = tmp_path / "test_ratelimit.db"
    test_app = create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "RATELIMIT_ENABLED": True,
        "RATELIMIT_STORAGE_URI": "memory://",
        "RATELIMIT_STRATEGY": "fixed-window",
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
    })

    with test_app.app_context():
        db.create_all()
        # Tạo sẵn tài khoản kiểm thử
        user = User(username="testlimiter", email="limiter@example.com", profile_completed=True)
        user.set_password("SecurePass123@")
        db.session.add(user)
        db.session.commit()

        # Đặt lại bộ đếm limiter cho test sạch sẽ
        limiter.reset()

    yield test_app

    with test_app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def rate_client(rate_limit_app):
    return rate_limit_app.test_client()


def test_login_rate_limiting_blocks_bruteforce(rate_client):
    """Gửi dồn dập POST /login (mô phỏng brute-force mật khẩu) -> bị chặn với 429."""
    # POST /login giới hạn 10 per minute
    statuses = []
    for i in range(12):
        res = rate_client.post(
            "/login",
            json={"username": "testlimiter", "password": f"WrongPass{i}"},
            headers={"Content-Type": "application/json"}
        )
        statuses.append(res.status_code)

    # Các request đầu bị 401 (sai pass), nhưng khi vượt giới hạn 10 lần phải bị 429
    assert 401 in statuses[:10]
    assert statuses[-1] == 429


def test_rate_limit_json_response_structure(rate_client):
    """Request JSON vượt quá giới hạn nhận về JSON 429 chuẩn mực."""
    for _ in range(11):
        res = rate_client.post(
            "/login",
            json={"username": "testlimiter", "password": "wrong"},
            headers={"Content-Type": "application/json"}
        )

    assert res.status_code == 429
    assert res.is_json
    data = res.get_json()
    assert data["status"] == 429
    assert "Quá nhiều yêu cầu" in data["error"] or "Rate Limit Exceeded" in data["error"]


def test_rate_limit_html_browser_response(rate_client):
    """Trình duyệt web (Accept: text/html) vượt giới hạn render giao diện 429.html."""
    for _ in range(11):
        res = rate_client.post(
            "/login",
            data={"username": "testlimiter", "password": "wrong"},
            headers={"Accept": "text/html"}
        )

    assert res.status_code == 429
    html = res.data.decode("utf-8")
    assert "429" in html
    assert "Tần suất gửi yêu cầu quá nhanh" in html or "Rate Limit Exceeded" in html


def test_resend_otp_rate_limiting(rate_client):
    """Gửi lại mã OTP liên tục (/resend-otp) bị chặn ở giới hạn 3 per minute."""
    with rate_client.session_transaction() as sess:
        sess["reset_user_id"] = 1
        sess["reset_target"] = "test@example.com"
        sess["reset_method"] = "email"

    statuses = []
    for _ in range(5):
        res = rate_client.post("/resend-otp", json={})
        statuses.append(res.status_code)

    # 3 lần đầu thành công (200), từ lần thứ 4 trở đi phải bị 429
    assert 200 in statuses[:3]
    assert 429 in statuses[3:]


def test_get_login_page_not_blocked_by_post_limit(rate_client):
    """Người dùng load trang đăng nhập (GET) không bị tính vào giới hạn POST."""
    for _ in range(15):
        res = rate_client.get("/login")
        assert res.status_code == 200
