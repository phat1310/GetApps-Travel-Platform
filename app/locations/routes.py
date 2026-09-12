"""Routes LOCATIONS — route upload ảnh tối giản.
Cần mở rộng thêm Place, Album, Tag.
"""
import os
import uuid
from flask import request, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.locations import locations_bp
from app.extensions import db
from app.models import Photo

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@locations_bp.route("/upload", methods=["POST"])
@login_required
def upload_photo():
    if "image" not in request.files:
        return jsonify({"error": "Thiếu file ảnh"}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "Chưa chọn file"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Định dạng file không hợp lệ"}), 400

    ext = secure_filename(file.filename).rsplit(".", 1)[1]
    unique_filename = f"{uuid.uuid4().hex}.{ext}"

    upload_folder = os.path.join(current_app.root_path, "static", "uploads")
    os.makedirs(upload_folder, exist_ok=True)
    file.save(os.path.join(upload_folder, unique_filename))

    caption = request.form.get("caption", "")
    photo = Photo(
        user_id=current_user.id,
        image_path=f"static/uploads/{unique_filename}",
        caption=caption,
    )
    db.session.add(photo)
    db.session.commit()

    return jsonify({"message": "Upload thành công", "photo_id": photo.id}), 201

@locations_bp.route("/feed", methods=["GET"])
@login_required
def feed():
    from app.models import Follow

    following_ids = [
        f.followed_id for f in Follow.query.filter_by(follower_id=current_user.id).all()
    ]

    photos = (
        Photo.query.filter(Photo.user_id.in_(following_ids))
        .order_by(Photo.created_at.desc())
        .all()
    )

    result = [
        {
            "photo_id": p.id,
            "user_id": p.user_id,
            "image_path": p.image_path,
            "caption": p.caption,
            "created_at": p.created_at.isoformat(),
        }
        for p in photos
    ]

    return jsonify({"feed": result})

from app.models import Like

@locations_bp.route("/photos/<int:photo_id>/like", methods=["POST"])
@login_required
def like_photo(photo_id):
    existing = Like.query.filter_by(user_id=current_user.id, photo_id=photo_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({"message": "Đã bỏ like", "liked": False})

    like = Like(user_id=current_user.id, photo_id=photo_id)
    db.session.add(like)
    db.session.commit()
    return jsonify({"message": "Đã like", "liked": True})