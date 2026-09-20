"""Routes LOCATIONS — route đăng bài (nhiều ảnh/video), bảng tin, like.
Cần mở rộng thêm Place, Album, Tag.
"""
import os
import uuid
from flask import request, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.locations import locations_bp
from app.extensions import db
from app.models import Post, Photo, Like

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

@locations_bp.route("/upload", methods=["POST"])
@login_required
def create_post():
    files = request.files.getlist("images")
    if not files or files[0].filename == "":
        return jsonify({"error": "Thiếu ít nhất 1 file ảnh/video"}), 400

    if len(files) > MAX_FILES_PER_POST:
        return jsonify({"error": f"Tối đa {MAX_FILES_PER_POST} file mỗi bài viết"}), 400

    for file in files:
        if get_media_type(file.filename) is None:
            return jsonify({"error": f"File '{file.filename}' sai định dạng"}), 400

    caption = request.form.get("caption", "")
    post = Post(user_id=current_user.id, caption=caption)
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

    return jsonify({"message": "Đăng bài thành công", "post_id": post.id}), 201

@locations_bp.route("/feed", methods=["GET"])
@login_required
def feed():
    from app.models import Follow

    following_ids = [
        f.followed_id for f in Follow.query.filter_by(follower_id=current_user.id).all()
    ]

    posts = (
        Post.query.filter(Post.user_id.in_(following_ids))
        .order_by(Post.created_at.desc())
        .all()
    )

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