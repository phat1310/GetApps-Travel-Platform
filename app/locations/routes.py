"""Routes LOCATIONS — đăng bài (nhiều ảnh/video + hashtag), bảng tin Discovery,
chi tiết bài viết, like, comment, share, save, địa điểm, lịch trình.
"""

import os
import uuid
from flask import request, jsonify, current_app, render_template, redirect, url_for, flash, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app.locations import locations_bp
from app.extensions import db
from app.models import (
    Post, Photo, Like, Comment, Share, SavedPost, Location, User,
    Itinerary, ItineraryDay, ItineraryStop, ItineraryLodging, ItineraryAttachment,
    Notification,
)
from app.locations.utils import get_or_create_location, normalize_location_name
from app.locations.hashtag_utils import parse_hashtags, get_or_create_hashtag
from app.locations.serializers import serialize_posts


IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
VIDEO_EXTENSIONS = {"mp4", "mov", "webm"}
MAX_FILES_PER_POST = 10


def get_media_type(filename):
    if "." not in filename:
        return None

    ext = filename.rsplit(".", 1)[1].lower()

    if ext in IMAGE_EXTENSIONS:
        return "image"

    if ext in VIDEO_EXTENSIONS:
        return "video"

    return None

def user_can_access_post(post):
    """
    Post public -> ai cũng xem/tương tác được.
    Post private -> chỉ chủ post hoặc người đang follow chủ post.
    """
    if post.visibility != "private":
        return True

    if not current_user.is_authenticated:
        return False

    if post.user_id == current_user.id:
        return True

    from app.models import Follow

    return (
        Follow.query.filter_by(
            follower_id=current_user.id,
            followed_id=post.user_id
        ).first()
        is not None
    )


# =========================================================
# POST - UPLOAD
# =========================================================

@locations_bp.route("/upload", methods=["GET", "POST"])
@login_required
def create_post():
    if request.method == "GET":
        return render_template("locations/upload.html")

    files = request.files.getlist("images")
    is_browser_form = request.accept_mimetypes.accept_html and not request.is_json and request.headers.get("X-Requested-With") != "XMLHttpRequest"

    if not files or files[0].filename == "":
        if is_browser_form:
            flash("Vui lòng chọn ít nhất 1 file ảnh hoặc video", "error")
            return render_template("locations/upload.html"), 400
        return jsonify({
            "error": "Thiếu ít nhất 1 file ảnh/video"
        }), 400

    if len(files) > MAX_FILES_PER_POST:
        if is_browser_form:
            flash(f"Tối đa {MAX_FILES_PER_POST} file mỗi bài viết", "error")
            return render_template("locations/upload.html"), 400
        return jsonify({
            "error": f"Tối đa {MAX_FILES_PER_POST} file mỗi bài viết"
        }), 400

    for file in files:
        if get_media_type(file.filename) is None:
            if is_browser_form:
                flash(f"File '{file.filename}' không đúng định dạng", "error")
                return render_template("locations/upload.html"), 400
            return jsonify({
                "error": f"File '{file.filename}' sai định dạng"
            }), 400


    caption = request.form.get("caption", "")

    hashtags = request.form.get(
        "hashtags",
        ""
    ).strip()

    visibility = request.form.get("visibility", "public")

    if visibility not in ("public", "private"):
        return jsonify({
            "error": "visibility phải là 'public' hoặc 'private'"
        }), 400

    # Kiểm tra hashtag TRƯỚC khi tạo bất cứ thứ gì (địa điểm, bài viết)
    hashtag_names, hashtag_error = parse_hashtags(request.form.getlist("hashtags"))
    if hashtag_error:
        return jsonify({"error": hashtag_error}), 400

    # Tạo/tìm địa điểm TRƯỚC khi tạo Post, vì get_or_create_location có thể commit
    location = get_or_create_location(request.form.get("location_name", ""))

    warning = None

    extra_names = request.form.getlist("extra_location_names")
    extra_links = request.form.getlist("extra_location_links")

    if len(extra_names) > 2:
        extra_names = extra_names[:2]
        extra_links = extra_links[:2]

        warning = (
            "Bạn đã thêm tối đa 2 địa điểm phụ, "
            "các địa điểm còn lại đã bị bỏ qua"
        )

    extra_locations = []
    for name, link in zip(extra_names, extra_links):
        extra_loc = get_or_create_location(name, map_link=link)
        if extra_loc and extra_loc not in extra_locations:
            extra_locations.append(extra_loc)

    post = Post(
        user_id=current_user.id,
        caption=caption,
        visibility=visibility,
        location_id=location.id if location else None,
    )

    db.session.add(post)
    db.session.flush()

    post.extra_locations.extend(extra_locations)

    upload_folder = os.path.join(
        current_app.root_path,
        "static",
        "uploads"
    )

    os.makedirs(upload_folder, exist_ok=True)

    saved_paths = []

    try:
        for name in hashtag_names:
            post.hashtags.append(get_or_create_hashtag(name))

        for file in files:
            media_type = get_media_type(file.filename)

            ext = secure_filename(
                file.filename
            ).rsplit(".", 1)[1]

            unique_filename = (
                f"{uuid.uuid4().hex}.{ext}"
            )

            full_path = os.path.join(
                upload_folder,
                unique_filename
            )

            file.save(full_path)
            saved_paths.append(full_path)

            photo = Photo(
                post_id=post.id,
                file_path=f"static/uploads/{unique_filename}",
                media_type=media_type,
            )

            db.session.add(photo)

        db.session.commit()

    except Exception:
        db.session.rollback()

        for path in saved_paths:
            if os.path.exists(path):
                os.remove(path)

        if is_browser_form:
            flash("Có lỗi xảy ra khi lưu bài viết, vui lòng thử lại", "error")
            return render_template("locations/upload.html"), 500

        return jsonify({
            "error": "Có lỗi xảy ra khi lưu bài viết, vui lòng thử lại"
        }), 500

    if is_browser_form:
        flash("Đăng bài viết thành công!", "success")
        return redirect(url_for("locations.feed"))

    response = {
        "message": "Đăng bài thành công",
        "post_id": post.id,
        "hashtags": hashtag_names
    }

    if warning:
        response["warning"] = warning

    return jsonify(response), 201


