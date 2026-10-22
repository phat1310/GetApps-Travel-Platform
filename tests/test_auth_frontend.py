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
    """GET /register hiển thị giao diện đăng ký 200 OK và trường Họ và tên mới."""
    res = client.get("/register")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Tạo tài khoản GETAPPS" in html
    assert "register-form" in html
    assert "full_name" in html
    assert "Họ và tên" in html
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
    """POST /register qua form tạo tài khoản mới thành công và chuyển hướng về /login với flash success."""
    res = client.post(
        "/register",
        data={
            "full_name": "Nguyễn Văn Du Lịch",
            "username": "newtraveler",
            "email": "newtraveler@example.com",
            "password": "StrongPassword123!",
            "confirm_password": "StrongPassword123!",
            "agree_terms": "y"
        },
        headers={"Accept": "text/html"}
    )
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]

    # Kiểm tra chuyển hướng về trang /login có hiển thị thông báo thành công
    login_page = client.get(res.headers["Location"])
    assert login_page.status_code == 200
    assert "Đăng ký tài khoản thành công" in login_page.data.decode("utf-8")

    with client.application.app_context():
        user = User.query.filter_by(username="newtraveler").first()
        assert user is not None
        assert user.role == "user"
        assert user.full_name == "Nguyễn Văn Du Lịch"


def test_register_while_authenticated_clears_session_and_redirects_to_login(client, users):
    """Khi user đã đăng nhập mà đăng ký tài khoản mới thì xóa session cũ và chuyển về /login."""
    login_user(client, "testuser1")
    
    res = client.post(
        "/register",
        data={
            "full_name": "Brand New User",
            "username": "brandnewuser",
            "email": "brandnew@example.com",
            "password": "StrongPassword123!",
            "confirm_password": "StrongPassword123!",
            "agree_terms": "y"
        },
        headers={"Accept": "text/html"}
    )
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]
    assert "registered=1" in res.headers["Location"]

    # Đảm bảo trang đích là form login (không bị đá về feed)
    login_page = client.get(res.headers["Location"])
    assert login_page.status_code == 200
    assert "Đăng ký tài khoản thành công" in login_page.data.decode("utf-8")
    assert "login-form" in login_page.data.decode("utf-8")


def test_register_weak_password_rejected(client):
    """POST /register mật khẩu yếu (thiếu hoa, thường, ký tự đặc biệt hoặc < 8 ký tự) bị từ chối."""
    # 1. Quá ngắn (< 8 ký tự)
    res_short = client.post(
        "/register",
        data={
            "full_name": "Short Pass User",
            "username": "shortpass",
            "email": "shortpass@example.com",
            "password": "Aa1!",
            "confirm_password": "Aa1!",
            "agree_terms": "y"
        },
        headers={"Accept": "text/html"}
    )
    assert res_short.status_code == 400
    assert "Mật khẩu phải có ít nhất 8 ký tự" in res_short.data.decode("utf-8")

    # 2. Thiếu ký tự đặc biệt
    res_no_special = client.post(
        "/register",
        data={
            "full_name": "No Special User",
            "username": "nospecial",
            "email": "nospecial@example.com",
            "password": "Password1234",
            "confirm_password": "Password1234",
            "agree_terms": "y"
        },
        headers={"Accept": "text/html"}
    )
    assert res_no_special.status_code == 400
    assert "ký tự đặc biệt" in res_no_special.data.decode("utf-8")


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


def test_explore_page_get(client):
    """GET /explore đã được dọn dẹp theo thiết kế mới -> trả về 404 Not Found."""
    res = client.get("/explore")
    assert res.status_code == 404


def test_change_password_requires_login(client):
    """GET /change-password khi chưa đăng nhập bị chuyển hướng về /login."""
    res = client.get("/change-password")
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]


def test_change_password_form_render(client, users):
    """GET /change-password khi đã đăng nhập hiển thị form đổi mật khẩu."""
    login_user(client, "testuser1")
    res = client.get("/change-password")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Đổi mật khẩu" in html
    assert "Mật khẩu hiện tại" in html
    assert "Mật khẩu mới" in html
    assert "pwd-strength-bar" in html


