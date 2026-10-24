"""
Kiểm thử phân hệ Quản trị (Admin Panel), Phân quyền chống Broken Access Control (BAC)
và Hệ thống Nhật ký An ninh (Security Logging).
"""
import pytest
from app.extensions import db
from app.models import User, Post, SecurityLog
from app.security_logging import log_security_event


def _login(client, username="testuser1", password="123456"):
    """Hàm phụ trợ đăng nhập bằng form chuẩn."""
    return client.post(
        "/login",
        data={
            "username": username,
            "password": password,
            "remember_me": False
        },
        headers={"Accept": "text/html"}
    )


def _create_admin(app, username="boss_admin", password="password123"):
    """Tạo tài khoản quản trị viên (is_admin = True)."""
    with app.app_context():
        admin = User.query.filter_by(username=username).first()
        if not admin:
            admin = User(
                username=username,
                email=f"{username}@example.com",
                profile_completed=True,
                is_admin=True
            )
            admin.set_password(password)
            db.session.add(admin)
            db.session.commit()
        else:
            admin.is_admin = True
            db.session.commit()
        return admin.id


def test_admin_guest_access_redirects_login(client):
    """Khách vãng lai (chưa đăng nhập) truy cập /admin/ bị chuyển hướng 302 về /login."""
    res = client.get("/admin/")
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]


def test_admin_normal_user_denied_and_logged(app, client):
    """Người dùng bình thường (is_admin = False) truy cập /admin/users bị 403 Forbidden
    và hệ thống tự động ghi nhận 1 bản ghi ACCESS_DENIED_403 vào bảng SecurityLog."""
    _login(client, username="testuser1", password="123456")

    with app.app_context():
        initial_count = SecurityLog.query.filter_by(event_type="ACCESS_DENIED_403").count()

    res = client.get("/admin/users")
    assert res.status_code == 403

    with app.app_context():
        new_count = SecurityLog.query.filter_by(event_type="ACCESS_DENIED_403").count()
        assert new_count == initial_count + 1

        last_log = SecurityLog.query.filter_by(event_type="ACCESS_DENIED_403").order_by(SecurityLog.id.desc()).first()
        assert last_log.status_code == 403
        assert last_log.endpoint == "/admin/users"
        assert last_log.action_taken == "BLOCKED"


def test_admin_access_granted_for_admin_user(app, client):
    """Admin thật (is_admin = True) truy cập /admin/ và /admin/users nhận 200 OK."""
    _create_admin(app, username="superadmin", password="password123")
    _login(client, username="superadmin", password="password123")

    res = client.get("/admin/")
    assert res.status_code == 200
    assert "Tổng quan hệ thống" in res.data.decode("utf-8")

    res_users = client.get("/admin/users")
    assert res_users.status_code == 200
    assert "Quản lý User" in res_users.data.decode("utf-8")