# =========================================================
# FEED
# =========================================================

@locations_bp.route("/feed", methods=["GET"])
@login_required
def feed():
    """Bảng tin Feed — Hỗ trợ song song cả Web HTML UI lẫn REST API JSON."""
    from app.models import Follow

    page = max(request.args.get("page", 1, type=int), 1)
    per_page = min(max(request.args.get("per_page", 10, type=int), 1), 50)

    # 1. Trả về JSON cho Mobile / API / Automation tests
    if request.args.get("format") == "json" or (
        request.headers.get("Accept") == "application/json" and not request.accept_mimetypes.accept_html
    ):
        posts = (
            Post.query.filter(Post.visibility == "public")
            .order_by(Post.created_at.desc(), Post.id.desc())
            .limit(per_page + 1)
            .offset((page - 1) * per_page)
            .all()
        )
        has_next = len(posts) > per_page
        posts = posts[:per_page]

        return jsonify({
            "feed": serialize_posts(posts, current_user.id),
            "page": page,
            "per_page": per_page,
            "has_next": has_next,
        })

    # 2. Render Template HTML cho Trình duyệt Web
    following_ids = [
        f.followed_id for f in Follow.query.filter_by(follower_id=current_user.id).all()
    ]
    feed_user_ids = list(set(following_ids + [current_user.id]))

    if feed_user_ids:
        posts = (
            Post.query.filter(Post.user_id.in_(feed_user_ids))
            .order_by(Post.created_at.desc())
            .all()
        )
    else:
        posts = []

    if not posts:
        posts = Post.query.order_by(Post.created_at.desc()).limit(20).all()

    post_cards = []
    for p in posts:
        author = db.session.get(User, p.user_id) if hasattr(db.session, 'get') else User.query.get(p.user_id)
        photos = Photo.query.filter_by(post_id=p.id).order_by(Photo.id.asc()).all()
        loc = db.session.get(Location, p.location_id) if (p.location_id and hasattr(db.session, 'get')) else (Location.query.get(p.location_id) if p.location_id else None)
        likes_count = Like.query.filter_by(post_id=p.id).count()
        is_liked = bool(Like.query.filter_by(user_id=current_user.id, post_id=p.id).first())
        comments = Comment.query.filter_by(post_id=p.id).order_by(Comment.created_at.asc()).all()
        comments_count = len(comments)
        is_saved = bool(SavedPost.query.filter_by(user_id=current_user.id, post_id=p.id).first())
        shares_count = Share.query.filter_by(post_id=p.id).count()

        formatted_comments = []
        for c in comments:
            c_author = db.session.get(User, c.user_id) if hasattr(db.session, 'get') else User.query.get(c.user_id)
            formatted_comments.append({
                "id": c.id,
                "user_id": c.user_id,
                "author_name": c_author.username if c_author else f"User #{c.user_id}",
                "content": c.content,
                "created_at": c.created_at.strftime("%H:%M %d/%m/%Y") if c.created_at else "",
                "can_delete": (c.user_id == current_user.id)
            })

        post_cards.append({
            "id": p.id,
            "author": author,
            "caption": p.caption,
            "location": loc,
            "created_at": p.created_at.strftime("%d/%m/%Y %H:%M") if p.created_at else "",
            "photos": photos,
            "likes_count": likes_count,
            "is_liked": is_liked,
            "comments_count": comments_count,
            "comments": formatted_comments,
            "is_saved": is_saved,
            "shares_count": shares_count,
        })

    suggested_locations = Location.query.order_by(Location.id.desc()).limit(5).all()
    suggested_users = User.query.filter(User.id != current_user.id).limit(5).all()

    return render_template(
        "locations/feed.html",
        posts=post_cards,
        suggested_locations=suggested_locations,
        suggested_users=suggested_users,
    )