def test_change_password_wrong_current(client, users):
    """POST /change-password sai mật khẩu hiện tại trả về lỗi 400."""
    login_user(client, "testuser1")
    res = client.post(
        "/change-password",
        data={
            "current_password": "WrongPassword123!",
            "new_password": "NewStrongPass123!",
            "confirm_new_password": "NewStrongPass123!"
        },
        headers={"Accept": "text/html"}
    )
    assert res.status_code == 400
    assert "Mật khẩu hiện tại không chính xác" in res.data.decode("utf-8")


def test_change_password_weak_new(client, users):
    """POST /change-password mật khẩu mới yếu (thiếu ký tự đặc biệt) trả về lỗi 400."""
    login_user(client, "testuser1")
    res = client.post(
        "/change-password",
        data={
            "current_password": "123456",
            "new_password": "NewPassword1234",
            "confirm_new_password": "NewPassword1234"
        },
        headers={"Accept": "text/html"}
    )
    assert res.status_code == 400
    assert "ký tự đặc biệt" in res.data.decode("utf-8")


def test_change_password_same_as_old(client, users):
    """POST /change-password mật khẩu mới trùng mật khẩu cũ trả về lỗi 400."""
    login_user(client, "testuser1")
    res = client.post(
        "/change-password",
        data={
            "current_password": "123456",
            "new_password": "123456",
            "confirm_new_password": "123456"
        },
        headers={"Accept": "text/html"}
    )
    assert res.status_code == 400


def test_change_password_success_and_login_with_new(client, users):
    """POST /change-password thành công cập nhật mật khẩu mới và có thể đăng nhập lại."""
    login_user(client, "testuser1")
    res = client.post(
        "/change-password",
        data={
            "current_password": "123456",
            "new_password": "BrandNewPassword123@",
            "confirm_new_password": "BrandNewPassword123@"
        },
        headers={"Accept": "text/html"}
    )
    assert res.status_code == 302
    assert "/profile" in res.headers["Location"]

    # Đăng xuất và đăng nhập lại bằng mật khẩu mới
    client.get("/logout")
    login_res = client.post(
        "/login",
        json={
            "username": "testuser1",
            "password": "BrandNewPassword123@"
        }
    )
    assert login_res.status_code == 200
    assert login_res.get_json()["message"] == "Đăng nhập thành công"


def test_change_password_api_json(client, users):
    """JSON API POST /change-password đổi mật khẩu thành công."""
    login_user(client, "testuser2")
    res = client.post(
        "/change-password",
        json={
            "current_password": "123456",
            "new_password": "VerySecret@2026",
            "confirm_new_password": "VerySecret@2026"
        }
    )
    assert res.status_code == 200
    assert res.get_json()["message"] == "Đổi mật khẩu thành công"


def test_forgot_password_page_get(client):
    """GET /forgot-password hiển thị form khôi phục mật khẩu 200 OK."""
    res = client.get("/forgot-password")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Quên mật khẩu?" in html
    assert "Qua Email" in html
    assert "Qua SĐT" in html


def test_forgot_password_unknown_target(client, users):
    """POST /forgot-password với email/SĐT không tồn tại trả về lỗi 400."""
    res = client.post(
        "/forgot-password",
        data={
            "method": "email",
            "target": "notfound@example.com"
        },
        headers={"Accept": "text/html"}
    )
    assert res.status_code == 400
    assert "Không tìm thấy tài khoản" in res.data.decode("utf-8")