def test_admin_toggle_admin_and_prevent_self_demote(app, client):
    """Admin có thể cấp quyền cho user khác, nhưng không thể tự tước quyền của chính mình."""
    admin_id = _create_admin(app, username="master_admin", password="password123")
    _login(client, username="master_admin", password="password123")

    with app.app_context():
        target = User.query.filter_by(username="testuser2").first()
        target_id = target.id
        assert target.is_admin is False

    # Cấp quyền admin cho testuser2
    res = client.post(f"/admin/users/{target_id}/toggle-admin", follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        target_updated = db.session.get(User, target_id)
        assert target_updated.is_admin is True

    # Tự bỏ quyền của chính mình -> Hệ thống cảnh báo và từ chối
    res_self = client.post(f"/admin/users/{admin_id}/toggle-admin", follow_redirects=True)
    assert "Không thể tự bỏ quyền admin của chính mình" in res_self.data.decode("utf-8")

    with app.app_context():
        self_admin = db.session.get(User, admin_id)
        assert self_admin.is_admin is True


def test_admin_toggle_ban_user(app, client):
    """Admin có thể khóa và mở khóa tài khoản người dùng."""
    _create_admin(app, username="moderator", password="password123")
    _login(client, username="moderator", password="password123")

    with app.app_context():
        target = User.query.filter_by(username="testuser1").first()
        target_id = target.id
        assert getattr(target, "is_banned", False) is False

    # Khóa tài khoản
    client.post(f"/admin/users/{target_id}/toggle-ban", follow_redirects=True)
    with app.app_context():
        assert db.session.get(User, target_id).is_banned is True

    # Mở khóa tài khoản
    client.post(f"/admin/users/{target_id}/toggle-ban", follow_redirects=True)
    with app.app_context():
        assert db.session.get(User, target_id).is_banned is False


def test_admin_security_logs_view_and_clear(app, client):
    """Trang /admin/security-logs hiển thị nhật ký bảo mật và nút reset demo xóa sạch dữ liệu."""
    _create_admin(app, username="security_officer", password="password123")
    _login(client, username="security_officer", password="password123")

    with app.app_context():
        # Tạo sẵn các sự kiện mẫu
        log_security_event("DDOS_RATE_LIMIT", severity="WARNING", status_code=429)
        log_security_event("SQLI_DETECTED", severity="CRITICAL", status_code=400, payload_snippet="' OR 1=1 --")
        log_security_event("XSS_DETECTED", severity="CRITICAL", status_code=400, payload_snippet="<script>alert(1)</script>")
        count_before = SecurityLog.query.count()
        assert count_before >= 3

    # Truy cập trang xem logs
    res = client.get("/admin/security-logs")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Nhật ký An ninh" in html
    assert "DDoS / Rate Limit" in html

    # Lọc theo loại sự kiện
    res_filter = client.get("/admin/security-logs?event_type=SQLI_DETECTED")
    assert res_filter.status_code == 200

    # Xóa nhật ký demo
    res_clear = client.post("/admin/security-logs/clear", follow_redirects=True)
    assert res_clear.status_code == 200
    assert "Đã xóa" in res_clear.data.decode("utf-8")

    with app.app_context():
        assert SecurityLog.query.count() == 0


def test_admin_demo_bac_vulnerable_flag(app, client):
    """Khi cờ DEMO_BAC_VULNERABLE = True, người dùng thường có thể lọt vào trang admin (mô phỏng lỗi)."""
    app.config["DEMO_BAC_VULNERABLE"] = True
    try:
        _login(client, username="testuser1", password="123456")
        res = client.get("/admin/users")
        # Do bật cờ giả lập lỗ hổng, request không bị 403 mà được render
        assert res.status_code == 200
    finally:
        app.config["DEMO_BAC_VULNERABLE"] = False


def test_admin_delete_post_and_itinerary_cascade(app, client):
    """Admin xóa bài viết hoặc lịch trình đã có tương tác (Like, Comment, Repost)
    sẽ xóa sạch dữ liệu liên quan qua delete_post_cascade / delete_itinerary_cascade mà không lỗi FK."""
    from app.models import Like, Comment, Itinerary
    _create_admin(app, username="cascade_admin", password="password123")
    _login(client, username="cascade_admin", password="password123")

    with app.app_context():
        u = User.query.filter_by(username="testuser1").first()
        p = Post(user_id=u.id, caption="Bài viết có tương tác để test xóa cascade", visibility="public")
        db.session.add(p)
        db.session.flush()
        repost = Post(user_id=u.id, caption="Repost", original_post_id=p.id, visibility="public")
        it = Itinerary(user_id=u.id, title="Lịch trình có tương tác", destination="Đà Lạt", visibility="public")
        db.session.add_all([repost, it])
        db.session.flush()

        db.session.add_all([
            Like(user_id=u.id, post_id=p.id),
            Comment(user_id=u.id, post_id=p.id, content="Bình luận test"),
            Like(user_id=u.id, itinerary_id=it.id),
            Comment(user_id=u.id, itinerary_id=it.id, content="Bình luận lịch trình"),
        ])
        db.session.commit()
        post_id, repost_id, it_id = p.id, repost.id, it.id

    res_p = client.post(f"/admin/posts/{post_id}/delete", follow_redirects=True)
    assert res_p.status_code == 200

    res_it = client.post(f"/admin/itineraries/{it_id}/delete", follow_redirects=True)
    assert res_it.status_code == 200

    with app.app_context():
        assert db.session.get(Post, post_id) is None
        assert db.session.get(Post, repost_id) is None
        assert Like.query.filter_by(post_id=post_id).count() == 0
        assert Comment.query.filter_by(post_id=post_id).count() == 0
        assert db.session.get(Itinerary, it_id) is None
        assert Like.query.filter_by(itinerary_id=it_id).count() == 0
        assert Comment.query.filter_by(itinerary_id=it_id).count() == 0