@locations_bp.route("/posts/<int:post_id>", methods=["GET"])
@login_required
def get_post(post_id):
    """Chi tiết 1 bài viết (thay cho route địa điểm cũ đã không còn)."""
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"error": "Bài viết không tồn tại"}), 404
    if not user_can_access_post(post):
        return jsonify({"error": "Bạn không có quyền xem bài viết này"}), 403

    return jsonify({"post": serialize_posts([post], current_user.id)[0]})


# =========================================================
# LIKE
# =========================================================

@locations_bp.route(
    "/posts/<int:post_id>/like",
    methods=["POST"]
)
@login_required
def like_post(post_id):
    post = db.session.get(Post, post_id)

    if not post:
        return jsonify({
            "error": "Bài viết không tồn tại"
        }), 404

    if not user_can_access_post(post):
        return jsonify({
            "error": "Bạn không có quyền xem bài viết này"
        }), 403

    existing = Like.query.filter_by(
        user_id=current_user.id,
        post_id=post_id
    ).first()

    if existing:
        db.session.delete(existing)
        db.session.commit()

        return jsonify({
            "message": "Đã bỏ tim",
            "liked": False
        })

    like = Like(
        user_id=current_user.id,
        post_id=post_id
    )

    db.session.add(like)

    # Tạo thông báo Like cho chủ bài viết
    # Không gửi thông báo nếu tự like bài của mình
    if current_user.id != post.user_id:
        notification = Notification(
            user_id=post.user_id,
            actor_id=current_user.id,
            notification_type="like",
            post_id=post.id
        )

        db.session.add(notification)

    # Lưu Like + Notification cùng transaction
    db.session.commit()

    return jsonify({
        "message": "Đã thả tim",
        "liked": True
    })


# =========================================================
# COMMENT - CREATE
# =========================================================

@locations_bp.route(
    "/posts/<int:post_id>/comments",
    methods=["POST"]
)
@login_required
def create_comment(post_id):
    post = db.session.get(Post, post_id)

    if not post:
        return jsonify({
            "error": "Bài viết không tồn tại"
        }), 404

    if not user_can_access_post(post):
        return jsonify({
            "error": "Bạn không có quyền bình luận bài viết này"
        }), 403

    data = request.get_json() or {}
    content = data.get("content", "").strip()

    if not content:
        return jsonify({
            "error": "Nội dung bình luận không được để trống"
        }), 400

    comment = Comment(
        user_id=current_user.id,
        post_id=post_id,
        content=content
    )

    db.session.add(comment)
    db.session.commit()

    return jsonify({
        "message": "Bình luận thành công",
        "comment": {
            "id": comment.id,
            "user_id": comment.user_id,
            "post_id": comment.post_id,
            "content": comment.content,
            "created_at": comment.created_at.isoformat()
        }
    }), 201


# =========================================================
# COMMENT - GET
# =========================================================

@locations_bp.route(
    "/posts/<int:post_id>/comments",
    methods=["GET"]
)
@login_required
def get_comments(post_id):
    post = db.session.get(Post, post_id)

    if not post:
        return jsonify({
            "error": "Bài viết không tồn tại"
        }), 404

    if not user_can_access_post(post):
        return jsonify({
            "error": "Bạn không có quyền xem bài viết này"
        }), 403

    comments = (
        Comment.query
        .filter_by(post_id=post_id)
        .order_by(Comment.created_at.asc())
        .all()
    )

    return jsonify({
        "post_id": post_id,
        "comments": [
            {
                "id": comment.id,
                "user_id": comment.user_id,
                "content": comment.content,
                "created_at": comment.created_at.isoformat()
            }
            for comment in comments
        ]
    })


# =========================================================
# COMMENT - DELETE
# =========================================================

