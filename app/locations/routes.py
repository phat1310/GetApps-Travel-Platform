"""Routes LOCATIONS — route đăng bài (nhiều ảnh/video), bảng tin, like.
Cần mở rộng thêm Place, Album, Tag.
"""
import os
import uuid
from flask import request, jsonify, current_app, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.locations import locations_bp
from app.extensions import db
from app.models import Post, Photo, Like, Comment, Share, SavedPost, Location, User
from app.locations.utils import get_or_create_location, normalize_location_name

IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
VIDEO_EXTENSIONS = {'mp4', 'mov', 'webm'}
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
        return jsonify({"error": "Thiếu ít nhất 1 file ảnh/video"}), 400

    if len(files) > MAX_FILES_PER_POST:
        if is_browser_form:
            flash(f"Tối đa {MAX_FILES_PER_POST} file mỗi bài viết", "error")
            return render_template("locations/upload.html"), 400
        return jsonify({"error": f"Tối đa {MAX_FILES_PER_POST} file mỗi bài viết"}), 400

    for file in files:
        if get_media_type(file.filename) is None:
            if is_browser_form:
                flash(f"File '{file.filename}' không đúng định dạng", "error")
                return render_template("locations/upload.html"), 400
            return jsonify({"error": f"File '{file.filename}' sai định dạng"}), 400

    caption = request.form.get("caption", "")
    location_name = request.form.get("location_name", "")
    location = get_or_create_location(location_name)

    post = Post(
        user_id=current_user.id,
        caption=caption,
        location_id=location.id if location else None,
    )
    db.session.add(post)
    db.session.flush()  # để lấy post.id trước khi commit, dùng gán cho Photo bên dưới

    upload_folder = os.path.join(current_app.root_path, "static", "uploads")
    os.makedirs(upload_folder, exist_ok=True)

    for file in files:
        media_type = get_media_type(file.filename)
        ext = secure_filename(file.filename).rsplit(".", 1)[1]
        unique_filename = f"{uuid.uuid4().hex}.{ext}"
        file.save(os.path.join(upload_folder, unique_filename))

        photo = Photo(
            post_id=post.id,
            file_path=f"static/uploads/{unique_filename}",
            media_type=media_type,
        )
        db.session.add(photo)

    db.session.commit()

    if is_browser_form:
        flash("Đăng bài viết thành công!", "success")
        return redirect(url_for("locations.feed"))

    return jsonify({"message": "Đăng bài thành công", "post_id": post.id}), 201

@locations_bp.route("/feed", methods=["GET"])
@login_required
def feed():
    from app.models import Follow

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

    # Trả về JSON nếu client yêu cầu hoặc qua API format=json
    if request.args.get("format") == "json" or (
        request.headers.get("Accept") == "application/json" and not request.accept_mimetypes.accept_html
    ):
        result = [
            {
                "post_id": p.id,
                "user_id": p.user_id,
                "caption": p.caption,
                "created_at": p.created_at.isoformat(),
                "media": [
                    {"file_path": ph.file_path, "media_type": ph.media_type}
                    for ph in Photo.query.filter_by(post_id=p.id).all()
                ],
            }
            for p in posts
        ]
        return jsonify({"feed": result})

    # Render Template HTML
    post_cards = []
    for p in posts:
        author = User.query.get(p.user_id)
        photos = Photo.query.filter_by(post_id=p.id).order_by(Photo.id.asc()).all()
        loc = Location.query.get(p.location_id) if p.location_id else None
        likes_count = Like.query.filter_by(post_id=p.id).count()
        is_liked = bool(Like.query.filter_by(user_id=current_user.id, post_id=p.id).first())
        comments = Comment.query.filter_by(post_id=p.id).order_by(Comment.created_at.asc()).all()
        comments_count = len(comments)
        is_saved = bool(SavedPost.query.filter_by(user_id=current_user.id, post_id=p.id).first())
        shares_count = Share.query.filter_by(post_id=p.id).count()

        formatted_comments = []
        for c in comments:
            c_author = User.query.get(c.user_id)
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

@locations_bp.route("/posts/<int:post_id>/like", methods=["POST"])
@login_required
def like_post(post_id):
    existing = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({"message": "Đã bỏ tim", "liked": False})

    like = Like(user_id=current_user.id, post_id=post_id)
    db.session.add(like)
    db.session.commit()
    return jsonify({"message": "Đã thả tim", "liked": True})
@locations_bp.route("/posts/<int:post_id>/comments", methods=["POST"])
@login_required
def create_comment(post_id):
    post = Post.query.get(post_id)

    if not post:
        return jsonify({"error": "Bài viết không tồn tại"}), 404

    data = request.get_json() or {}
    content = data.get("content", "").strip()

    if not content:
        return jsonify({"error": "Nội dung bình luận không được để trống"}), 400

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

@locations_bp.route("/posts/<int:post_id>/comments", methods=["GET"])
@login_required
def get_comments(post_id):
    post = Post.query.get(post_id)

    if not post:
        return jsonify({"error": "Bài viết không tồn tại"}), 404

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

@locations_bp.route("/comments/<int:comment_id>", methods=["DELETE"])
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get(comment_id)

    if not comment:
        return jsonify({"error": "Bình luận không tồn tại"}), 404

    if comment.user_id != current_user.id:
        return jsonify({"error": "Bạn không có quyền xóa bình luận này"}), 403

    db.session.delete(comment)
    db.session.commit()

    return jsonify({
        "message": "Xóa bình luận thành công"
    })

@locations_bp.route("/posts/<int:post_id>/share", methods=["POST"])
@login_required
def share_post(post_id):
    post = Post.query.get(post_id)

    if not post:
        return jsonify({"error": "Bài viết không tồn tại"}), 404


    share = Share(
        user_id=current_user.id,
        post_id=post_id
    )

    db.session.add(share)
    db.session.commit()

    return jsonify({
        "message": "Chia sẻ bài viết thành công",
        "share": {
            "id": share.id,
            "user_id": share.user_id,
            "post_id": share.post_id,
            "created_at": share.created_at.isoformat()
        }
    }), 201

@locations_bp.route("/posts/<int:post_id>/save", methods=["POST"])
@login_required
def save_post(post_id):
    post = Post.query.get(post_id)

    if not post:
        return jsonify({"error": "Bài viết không tồn tại"}), 404

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

@locations_bp.route("/locations", methods=["POST"])
@login_required
def create_location():
    """Tạo địa điểm mới — tự dedupe theo slug (Đà Lạt = Da Lat = DALAT)."""
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Tên địa điểm không được để trống"}), 400

    location = get_or_create_location(name)
    return jsonify({
        "location": {"id": location.id, "name": location.name, "slug": location.slug}
    }), 201


@locations_bp.route("/search", methods=["GET"])
@locations_bp.route("/locations/search", methods=["GET"])
@login_required
def search_locations():
    """Autocomplete — gõ vài ký tự trả về gợi ý địa điểm đã có."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"locations": []})

    query_slug = normalize_location_name(query)
    locations = (
        Location.query
        .filter(Location.slug.contains(query_slug))
        .limit(10)
        .all()
    )
    return jsonify({
        "locations": [
            {"id": l.id, "name": l.name, "slug": l.slug} for l in locations
        ]
    })