def test_forgot_password_via_email_and_reset_flow(client, users):
    """Quy trình khôi phục mật khẩu hoàn chỉnh qua Email: Quên -> Nhận OTP -> Đặt lại MK mới -> Đăng nhập."""
    # 1. Gửi yêu cầu qua Email
    res_forgot = client.post(
        "/forgot-password",
        data={
            "method": "email",
            "target": "test1@example.com"
        },
        headers={"Accept": "text/html"}
    )
    assert res_forgot.status_code == 302
    assert "/reset-password" in res_forgot.headers["Location"]

    # 2. Kiểm tra trang reset-password hiển thị đúng
    with client.session_transaction() as sess:
        otp = sess.get("reset_otp")
        assert otp is not None
        assert len(otp) == 6

    res_get_reset = client.get("/reset-password")
    assert res_get_reset.status_code == 200
    assert "Xác thực OTP & Mật khẩu mới" in res_get_reset.data.decode("utf-8")

    # 3. Nhập sai OTP -> 400
    res_wrong_otp = client.post(
        "/reset-password",
        data={
            "otp": "000000",
            "new_password": "NewResetPassword123@",
            "confirm_new_password": "NewResetPassword123@"
        },
        headers={"Accept": "text/html"}
    )
    assert res_wrong_otp.status_code == 400
    assert "Mã xác thực OTP không chính xác" in res_wrong_otp.data.decode("utf-8")

    # 4. Nhập đúng OTP nhưng mật khẩu trùng mật khẩu cũ ("123456") -> 400
    res_same_pwd = client.post(
        "/reset-password",
        data={
            "otp": otp,
            "new_password": "123456",
            "confirm_new_password": "123456"
        },
        headers={"Accept": "text/html"}
    )
    assert res_same_pwd.status_code == 400

    # 5. Nhập đúng OTP và mật khẩu mới an toàn -> 302 chuyển về /login
    res_success = client.post(
        "/reset-password",
        data={
            "otp": otp,
            "new_password": "SuperSecureResetPassword@2026",
            "confirm_new_password": "SuperSecureResetPassword@2026"
        },
        headers={"Accept": "text/html"}
    )
    assert res_success.status_code == 302
    assert "/login" in res_success.headers["Location"]

    # 6. Đăng nhập lại với mật khẩu mới thành công
    res_login = client.post(
        "/login",
        json={
            "username": "testuser1",
            "password": "SuperSecureResetPassword@2026"
        }
    )
    assert res_login.status_code == 200
    assert res_login.get_json()["message"] == "Đăng nhập thành công"


def test_forgot_password_via_phone_and_resend_otp(client, users):
    """Quy trình khôi phục mật khẩu qua Số điện thoại (SĐT) và kiểm thử gửi lại OTP."""
    # Cập nhật số điện thoại cho user2
    with client.application.app_context():
        u2 = User.query.filter_by(username="testuser2").first()
        u2.phone_number = "0988776655"
        db.session.commit()

    # 1. Gửi yêu cầu qua SĐT
    res_forgot = client.post(
        "/forgot-password",
        data={
            "method": "phone",
            "target": "0988776655"
        },
        headers={"Accept": "text/html"}
    )
    assert res_forgot.status_code == 302
    assert "/reset-password" in res_forgot.headers["Location"]

    # Lấy OTP ban đầu
    with client.session_transaction() as sess:
        initial_otp = sess.get("reset_otp")
        assert initial_otp is not None

    # 2. Bấm Gửi lại mã OTP
    res_resend = client.post("/resend-otp")
    assert res_resend.status_code == 302
    assert "/reset-password" in res_resend.headers["Location"]

    # Lấy OTP mới
    with client.session_transaction() as sess:
        new_otp = sess.get("reset_otp")
        assert new_otp is not None

    # 3. Đặt lại mật khẩu thành công với OTP mới
    res_reset = client.post(
        "/reset-password",
        data={
            "otp": new_otp,
            "new_password": "PhoneUserNewPassword999!",
            "confirm_new_password": "PhoneUserNewPassword999!"
        },
        headers={"Accept": "text/html"}
    )
    assert res_reset.status_code == 302
    assert "/login" in res_reset.headers["Location"]


def test_forgot_password_api_json(client, users):
    """Kiểm thử JSON API cho chức năng Quên mật khẩu và Reset mật khẩu."""
    # 1. API Forgot Password
    res_forgot = client.post(
        "/forgot-password",
        json={"target": "test2@example.com"}
    )
    assert res_forgot.status_code == 200
    data = res_forgot.get_json()
    assert "otp" in data
    otp = data["otp"]

    # 2. API Reset Password
    res_reset = client.post(
        "/reset-password",
        json={
            "otp": otp,
            "new_password": "ApiResetPass#2026",
            "confirm_new_password": "ApiResetPass#2026"
        }
    )
    assert res_reset.status_code == 200
    assert res_reset.get_json()["message"] == "Đặt lại mật khẩu thành công"