@locations_bp.route(
    "/comments/<int:comment_id>",
    methods=["DELETE"]
)
@login_required
def delete_comment(comment_id):
    comment = db.session.get(Comment, comment_id)

    if not comment:
        return jsonify({
            "error": "Bình luận không tồn tại"
        }), 404

    if comment.user_id != current_user.id:
        return jsonify({
            "error": "Bạn không có quyền xóa bình luận này"
        }), 403

    db.session.delete(comment)
    db.session.commit()

    return jsonify({
        "message": "Xóa bình luận thành công"
    })


# =========================================================
# SHARE - DOWNLOAD
# =========================================================

@locations_bp.route(
    "/posts/<int:post_id>/share/download",
    methods=["GET"]
)
@login_required
def download_post(post_id):
    post = db.session.get(Post, post_id)

    if not post:
        return jsonify({
            "error": "Bài viết không tồn tại"
        }), 404

    if not user_can_access_post(post):
        return jsonify({
            "error": "Bạn không có quyền tải bài viết này"
        }), 403

    photo = Photo.query.filter_by(
        post_id=post_id
    ).first()

    if not photo:
        return jsonify({
            "error": "Bài viết không có file"
        }), 404

    upload_folder = os.path.join(
        current_app.root_path,
        "static",
        "uploads"
    )

    filename = os.path.basename(
        photo.file_path
    )

    full_path = os.path.join(
        upload_folder,
        filename
    )

    if not os.path.exists(full_path):
        return jsonify({
            "error": "File không tồn tại trên server"
        }), 404

    # Chỉ ghi nhận download một lần
    existing = Share.query.filter_by(
        user_id=current_user.id,
        post_id=post_id,
        share_type="download"
    ).first()

    if not existing:
        share = Share(
            user_id=current_user.id,
            post_id=post_id,
            share_type="download"
        )

        db.session.add(share)

        # Tạo thông báo Share cho chủ bài viết
        # Không gửi thông báo nếu tự download bài của mình
        if current_user.id != post.user_id:
            notification = Notification(
                user_id=post.user_id,
                actor_id=current_user.id,
                notification_type="share",
                post_id=post.id
            )

            db.session.add(notification)

        # Lưu Share + Notification cùng transaction
        db.session.commit()

    return send_from_directory(
        upload_folder,
        filename,
        as_attachment=True
    )


# =========================================================
# SHARE - COPY LINK
# =========================================================

@locations_bp.route(
    "/posts/<int:post_id>/share",
    methods=["POST"]
)
@login_required
def share_post(post_id):
    post = db.session.get(Post, post_id)

    if not post:
        return jsonify({
            "error": "Bài viết không tồn tại"
        }), 404

    if not user_can_access_post(post):
        return jsonify({
            "error": "Bạn không có quyền chia sẻ bài viết này"
        }), 403

    link = (
        f"http://127.0.0.1:5000/"
        f"locations/posts/{post_id}"
    )

    # Chỉ ghi nhận copy_link một lần
    existing = Share.query.filter_by(
        user_id=current_user.id,
        post_id=post_id,
        share_type="copy_link"
    ).first()

    if existing:
        return jsonify({
            "message": "Đã sao chép liên kết bài viết",
            "link": link,
            "share": {
                "id": existing.id,
                "user_id": existing.user_id,
                "post_id": existing.post_id,
                "share_type": existing.share_type,
                "created_at": existing.created_at.isoformat()
            }
        }), 200

    share = Share(
        user_id=current_user.id,
        post_id=post_id,
        share_type="copy_link"
    )

    db.session.add(share)

    # Tạo thông báo Share cho chủ bài viết
    # Không gửi thông báo nếu tự share bài của mình
    if current_user.id != post.user_id:
        notification = Notification(
            user_id=post.user_id,
            actor_id=current_user.id,
            notification_type="share",
            post_id=post.id
        )

        db.session.add(notification)

    # Lưu Share + Notification cùng transaction
    db.session.commit()

    return jsonify({
        "message": "Đã sao chép liên kết bài viết",
        "link": link,
        "share": {
            "id": share.id,
            "user_id": share.user_id,
            "post_id": share.post_id,
            "share_type": share.share_type,
            "created_at": share.created_at.isoformat()
        }
    }), 201


# =========================================================
# SAVE
# =========================================================

@locations_bp.route(
    "/posts/<int:post_id>/save",
    methods=["POST"]
)
@login_required
def save_post(post_id):
    post = db.session.get(Post, post_id)

    if not post:
        return jsonify({
            "error": "Bài viết không tồn tại"
        }), 404

    if not user_can_access_post(post):
        return jsonify({
            "error": "Bạn không có quyền lưu bài viết này"
        }), 403

    existing = SavedPost.query.filter_by(
        user_id=current_user.id,
        post_id=post_id
    ).first()

    if existing:
        db.session.delete(existing)
        db.session.commit()

        return jsonify({
            "message": "Đã bỏ lưu bài viết",
            "saved": False
        })

    saved_post = SavedPost(
        user_id=current_user.id,
        post_id=post_id
    )

    db.session.add(saved_post)
    db.session.commit()

    return jsonify({
        "message": "Đã lưu bài viết",
        "saved": True
    }), 201


