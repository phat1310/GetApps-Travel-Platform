"""Routes LOCATIONS — route đăng bài (nhiều ảnh/video), bảng tin, like.
Cần mở rộng thêm Place, Album, Tag.
"""
import os
import uuid
from flask import request, jsonify, current_app, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.locations import locations_bp
from app.extensions import db
from app.models import Post, Photo, Like, Comment, Share, SavedPost

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


@locations_bp.route("/posts/<int:post_id>/share/download", methods=["GET"])
@login_required
def download_post(post_id):
    post = Post.query.get(post_id)

    if not post:
        return jsonify({
            "error": "Bài viết không tồn tại"
        }), 404

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

    filename = os.path.basename(photo.file_path)

    full_path = os.path.join(
        upload_folder,
        filename
    )

    if not os.path.exists(full_path):
        return jsonify({
            "error": "File không tồn tại trên server"
        }), 404

    share = Share(
        user_id=current_user.id,
        post_id=post_id,
        share_type="download"
    )

    db.session.add(share)
    db.session.commit()

    return send_from_directory(
        upload_folder,
        filename,
        as_attachment=True
    )

@locations_bp.route("/posts/<int:post_id>/share", methods=["POST"])
@login_required
def share_post(post_id):
    post = Post.query.get(post_id)

    if not post:
        return jsonify({"error": "Bài viết không tồn tại"}), 404

    share = Share(
        user_id=current_user.id,
        post_id=post_id,
        share_type="copy_link"
    )

    db.session.add(share)
    db.session.commit()

    link = f"http://127.0.0.1:5000/locations/posts/{post_id}"

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

@locations_bp.route("/posts/<int:post_id>/repost", methods=["POST"])
@login_required
def repost_post(post_id):
    original_post = Post.query.get(post_id)

    if not original_post:
        return jsonify({
            "error": "Bài viết không tồn tại"
        }), 404

    repost = Post(
        user_id=current_user.id,
        caption=original_post.caption,
        original_post_id=original_post.id
    )

    db.session.add(repost)
    db.session.flush()

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