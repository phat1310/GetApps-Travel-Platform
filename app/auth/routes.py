"""Routes AUTH — đăng ký, đăng nhập, đăng xuất, follow/unfollow, onboarding,
đổi mật khẩu, thông tin liên hệ, CSRF token, đăng nhập Google (OAuth).
Trả về JSON để test bằng Postman trước.
"""
import json
import secrets
import urllib.error
import urllib.parse
import urllib.request

from flask import request, jsonify, session, redirect, url_for, current_app, render_template
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf.csrf import generate_csrf
from app.auth import auth_bp
from app.auth.utils import validate_password
from app.extensions import db
from app.models import User, Follow

FIXED_TAGS = {"dia_phuong", "phuot", "sang_tao_noi_dung", "chu_dia_diem"}

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


#Xử lý đăng ký người dùng mới
@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not username or not email or not password:
        return jsonify({"error": "Thiếu username/email/password"}), 400

    password_error = validate_password(password)
    if password_error:
        return jsonify({"error": password_error}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username đã tồn tại"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email đã tồn tại"}), 400

    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    login_user(user)
    return jsonify({
        "message": "Đăng ký thành công",
        "user_id": user.id,
        "profile_completed": user.profile_completed,
    }), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()   #kiểm tra tài khoản đã có
    if not user or not user.check_password(password):
        return jsonify({"error": "Sai username hoặc password"}), 401

    login_user(user)
    return jsonify({"message": "Đăng nhập thành công", "username": user.username})


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return jsonify({"message": "Đăng xuất thành công"})


@auth_bp.route("/follow/<int:user_id>", methods=["POST"])
@login_required
def follow(user_id):
    if current_user.id == user_id:
        return jsonify({"error": "Không thể tự follow chính mình"}), 400

    existing = Follow.query.filter_by(
        follower_id=current_user.id, followed_id=user_id).first()
    if existing:
        return jsonify({"error": "Đã follow rồi"}), 400

    f = Follow(follower_id=current_user.id, followed_id=user_id)
    db.session.add(f)
    db.session.commit()
    return jsonify({"message": f"Đã follow user {user_id}"}), 201


@auth_bp.route("/unfollow/<int:user_id>", methods=["POST"])
@login_required
def unfollow(user_id):
    f = Follow.query.filter_by(
        follower_id=current_user.id, followed_id=user_id).first()
    if not f:
        return jsonify({"error": "Chưa follow user này"}), 400

    db.session.delete(f)
    db.session.commit()
    return jsonify({"message": f"Đã unfollow user {user_id}"})


@auth_bp.route("/onboarding", methods=["POST"])
@login_required
def onboarding():
    data = request.get_json(silent=True) or {}
    nickname = data.get("nickname")
    avatar_url = data.get("avatar_url")
    tags = data.get("tags", [])

    if not isinstance(tags, list):
        return jsonify({"error": "tags phải là một danh sách"}), 400

    if len(tags) > 3:
        return jsonify({"error": "Chỉ được chọn tối đa 3 nhãn"}), 400

    invalid_tags = [t for t in tags if t not in FIXED_TAGS]
    if invalid_tags:
        return jsonify({
            "error": f"Nhãn không hợp lệ: {', '.join(invalid_tags)}",
            "allowed_tags": sorted(FIXED_TAGS),
        }), 400

    if nickname:
        current_user.nickname = nickname
    if avatar_url:
        current_user.avatar_url = avatar_url
    current_user.tags = ",".join(tags)
    current_user.profile_completed = True

    db.session.commit()

    return jsonify({
        "message": "Hoàn tất onboarding",
        "user": {
            "id": current_user.id,
            "nickname": current_user.nickname,
            "avatar_url": current_user.avatar_url,
            "tags": current_user.tags,
            "profile_completed": current_user.profile_completed,
        },
    })


@auth_bp.route("/change-password", methods=["POST"])
@login_required
def change_password():
    data = request.get_json(silent=True) or {}
    old_password = data.get("old_password")
    new_password = data.get("new_password")

    if not old_password or not new_password:
        return jsonify({"error": "Thiếu old_password/new_password"}), 400

    if not current_user.check_password(old_password):
        return jsonify({"error": "Mật khẩu cũ không đúng"}), 401

    if old_password == new_password:
        return jsonify({"error": "Mật khẩu mới phải khác mật khẩu cũ"}), 400

    password_error = validate_password(new_password)
    if password_error:
        return jsonify({"error": password_error}), 400

    current_user.set_password(new_password)
    db.session.commit()

    return jsonify({"message": "Đổi mật khẩu thành công"})