# =========================================================
# SHARE - REPOST
# =========================================================

@locations_bp.route(
    "/posts/<int:post_id>/repost",
    methods=["POST"]
)
@login_required
def repost_post(post_id):
    original_post = db.session.get(
        Post,
        post_id
    )

    if not original_post:
        return jsonify({
            "error": "Bài viết không tồn tại"
        }), 404

    if not user_can_access_post(original_post):
        return jsonify({
            "error": "Bạn không có quyền đăng lại bài viết này"
        }), 403

    # Mỗi user chỉ repost một bài một lần
    existing = Share.query.filter_by(
        user_id=current_user.id,
        post_id=post_id,
        share_type="repost"
    ).first()

    if existing:
        return jsonify({
            "error": "Bạn đã đăng lại bài viết này"
        }), 409

    repost = Post(
        user_id=current_user.id,
        caption=original_post.caption,
        visibility="public",
        location_id=original_post.location_id,
        original_post_id=original_post.id
    )

    db.session.add(repost)
    db.session.flush()

    # Giữ các địa điểm phụ của bài gốc
    for location in original_post.extra_locations:
        repost.extra_locations.append(location)

    original_photos = Photo.query.filter_by(
        post_id=original_post.id
    ).all()

    for photo in original_photos:
        new_photo = Photo(
            post_id=repost.id,
            file_path=photo.file_path,
            media_type=photo.media_type
        )

        db.session.add(new_photo)

    share = Share(
        user_id=current_user.id,
        post_id=original_post.id,
        share_type="repost"
    )

    db.session.add(share)

    # Tạo thông báo Share cho chủ bài viết gốc
    # Không gửi thông báo nếu tự repost bài của mình
    if current_user.id != original_post.user_id:
        notification = Notification(
            user_id=original_post.user_id,
            actor_id=current_user.id,
            notification_type="share",
            post_id=original_post.id
        )

        db.session.add(notification)

    # Lưu Repost + Share + Notification cùng transaction
    db.session.commit()

    return jsonify({
        "message": "Đăng lại bài viết thành công",
        "repost": {
            "id": repost.id,
            "user_id": repost.user_id,
            "original_post_id": repost.original_post_id,
            "caption": repost.caption
        },
        "share": {
            "id": share.id,
            "share_type": share.share_type
        }
    }), 201


# =========================================================
# LOCATION - CREATE
# =========================================================

@locations_bp.route(
    "/locations",
    methods=["POST"]
)
@login_required
def create_location():
    """
    Tạo địa điểm mới — tự dedupe theo slug
    (Đà Lạt = Da Lat = DALAT).
    """
    data = request.get_json() or {}

    name = data.get(
        "name",
        ""
    ).strip()

    map_link = data.get(
        "map_link",
        ""
    ).strip() or None

    if not name:
        return jsonify({
            "error": "Tên địa điểm không được để trống"
        }), 400

    location = get_or_create_location(
        name,
        map_link=map_link
    )

    return jsonify({
        "location": {
            "id": location.id,
            "name": location.name,
            "slug": location.slug,
            "map_link": location.map_link
        }
    }), 201


# =========================================================
# LOCATION - SEARCH
# =========================================================

@locations_bp.route("/search", methods=["GET"])
@locations_bp.route(
    "/locations/search",
    methods=["GET"]
)
@login_required
def search_locations():
    """
    Tìm kiếm địa điểm.
    Sort theo số lần share của các bài viết thuộc địa điểm:
    share nhiều -> đứng trước.
    """

    query = request.args.get(
        "q",
        ""
    ).strip()

    if not query:
        return jsonify({
            "locations": []
        })

    query_slug = normalize_location_name(
        query
    )

    locations = (
        db.session.query(
            Location,
            db.func.count(Share.id).label("share_count")
        )
        .outerjoin(
            Post,
            Post.location_id == Location.id
        )
        .outerjoin(
            Share,
            Share.post_id == Post.id
        )
        .filter(
            Location.slug.contains(query_slug)
        )
        .group_by(
            Location.id
        )
        .order_by(
            db.func.count(Share.id).desc(),
            Location.name.asc()
        )
        .limit(10)
        .all()
    )

    return jsonify({
        "locations": [
            {
                "id": location.id,
                "name": location.name,
                "slug": location.slug,
                "address": location.address,
                "map_link": location.map_link,
                "share_count": share_count
            }
            for location, share_count in locations
        ]
    })

# ============================================================
# LỊCH TRÌNH (ITINERARY) — Pack 3, phụ trách: Khánh
# Itinerary luôn công khai (theo File 1) -> không cần user_can_access_post
# ============================================================

@locations_bp.route("/itineraries", methods=["POST"])
@login_required
def create_itinerary():
    data = request.get_json()
    if not data or not data.get("title"):
        return jsonify({"error": "Thiếu tên chuyến đi"}), 400

    from datetime import datetime
    location = None
    if data.get("location_name"):
        location = get_or_create_location(data["location_name"], data.get("map_link"))

    itinerary = Itinerary(
        user_id=current_user.id,
        title=data["title"],
        description=data.get("description"),
        location_id=location.id if location else None,
        start_date=datetime.fromisoformat(data["start_date"]).date() if data.get("start_date") else None,
        end_date=datetime.fromisoformat(data["end_date"]).date() if data.get("end_date") else None,
        trip_type=data.get("trip_type"),
        participants_count=data.get("participants_count"),
        budget_estimate=data.get("budget_estimate"),
    )
    db.session.add(itinerary)
    db.session.flush()  # có itinerary.id ngay, chưa commit, để gắn Day/Stop cùng 1 transaction

    for day_data in data.get("days", []):
        day = ItineraryDay(itinerary_id=itinerary.id, day_number=day_data["day_number"])
        db.session.add(day)
        db.session.flush()
        for i, stop_data in enumerate(day_data.get("stops", [])):
            from datetime import time as dtime
            start_t = dtime.fromisoformat(stop_data["start_time"]) if stop_data.get("start_time") else None
            end_t = dtime.fromisoformat(stop_data["end_time"]) if stop_data.get("end_time") else None
            db.session.add(ItineraryStop(
                day_id=day.id,
                order_index=i,
                activity_name=stop_data["activity_name"],
                location_link=stop_data.get("location_link"),
                price=stop_data.get("price"),
                note=stop_data.get("note"),
                start_time=start_t,
                end_time=end_t,
            ))

    for lodging_data in data.get("lodgings", []):
        db.session.add(ItineraryLodging(
            itinerary_id=itinerary.id,
            name=lodging_data["name"],
            price_per_night=lodging_data.get("price_per_night"),
            booking_link=lodging_data.get("booking_link"),
            note=lodging_data.get("note"),
        ))

    db.session.commit()
    return jsonify({"message": "Đăng lịch trình thành công", "itinerary": serialize_itinerary(itinerary)}), 201


@locations_bp.route("/itineraries/feed", methods=["GET"])
@login_required
def itinerary_feed():
    itineraries = Itinerary.query.order_by(Itinerary.created_at.desc()).all()
    return jsonify({"feed": [
        {
            "id": it.id,
            "title": it.title,
            "cover_image": it.cover_image,
            "user_id": it.user_id,
            "start_date": it.start_date.isoformat() if it.start_date else None,
            "end_date": it.end_date.isoformat() if it.end_date else None,
        } for it in itineraries
    ]})

def serialize_itinerary(it):
    return {
        "id": it.id,
        "title": it.title,
        "description": it.description,
        "cover_image": it.cover_image,
        "user_id": it.user_id,
        "start_date": it.start_date.isoformat() if it.start_date else None,
        "end_date": it.end_date.isoformat() if it.end_date else None,
        "trip_type": it.trip_type,
        "participants_count": it.participants_count,
        "budget_estimate": it.budget_estimate,
        "days": [{
            "id": d.id,
            "day_number": d.day_number,
            "stops": [{
                "id": s.id,
                "activity_name": s.activity_name,
                "location_link": s.location_link,
                "price": s.price,
                "note": s.note,
                "image_path": s.image_path,
                "start_time": s.start_time.strftime("%H:%M") if s.start_time else None,
                "end_time": s.end_time.strftime("%H:%M") if s.end_time else None,
            } for s in d.stops],
        } for d in it.days],
        "lodgings": [{
            "id": l.id,
            "name": l.name,
            "price_per_night": l.price_per_night,
            "booking_link": l.booking_link,
            "note": l.note,
        } for l in it.lodgings],
        "attachments": [{"id": a.id, "original_name": a.original_name, "file_path": a.file_path} for a in it.attachments],
        "like_count": Like.query.filter_by(itinerary_id=it.id).count(),
        "comment_count": Comment.query.filter_by(itinerary_id=it.id).count(),
    }


@locations_bp.route("/itineraries/<int:itinerary_id>", methods=["GET"])
@login_required
def get_itinerary(itinerary_id):
    it = db.get_or_404(Itinerary, itinerary_id)
    return jsonify(serialize_itinerary(it))