def test_login_with_email_case_insensitive_and_whitespace(client, users):
    """Đăng nhập bằng Email không phân biệt chữ hoa/thường và tự động cắt khoảng trắng thừa."""
    # Test với email viết hoa và có khoảng trắng
    res = client.post(
        "/login",
        data={
            "username": "  TEST1@EXAMPLE.COM  ",
            "password": "123456",
            "remember_me": False
        },
        headers={"Accept": "text/html"}
    )
    assert res.status_code == 302
    assert "/locations/feed" in res.headers["Location"]

    # Đăng nhập qua JSON API với email chữ hoa
    res_json = client.post(
        "/login",
        json={
            "username": " Test1@Example.com ",
            "password": "123456"
        }
    )
    assert res_json.status_code == 200
    assert res_json.get_json()["username"] == "testuser1"


def test_login_with_phone_number(client, users, app):
    """Đăng nhập thành công bằng Số điện thoại đã đăng ký."""
    with app.app_context():
        u = User.query.filter_by(username="testuser1").first()
        u.phone_number = "0987654321"
        db.session.commit()

    res = client.post(
        "/login",
        data={
            "username": "0987654321",
            "password": "123456",
            "remember_me": False
        },
        headers={"Accept": "text/html"}
    )
    assert res.status_code == 302
    assert "/locations/feed" in res.headers["Location"]


def test_settings_page_get(client, users):
    """GET /settings hiển thị giao diện cài đặt tài khoản theo chuẩn Proposal GEs."""
    login_user(client, "testuser1", "123456")
    res = client.get("/settings")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Cài đặt tài khoản" in html
    assert "Biệt danh (Nickname)" in html
    assert "Nhãn (Tags)" in html
    assert "BẢO MẬT" in html
    assert "Đăng xuất" in html
    assert "Chọn Nhãn Hồ Sơ" in html


def test_settings_page_post_update(client, users, app):
    """POST /settings cập nhật thành công Biệt danh, Số điện thoại và Tiểu sử."""
    login_user(client, "testuser1", "123456")
    res = client.post(
        "/settings",
        data={
            "nickname": "Minh Đi Đâu",
            "profile_tag": "#nguoidulich",
            "email": "test1@example.com",
            "phone_number": "0987654321",
            "bio": "Đam mê xê dịch & chia sẻ trải nghiệm thực tế.",
            "avatar_url": ""
        },
        headers={"Accept": "text/html"}
    )
    assert res.status_code == 302
    assert "/settings" in res.headers["Location"]

    with app.app_context():
        u = User.query.filter_by(username="testuser1").first()
        assert u.nickname == "Minh Đi Đâu"
        assert u.phone_number == "0987654321"
        assert u.profile_tag == "#nguoidulich"
        assert "Đam mê xê dịch" in u.bio


def test_api_profile_tag_and_avatar(client, users, app):
    """Kiểm thử API AJAX cập nhật nhanh nhãn hồ sơ và ảnh đại diện."""
    login_user(client, "testuser1", "123456")

    # 1. Update tag
    res_tag = client.post(
        "/api/profile/tag",
        json={"tag": "dandiaphuong"}
    )
    assert res_tag.status_code == 200
    assert res_tag.get_json()["tag"] == "#dandiaphuong"

    # 2. Update avatar
    res_avatar = client.post(
        "/api/profile/avatar",
        json={"avatar_url": "https://example.com/minh_avatar.jpg"}
    )
    assert res_avatar.status_code == 200
    assert res_avatar.get_json()["avatar_url"] == "https://example.com/minh_avatar.jpg"

    with app.app_context():
        u = User.query.filter_by(username="testuser1").first()
        assert u.profile_tag == "#dandiaphuong"
        assert u.avatar_url == "https://example.com/minh_avatar.jpg"