@auth_bp.route("/settings/contact", methods=["POST"])
@login_required
def update_contact():
    data = request.get_json(silent=True) or {}
    phone_number = data.get("phone_number")
    secondary_email = data.get("secondary_email")

    if not phone_number and not secondary_email:
        return jsonify({"error": "Cần cung cấp phone_number hoặc secondary_email"}), 400

    if secondary_email:
        if "@" not in secondary_email or "." not in secondary_email:
            return jsonify({"error": "secondary_email không hợp lệ"}), 400

        if secondary_email == current_user.email:
            return jsonify({"error": "secondary_email không được trùng với email chính"}), 400

        existing = User.query.filter(
            (User.email == secondary_email) | (User.secondary_email == secondary_email)
        ).filter(User.id != current_user.id).first()
        if existing:
            return jsonify({"error": "Email này đã được dùng bởi tài khoản khác"}), 400

        current_user.secondary_email = secondary_email

    if phone_number:
        current_user.phone_number = phone_number

    db.session.commit()

    return jsonify({
        "message": "Cập nhật thông tin liên hệ thành công",
        "user": {
            "phone_number": current_user.phone_number,
            "secondary_email": current_user.secondary_email,
        },
    })


@auth_bp.route("/csrf-token", methods=["GET"])
def csrf_token():
    return jsonify({"csrf_token": generate_csrf()})


# ---------------------------------------------------------------------------
# Đăng nhập bằng Google (OAuth 2.0 Authorization Code) — chỉ dùng thư viện chuẩn
# ---------------------------------------------------------------------------

def _google_exchange_code(code, redirect_uri):
    """Đổi authorization code lấy access_token từ Google."""
    body = urllib.parse.urlencode({
        "code": code,
        "client_id": current_app.config["GOOGLE_CLIENT_ID"],
        "client_secret": current_app.config["GOOGLE_CLIENT_SECRET"],
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }).encode()
    req = urllib.request.Request(GOOGLE_TOKEN_URL, data=body, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def _google_get_userinfo(access_token):
    """Lấy thông tin người dùng (sub, email, name, picture) từ Google."""
    req = urllib.request.Request(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def _unique_username(base):
    """Sinh username chưa bị dùng, thêm số phía sau nếu trùng."""
    base = (base or "user")[:50]
    username = base
    n = 1
    while User.query.filter_by(username=username).first():
        n += 1
        username = f"{base}{n}"
    return username


@auth_bp.route("/auth/google/login", methods=["GET"])
def google_login():
    if not current_app.config.get("GOOGLE_CLIENT_ID") or not current_app.config.get("GOOGLE_CLIENT_SECRET"):
        return jsonify({"error": "Chưa cấu hình GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET trong .env"}), 500

    state = secrets.token_urlsafe(32)
    session["google_oauth_state"] = state

    params = urllib.parse.urlencode({
        "client_id": current_app.config["GOOGLE_CLIENT_ID"],
        "redirect_uri": url_for("auth.google_callback", _external=True),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
    })
    return redirect(f"{GOOGLE_AUTH_URL}?{params}")


@auth_bp.route("/auth/google/callback", methods=["GET"])
def google_callback():
    if request.args.get("error"):
        return jsonify({"error": "Bạn đã hủy đăng nhập Google"}), 400

    expected_state = session.pop("google_oauth_state", None)
    if not expected_state or request.args.get("state") != expected_state:
        return jsonify({"error": "State không hợp lệ, vui lòng đăng nhập lại"}), 400

    code = request.args.get("code")
    if not code:
        return jsonify({"error": "Thiếu authorization code"}), 400

    redirect_uri = url_for("auth.google_callback", _external=True)
    try:
        token = _google_exchange_code(code, redirect_uri)
        userinfo = _google_get_userinfo(token["access_token"])
    except urllib.error.HTTPError as e:
        current_app.logger.error("Google HTTPError %s: %s", e.code, e.read().decode(errors="replace"))
        return jsonify({"error": "Google từ chối yêu cầu, vui lòng thử lại"}), 502
    except (urllib.error.URLError, KeyError, ValueError) as e:
        current_app.logger.error("Google OAuth lỗi: %r", e)
        return jsonify({"error": "Không kết nối được với Google, vui lòng thử lại"}), 502

    google_id = userinfo.get("sub")
    email = userinfo.get("email")
    if not google_id or not email or not userinfo.get("email_verified"):
        return jsonify({"error": "Tài khoản Google chưa có email đã xác minh"}), 400

    user = User.query.filter_by(google_id=google_id).first()

    if not user:
        user = User.query.filter_by(email=email).first()
        if user:
            # Trùng email với tài khoản thường -> gắn google_id vào tài khoản đó
            user.google_id = google_id
        else:
            user = User(
                username=_unique_username(email.split("@")[0]),
                email=email,
                google_id=google_id,
                avatar_url=userinfo.get("picture"),
                nickname=userinfo.get("name"),
            )
            user.set_password(secrets.token_urlsafe(32))  # mật khẩu ngẫu nhiên, không ai biết
            db.session.add(user)
        db.session.commit()

    login_user(user)
    return jsonify({
        "message": "Đăng nhập Google thành công",
        "user_id": user.id,
        "username": user.username,
        "profile_completed": user.profile_completed,
    })


@auth_bp.route("/settings", methods=["GET"])
@login_required
def settings_page():
    return render_template("settings.html")