@locations_bp.route("/itineraries/<int:itinerary_id>", methods=["DELETE"])
@login_required
def delete_itinerary(itinerary_id):
    it = db.get_or_404(Itinerary, itinerary_id)
    if it.user_id != current_user.id:
        return jsonify({"error": "Bạn không có quyền xóa lịch trình này"}), 403
    db.session.delete(it)
    db.session.commit()
    return jsonify({"message": "Xóa lịch trình thành công"})


ATTACHMENT_EXTENSIONS = {"docx", "xlsx", "pdf", "pptx"}

@locations_bp.route("/itineraries/<int:itinerary_id>/attachments", methods=["POST"])
@login_required
def upload_itinerary_attachment(itinerary_id):
    it = db.get_or_404(Itinerary, itinerary_id)
    if it.user_id != current_user.id:
        return jsonify({"error": "Bạn không có quyền thêm file vào lịch trình này"}), 403

    file = request.files.get("file")
    if not file or file.filename == "":
        return jsonify({"error": "Thiếu file"}), 400
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ATTACHMENT_EXTENSIONS:
        return jsonify({"error": f"Chỉ nhận file: {', '.join(ATTACHMENT_EXTENSIONS)}"}), 400

    filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
    upload_dir = os.path.join(current_app.root_path, "static", "uploads", "itineraries")
    os.makedirs(upload_dir, exist_ok=True)
    save_path = os.path.join(upload_dir, filename)
    file.save(save_path)

    attachment = ItineraryAttachment(
        itinerary_id=itinerary_id,
        file_path=f"uploads/itineraries/{filename}",
        original_name=file.filename,
    )
    db.session.add(attachment)
    db.session.commit()
    return jsonify({"message": "Upload thành công", "attachment_id": attachment.id}), 201


# ---- Like / Comment / Share / Save áp dụng cho Itinerary ----

