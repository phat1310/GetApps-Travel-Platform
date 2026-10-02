"""
Routes API — REST API dùng JWT, dành cho mobile app/client ngoài.
Các API trong file này sử dụng JWT để xác thực người dùng.
"""

from flask import jsonify, request
from flask_jwt_extended import (
    jwt_required,
    get_jwt_identity,
    create_access_token
)

from app.api import api_bp
from app.extensions import db
from app.models import User, Follow, SavedPost, Post, Photo


# =========================================================
# API LOGIN
# =========================================================

@api_bp.route("/login", methods=["POST"])
def api_login():
    data = request.get_json() or {}

    username = data.get("username")
    password = data.get("password")

    user = User.query.filter_by(
        username=username
    ).first()

    if not user or not user.check_password(password):
        return jsonify({
            "error": "Sai username hoặc password"
        }), 401

    access_token = create_access_token(
        identity=str(user.id)
    )

    return jsonify({
        "access_token": access_token
    }), 200


# =========================================================
# GET USER PROFILE
# =========================================================

@api_bp.route("/users/<int:user_id>", methods=["GET"])
@jwt_required()
def get_user(user_id):
    """
    Lấy thông tin profile của một user.

    Nếu tài khoản riêng tư:
    - Chính chủ vẫn xem được.
    - Người đang follow vẫn xem được.
    - Người chưa follow chỉ nhận được thông tin cơ bản.
    """

    current_user_id = int(get_jwt_identity())
    user = db.get_or_404(User, user_id)

    follower_count = Follow.query.filter_by(
        followed_id=user.id
    ).count()

    following_count = Follow.query.filter_by(
        follower_id=user.id
    ).count()

    is_owner = current_user_id == user.id

    is_following = Follow.query.filter_by(
        follower_id=current_user_id,
        followed_id=user.id
    ).first() is not None

    # Tài khoản private và người xem không phải owner/follower
    if user.is_private and not is_owner and not is_following:
        return jsonify({
            "id": user.id,
            "username": user.username,
            "nickname": user.nickname,
            "avatar_url": user.avatar_url,
            "is_private": True,
            "is_following": False,
            "follower_count": follower_count,
            "following_count": following_count,
            "profile_access": "private"
        }), 200

    # Public hoặc owner/follower được xem profile đầy đủ
    return jsonify({
        "id": user.id,
        "username": user.username,
        "nickname": user.nickname,
        "avatar_url": user.avatar_url,
        "bio": user.bio,
        "role": user.role,
        "is_private": user.is_private,
        "is_following": is_following,
        "follower_count": follower_count,
        "following_count": following_count,
        "profile_access": "full"
    }), 200


# =========================================================
# UPDATE USER PROFILE
# =========================================================

@api_bp.route("/users/me", methods=["PATCH", "PUT"])
@jwt_required()
def update_profile():
    """
    Cập nhật profile của user đang đăng nhập.

    Có thể cập nhật:
    - username
    - nickname
    - avatar_url
    - bio
    """

    current_user_id = int(get_jwt_identity())
    user = db.session.get(User, current_user_id)

    if not user:
        return jsonify({
            "error": "Không tìm thấy user"
        }), 404

    data = request.get_json() or {}

    # Cập nhật username
    if "username" in data:
        username = str(data["username"]).strip()

        if not username:
            return jsonify({
                "error": "Username không được để trống"
            }), 400

        existing_user = User.query.filter(
            User.username == username,
            User.id != user.id
        ).first()

        if existing_user:
            return jsonify({
                "error": "Username đã tồn tại"
            }), 400

        user.username = username

    # Cập nhật nickname
    if "nickname" in data:
        nickname = data["nickname"]

        if nickname is not None:
            nickname = str(nickname).strip()

        user.nickname = nickname

    # Cập nhật avatar
    if "avatar_url" in data:
        avatar_url = data["avatar_url"]

        if avatar_url is not None:
            avatar_url = str(avatar_url).strip()

        user.avatar_url = avatar_url

    # Cập nhật bio
    if "bio" in data:
        bio = data["bio"]

        if bio is not None:
            bio = str(bio).strip()

        user.bio = bio

    db.session.commit()

    return jsonify({
        "message": "Cập nhật hồ sơ thành công",
        "user": {
            "id": user.id,
            "username": user.username,
            "nickname": user.nickname,
            "avatar_url": user.avatar_url,
            "bio": user.bio,
            "is_private": user.is_private
        }
    }), 200


# =========================================================
# UPDATE ACCOUNT PRIVACY
# =========================================================

@api_bp.route("/users/me/privacy", methods=["PATCH"])
@jwt_required()
def update_account_privacy():
    """
    Bật/tắt chế độ riêng tư cho toàn bộ tài khoản.

    JSON:
    {
        "is_private": true
    }
    """

    current_user_id = int(get_jwt_identity())
    user = db.session.get(User, current_user_id)

    if not user:
        return jsonify({
            "error": "Không tìm thấy user"
        }), 404

    data = request.get_json() or {}

    if "is_private" not in data:
        return jsonify({
            "error": "Thiếu trường is_private"
        }), 400

    is_private = data["is_private"]

    if not isinstance(is_private, bool):
        return jsonify({
            "error": "is_private phải là true hoặc false"
        }), 400

    user.is_private = is_private
    db.session.commit()

    return jsonify({
        "message": (
            "Đã chuyển tài khoản sang riêng tư"
            if user.is_private
            else "Đã chuyển tài khoản sang công khai"
        ),
        "is_private": user.is_private
    }), 200

# =========================================================
# GET FOLLOWERS
# =========================================================

@api_bp.route("/users/<int:user_id>/followers", methods=["GET"])
@jwt_required()
def get_followers(user_id):
    """
    Lấy danh sách những user đang follow user_id.
    """

    # Kiểm tra user cần xem có tồn tại không
    user = db.session.get(User, user_id)

    if not user:
        return jsonify({
            "error": "Không tìm thấy user"
        }), 404

    # Tìm tất cả quan hệ mà user_id là người được follow
    follows = Follow.query.filter_by(
        followed_id=user_id
    ).order_by(Follow.created_at.desc()).all()

    followers = []

    for follow in follows:
        follower = db.session.get(User, follow.follower_id)

        if follower:
            followers.append({
                "id": follower.id,
                "username": follower.username,
                "nickname": follower.nickname,
                "avatar_url": follower.avatar_url,
                "is_private": follower.is_private
            })

    return jsonify({
        "user_id": user.id,
        "count": len(followers),
        "followers": followers
    }), 200


# =========================================================
# GET FOLLOWING
# =========================================================

@api_bp.route("/users/<int:user_id>/following", methods=["GET"])
@jwt_required()
def get_following(user_id):
    """
    Lấy danh sách những user mà user_id đang follow.
    """

    # Kiểm tra user cần xem có tồn tại không
    user = db.session.get(User, user_id)

    if not user:
        return jsonify({
            "error": "Không tìm thấy user"
        }), 404

    # Tìm tất cả quan hệ mà user_id là người đi follow
    follows = Follow.query.filter_by(
        follower_id=user_id
    ).order_by(Follow.created_at.desc()).all()

    following = []

    for follow in follows:
        followed_user = db.session.get(User, follow.followed_id)

        if followed_user:
            following.append({
                "id": followed_user.id,
                "username": followed_user.username,
                "nickname": followed_user.nickname,
                "avatar_url": followed_user.avatar_url,
                "is_private": followed_user.is_private
            })

    return jsonify({
        "user_id": user.id,
        "count": len(following),
        "following": following
    }), 200

# =========================================================
# GET SAVED POSTS
# =========================================================

@api_bp.route("/users/me/saved-posts", methods=["GET"])
@jwt_required()
def get_saved_posts():
    """
    Lấy danh sách bài viết mà user hiện tại đã lưu.
    """

    # Lấy ID user từ JWT
    current_user_id = int(get_jwt_identity())

    # Kiểm tra user có tồn tại không
    user = db.session.get(User, current_user_id)

    if not user:
        return jsonify({
            "error": "Không tìm thấy user"
        }), 404

    # Lấy các bài đã lưu, mới lưu nhất lên trước
    saved_records = SavedPost.query.filter_by(
        user_id=current_user_id
    ).order_by(SavedPost.created_at.desc()).all()

    saved_posts = []

    for saved in saved_records:
        post = db.session.get(Post, saved.post_id)

        # Nếu bài viết đã bị xóa thì bỏ qua
        if not post:
            continue

        # Lấy ảnh/video thuộc bài viết
        photos = Photo.query.filter_by(
            post_id=post.id
        ).order_by(Photo.created_at.asc()).all()

        media = []

        for photo in photos:
            media.append({
                "id": photo.id,
                "file_path": photo.file_path,
                "media_type": photo.media_type
            })

        saved_posts.append({
            "saved_post_id": saved.id,
            "saved_at": saved.created_at.isoformat()
                if saved.created_at else None,

            "post": {
                "id": post.id,
                "user_id": post.user_id,
                "caption": post.caption,
                "visibility": post.visibility,
                "location_id": post.location_id,
                "original_post_id": post.original_post_id,
                "created_at": post.created_at.isoformat()
                    if post.created_at else None,
                "media": media
            }
        })

    return jsonify({
        "count": len(saved_posts),
        "saved_posts": saved_posts
    }), 200