"""Routes AUTH — xử lý đăng ký, đăng nhập, đăng xuất, follow/unfollow.
Week1_Fase1: chưa có giao diện HTML, trả về JSON để test bằng Postman trước.
"""

from flask import request, jsonify
from flask_login import login_user, logout_user, login_required, current_user

from app.auth import auth_bp
from app.auth.utils import validate_password
from app.extensions import db
from app.models import User, Follow, Notification


# =========================================================
# ĐĂNG KÝ
# =========================================================

@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json()

    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    if not username or not email or not password:
        return jsonify({
            "error": "Thiếu username/email/password"
        }), 400

    password_error = validate_password(password)

    if password_error:
        return jsonify({
            "error": password_error
        }), 400

    if User.query.filter_by(username=username).first():
        return jsonify({
            "error": "Username đã tồn tại"
        }), 400

    user = User(
        username=username,
        email=email
    )

    user.set_password(password)

    db.session.add(user)
    db.session.commit()

    return jsonify({
        "message": "Đăng ký thành công",
        "user_id": user.id
    }), 201


# =========================================================
# ĐĂNG NHẬP
# =========================================================

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()

    username = data.get("username")
    password = data.get("password")

    user = User.query.filter_by(
        username=username
    ).first()

    if not user or not user.check_password(password):
        return jsonify({
            "error": "Sai username hoặc password"
        }), 401

    login_user(user)

    return jsonify({
        "message": "Đăng nhập thành công",
        "username": user.username
    })


# =========================================================
# ĐĂNG XUẤT
# =========================================================

@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()

    return jsonify({
        "message": "Đăng xuất thành công"
    })


# =========================================================
# FOLLOW USER
# =========================================================

@auth_bp.route("/follow/<int:user_id>", methods=["POST"])
@login_required
def follow(user_id):

    # Không được tự follow chính mình
    if current_user.id == user_id:
        return jsonify({
            "error": "Không thể tự follow chính mình"
        }), 400

    # Kiểm tra user được follow có tồn tại không
    followed_user = db.session.get(User, user_id)

    if not followed_user:
        return jsonify({
            "error": "Không tìm thấy user"
        }), 404

    # Kiểm tra đã follow user này chưa
    existing = Follow.query.filter_by(
        follower_id=current_user.id,
        followed_id=user_id
    ).first()

    if existing:
        return jsonify({
            "error": "Đã follow rồi"
        }), 400

    # Tạo quan hệ Follow
    new_follow = Follow(
        follower_id=current_user.id,
        followed_id=user_id
    )

    db.session.add(new_follow)

    # Tạo Notification cho người được follow
    notification = Notification(
        user_id=user_id,
        actor_id=current_user.id,
        notification_type="follow",
        post_id=None
    )

    db.session.add(notification)

    # Lưu Follow và Notification cùng lúc
    db.session.commit()

    return jsonify({
        "message": f"Đã follow user {user_id}"
    }), 201


# =========================================================
# UNFOLLOW USER
# =========================================================

@auth_bp.route("/unfollow/<int:user_id>", methods=["POST"])
@login_required
def unfollow(user_id):

    follow_record = Follow.query.filter_by(
        follower_id=current_user.id,
        followed_id=user_id
    ).first()

    if not follow_record:
        return jsonify({
            "error": "Chưa follow user này"
        }), 400

    db.session.delete(follow_record)
    db.session.commit()

    return jsonify({
        "message": f"Đã unfollow user {user_id}"
    })