def test_onboarding_flow(client, app):
    """Kiểm thử toàn bộ luồng Onboarding theo Slide 23 của Proposal."""
    # 1. Đăng ký tài khoản mới (profile_completed = False)
    res_reg = client.post(
        "/register",
        data={
            "full_name": "Phượt Thủ Hà Nội",
            "username": "onboarduser",
            "email": "onboard@example.com",
            "password": "StrongPassword123!",
            "confirm_password": "StrongPassword123!",
            "agree_terms": "y"
        },
        headers={"Accept": "text/html"}
    )
    assert res_reg.status_code == 302

    # 2. Đăng nhập -> vì profile_completed == False nên chuyển hướng sang /onboarding
    res_login = client.post(
        "/login",
        data={
            "username": "onboarduser",
            "password": "StrongPassword123!",
            "remember_me": False
        },
        headers={"Accept": "text/html"}
    )
    assert res_login.status_code == 302
    assert "/onboarding" in res_login.headers["Location"]

    # 3. GET /onboarding hiển thị giao diện Slide 23
    res_get = client.get("/onboarding")
    assert res_get.status_code == 200
    html = res_get.data.decode("utf-8")
    assert "Xin chào!" in html
    assert "Người du lịch" in html
    assert "Dân địa phương" in html
    assert "Đi phượt" in html
    assert "Hướng dẫn viên" in html
    assert "Người nổi tiếng" in html

    # 4. POST /onboarding lưu hồ sơ và nhãn thành công
    res_post = client.post(
        "/onboarding",
        data={
            "nickname": "Phượt Thủ Sài Gòn",
            "tags": ["phuot", "nguoi_du_lich"]
        },
        headers={"Accept": "text/html"}
    )
    assert res_post.status_code == 302
    assert "/locations/feed" in res_post.headers["Location"]

    with app.app_context():
        u = User.query.filter_by(username="onboarduser").first()
        assert u.profile_completed is True
        assert u.nickname == "Phượt Thủ Sài Gòn"
        assert "phuot" in u.tags

    # 5. Khi profile đã hoàn tất, truy cập lại /onboarding sẽ chuyển thẳng đến /locations/feed
    res_revisit = client.get("/onboarding")
    assert res_revisit.status_code == 302
    assert "/locations/feed" in res_revisit.headers["Location"]


def test_onboarding_skip(client, app):
    """Kiểm thử tính năng bỏ qua Onboarding."""
    client.post(
        "/register",
        data={
            "full_name": "Người Dùng Bỏ Qua",
            "username": "skipuser",
            "email": "skip@example.com",
            "password": "StrongPassword123!",
            "confirm_password": "StrongPassword123!",
            "agree_terms": "y"
        },
        headers={"Accept": "text/html"}
    )
    client.post(
        "/login",
        data={
            "username": "skipuser",
            "password": "StrongPassword123!"
        },
        headers={"Accept": "text/html"}
    )

    res_skip = client.get("/onboarding/skip")
    assert res_skip.status_code == 302
    assert "/locations/feed" in res_skip.headers["Location"]

    with app.app_context():
        u = User.query.filter_by(username="skipuser").first()
        assert u.profile_completed is True


def test_notifications_page(client, users):
    """Kiểm thử trang danh sách thông báo /notifications."""
    login_user(client, "testuser1", "123456")
    res = client.get("/notifications")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Thông báo" in html


def test_feed_proposal_ui_elements(client, users, post):
    """Kiểm thử Bảng tin feed.html đã bỏ Story, bỏ Bookmark và có Share Modal theo Proposal."""
    login_user(client, "testuser1", "123456")
    res = client.get("/locations/feed", headers={"Accept": "text/html"})
    assert res.status_code == 200
    html = res.data.decode("utf-8")

    # Có khung Top Bar & Pill Sidebar
    assert "st-top" in html
    assert "st-side" in html

    # Có Địa điểm nổi bật & Gợi ý kết nối
    assert "Địa điểm nổi bật" in html
    assert "Gợi ý kết nối" in html

    # Có Share Modal theo Slide 4
    assert "shareModal" in html
    assert "Tải về máy" in html
    assert "Đăng lại (Repost)" in html
    assert "Sao chép liên kết" in html

    # Không còn Story Bar
    assert "story-avatar" not in html
    assert "story-item" not in html




