"""Model SHARE — các hình thức chia sẻ một bài viết Post."""

from datetime import datetime
from app.extensions import db


class Share(db.Model):
    __tablename__ = "shares"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    post_id = db.Column(
        db.Integer,
        db.ForeignKey("posts.id"),
        nullable=False
    )

    # Loại chia sẻ:
    # - download: tải hình ảnh về máy
    # - repost: đăng lại bài viết
    # - copy_link: sao chép liên kết
    share_type = db.Column(
        db.String(20),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )