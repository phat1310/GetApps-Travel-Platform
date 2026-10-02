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
from app.models import (
    User,
    Follow,
    SavedPost,
    Post,
    Photo,
    Notification,
    Like,
    Comment,
    Share,
    Location
)


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

# =========================================================
# SEARCH USERS
# =========================================================

@api_bp.route("/users/search", methods=["GET"])
@jwt_required()
def search_users():
    """
    Tìm kiếm user.

    Ưu tiên:
    1. Username khớp chính xác.
    2. Nếu không có username chính xác thì tìm gần giống.
    """

    keyword = request.args.get(
        "q",
        ""
    ).strip()

    if not keyword:
        return jsonify({
            "error": "Thiếu từ khóa tìm kiếm"
        }), 400

    # =====================================================
    # 1. TÌM KHỚP CHÍNH XÁC
    # =====================================================

    exact_user = User.query.filter(
        User.username.ilike(keyword)
    ).first()

    if exact_user:
        users = [exact_user]

    else:
        # =================================================
        # 2. TÌM GẦN GIỐNG
        # =================================================

        users = User.query.filter(
            User.username.ilike(f"%{keyword}%")
        ).order_by(
            User.username.asc()
        ).limit(20).all()

    result = []

    for user in users:
        result.append({
            "id": user.id,
            "username": user.username,
            "nickname": user.nickname,
            "avatar_url": user.avatar_url,
            "is_private": user.is_private
        })

    return jsonify({
        "keyword": keyword,
        "count": len(result),
        "users": result
    }), 200

# =========================================================
# GET NOTIFICATIONS
# =========================================================

@api_bp.route("/notifications", methods=["GET"])
@jwt_required()
def get_notifications():
    """
    Lấy danh sách notification của user hiện tại.

    Các notification cùng:
    - notification_type
    - post_id

    sẽ được gom lại.

    Ví dụ:
    User 2 like + User 3 like cùng một post
    -> User 2 + 1 người khác đã like.
    """

    current_user_id = int(get_jwt_identity())

    notifications = Notification.query.filter_by(
        user_id=current_user_id
    ).order_by(
        Notification.created_at.desc()
    ).all()

    # =====================================================
    # GROUP NOTIFICATIONS
    # =====================================================

    groups = {}

    for notification in notifications:

        # Follow không có post_id
        # Like/share theo cùng post sẽ được group
        key = (
            notification.notification_type,
            notification.post_id
        )

        if key not in groups:
            groups[key] = []

        groups[key].append(notification)

    result = []

    for key, group in groups.items():

        # Notification mới nhất đại diện cho group
        latest = group[0]

        actor = db.session.get(
            User,
            latest.actor_id
        )

        post = None

        if latest.post_id:
            post = db.session.get(
                Post,
                latest.post_id
            )

        result.append({
            "id": latest.id,
            "type": latest.notification_type,
            "is_read": all(
                n.is_read for n in group
            ),
            "created_at": (
                latest.created_at.isoformat()
                if latest.created_at
                else None
            ),

            "actor": {
                "id": actor.id,
                "username": actor.username,
                "nickname": actor.nickname,
                "avatar_url": actor.avatar_url
            } if actor else None,

            "other_count": max(
                len(group) - 1,
                0
            ),

            "post": {
                "id": post.id,
                "caption": post.caption
            } if post else None
        })

    return jsonify({
        "count": len(result),
        "notifications": result
    }), 200

# =========================================================
# SEARCH HASHTAGS
# =========================================================

@api_bp.route("/hashtags/search", methods=["GET"])
@jwt_required()
def search_hashtags():
    """
    Tìm bài viết theo hashtag.

    Ví dụ:
    /api/hashtags/search?q=dalat
    """

    keyword = request.args.get(
        "q",
        ""
    ).strip().lstrip("#").lower()

    if not keyword:
        return jsonify({
            "error": "Thiếu hashtag cần tìm"
        }), 400

    posts = Post.query.filter(
        Post.hashtags.ilike(f"%{keyword}%")
    ).order_by(
        Post.created_at.desc()
    ).limit(20).all()

    result = []

    for post in posts:
        result.append({
            "id": post.id,
            "user_id": post.user_id,
            "caption": post.caption,
            "hashtags": post.hashtags,
            "visibility": post.visibility,
            "created_at": (
                post.created_at.isoformat()
                if post.created_at
                else None
            )
        })

    return jsonify({
        "keyword": keyword,
        "count": len(result),
        "posts": result
    }), 200

# =========================================================
# SEARCH ALL - SORT TỔNG HỢP
# =========================================================

@api_bp.route("/search", methods=["GET"])
@jwt_required()
def search_all():
    """
    Tìm kiếm tổng hợp bài viết.

    Score được tính từ:
    - hashtag popularity
    - like count
    - comment count
    - share count

    Công thức:
        score = hashtag_popularity
              + like_count
              + comment_count
              + share_count
    """

    keyword = request.args.get(
        "q",
        ""
    ).strip().lower()

    if not keyword:
        return jsonify({
            "error": "Thiếu từ khóa cần tìm"
        }), 400

    posts = (
        Post.query
        .filter(
            db.or_(
                Post.caption.ilike(f"%{keyword}%"),
                Post.hashtags.ilike(f"%{keyword}%")
            )
        )
        .all()
    )

    result = []

    for post in posts:

        # -------------------------------------------------
        # LIKE COUNT
        # -------------------------------------------------
        like_count = Like.query.filter_by(
            post_id=post.id
        ).count()

        # -------------------------------------------------
        # COMMENT COUNT
        # -------------------------------------------------
        comment_count = Comment.query.filter_by(
            post_id=post.id
        ).count()

        # -------------------------------------------------
        # SHARE COUNT
        # -------------------------------------------------
        share_count = Share.query.filter_by(
            post_id=post.id
        ).count()

        # -------------------------------------------------
        # HASHTAG POPULARITY
        # -------------------------------------------------
        hashtag_popularity = 0

        if post.hashtags:
            hashtags = [
                tag.strip().lstrip("#").lower()
                for tag in post.hashtags.split(",")
                if tag.strip()
            ]

            for tag in hashtags:
                hashtag_popularity += (
                    Post.query
                    .filter(
                        Post.hashtags.ilike(
                            f"%{tag}%"
                        )
                    )
                    .count()
                )

        # -------------------------------------------------
        # TOTAL SCORE
        # -------------------------------------------------
        score = (
            hashtag_popularity
            + like_count
            + comment_count
            + share_count
        )

        result.append({
            "id": post.id,
            "user_id": post.user_id,
            "caption": post.caption,
            "hashtags": post.hashtags,
            "visibility": post.visibility,
            "created_at": (
                post.created_at.isoformat()
                if post.created_at
                else None
            ),
            "like_count": like_count,
            "comment_count": comment_count,
            "share_count": share_count,
            "hashtag_popularity": hashtag_popularity,
            "score": score
        })

    # Score cao đứng trước
    result.sort(
        key=lambda item: (
            item["score"],
            item["created_at"] or ""
        ),
        reverse=True
    )

    return jsonify({
        "keyword": keyword,
        "count": len(result),
        "posts": result
    }), 200