@locations_bp.route("/itineraries/<int:itinerary_id>/like", methods=["POST"])
@login_required
def like_itinerary(itinerary_id):
    db.get_or_404(Itinerary, itinerary_id)
    existing = Like.query.filter_by(user_id=current_user.id, itinerary_id=itinerary_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({"message": "Đã bỏ tim", "liked": False})
    db.session.add(Like(user_id=current_user.id, itinerary_id=itinerary_id))
    db.session.commit()
    return jsonify({"message": "Đã thả tim", "liked": True})


@locations_bp.route("/itineraries/<int:itinerary_id>/comments", methods=["POST"])
@login_required
def create_itinerary_comment(itinerary_id):
    db.get_or_404(Itinerary, itinerary_id)
    data = request.get_json()
    content = data.get("content", "").strip() if data else ""
    if not content:
        return jsonify({"error": "Nội dung bình luận không được rỗng"}), 400
    comment = Comment(user_id=current_user.id, itinerary_id=itinerary_id, content=content)
    db.session.add(comment)
    db.session.commit()
    return jsonify({"message": "Đã bình luận", "comment_id": comment.id}), 201


@locations_bp.route("/itineraries/<int:itinerary_id>/comments", methods=["GET"])
@login_required
def get_itinerary_comments(itinerary_id):
    db.get_or_404(Itinerary, itinerary_id)
    comments = Comment.query.filter_by(itinerary_id=itinerary_id).order_by(Comment.created_at.asc()).all()
    return jsonify({"comments": [
        {"id": c.id, "user_id": c.user_id, "content": c.content} for c in comments
    ]})


@locations_bp.route("/itineraries/<int:itinerary_id>/share", methods=["POST"])
@login_required
def share_itinerary(itinerary_id):
    db.get_or_404(Itinerary, itinerary_id)
    existing = Share.query.filter_by(user_id=current_user.id, itinerary_id=itinerary_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({"message": "Đã hủy chia sẻ", "shared": False})
    db.session.add(Share(user_id=current_user.id, itinerary_id=itinerary_id, share_type="copy_link"))
    db.session.commit()
    return jsonify({"message": "Đã chia sẻ", "shared": True})


@locations_bp.route("/itineraries/<int:itinerary_id>/save", methods=["POST"])
@login_required
def save_itinerary(itinerary_id):
    db.get_or_404(Itinerary, itinerary_id)
    existing = SavedPost.query.filter_by(user_id=current_user.id, itinerary_id=itinerary_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({"message": "Đã bỏ lưu", "saved": False})
    db.session.add(SavedPost(user_id=current_user.id, itinerary_id=itinerary_id))
    db.session.commit()
    return jsonify({"message": "Đã lưu", "saved": True})

@locations_bp.route("/itineraries/<int:itinerary_id>", methods=["PUT"])
@login_required
def update_itinerary(itinerary_id):
    it = db.get_or_404(Itinerary, itinerary_id)
    if it.user_id != current_user.id:
        return jsonify({"error": "Bạn không có quyền sửa lịch trình này"}), 403

    data = request.get_json()
    if not data:
        return jsonify({"error": "Thiếu dữ liệu"}), 400

    from datetime import datetime

    if "title" in data:
        if not data["title"]:
            return jsonify({"error": "Tên chuyến đi không được để trống"}), 400
        it.title = data["title"]
    if "description" in data:
        it.description = data["description"]
    if "start_date" in data:
        it.start_date = datetime.fromisoformat(data["start_date"]).date() if data["start_date"] else None
    if "end_date" in data:
        it.end_date = datetime.fromisoformat(data["end_date"]).date() if data["end_date"] else None
    if "trip_type" in data:
        it.trip_type = data["trip_type"]
    if "participants_count" in data:
        it.participants_count = data["participants_count"]
    if "budget_estimate" in data:
        it.budget_estimate = data["budget_estimate"]

    # Nếu client gửi kèm "days" hoặc "lodgings" -> xóa sạch cũ, tạo lại từ đầu
    # (nhờ cascade="all, delete-orphan" đã khai báo sẵn trong model Itinerary)
    if "days" in data:
        it.days = []
        db.session.flush()
        for day_data in data["days"]:
            day = ItineraryDay(itinerary_id=it.id, day_number=day_data["day_number"])
            db.session.add(day)
            db.session.flush()
            for i, stop_data in enumerate(day_data.get("stops", [])):
                db.session.add(ItineraryStop(
                    day_id=day.id,
                    order_index=i,
                    activity_name=stop_data["activity_name"],
                    location_link=stop_data.get("location_link"),
                    price=stop_data.get("price"),
                    note=stop_data.get("note"),
                ))

    if "lodgings" in data:
        it.lodgings = []
        db.session.flush()
        for lodging_data in data["lodgings"]:
            db.session.add(ItineraryLodging(
                itinerary_id=it.id,
                name=lodging_data["name"],
                price_per_night=lodging_data.get("price_per_night"),
                booking_link=lodging_data.get("booking_link"),
                note=lodging_data.get("note"),
            ))

    db.session.commit()
    return jsonify({"message": "Cập nhật lịch trình thành công", "itinerary_id": it.id})

@locations_bp.route("/itineraries/<int:itinerary_id>/cover-image", methods=["POST"])
@login_required
def upload_itinerary_cover(itinerary_id):
    it = db.get_or_404(Itinerary, itinerary_id)
    if it.user_id != current_user.id:
        return jsonify({"error": "Bạn không có quyền sửa lịch trình này"}), 403

    file = request.files.get("image")
    if not file or file.filename == "":
        return jsonify({"error": "Thiếu file ảnh"}), 400
    if get_media_type(file.filename) != "image":
        return jsonify({"error": "Chỉ nhận file ảnh (jpg/png/gif)"}), 400

    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    upload_dir = os.path.join(current_app.root_path, "static", "uploads", "itineraries")
    os.makedirs(upload_dir, exist_ok=True)
    file.save(os.path.join(upload_dir, filename))

    it.cover_image = f"uploads/itineraries/{filename}"
    db.session.commit()
    return jsonify({"message": "Đã cập nhật ảnh bìa", "cover_image": it.cover_image})


@locations_bp.route("/itineraries/stops/<int:stop_id>/image", methods=["POST"])
@login_required
def upload_stop_image(stop_id):
    stop = db.get_or_404(ItineraryStop, stop_id)
    if stop.day.itinerary.user_id != current_user.id:
        return jsonify({"error": "Bạn không có quyền sửa chặng này"}), 403

    file = request.files.get("image")
    if not file or file.filename == "":
        return jsonify({"error": "Thiếu file ảnh"}), 400
    if get_media_type(file.filename) != "image":
        return jsonify({"error": "Chỉ nhận file ảnh (jpg/png/gif)"}), 400

    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    upload_dir = os.path.join(current_app.root_path, "static", "uploads", "itineraries")
    os.makedirs(upload_dir, exist_ok=True)
    file.save(os.path.join(upload_dir, filename))

    stop.image_path = f"uploads/itineraries/{filename}"
    db.session.commit()
    return jsonify({"message": "Đã cập nhật ảnh chặng", "image_path": stop.image_path})

@locations_bp.route("/itineraries/new", methods=["GET"])
@login_required
def new_itinerary_page():
    return render_template("itinerary_create.html")