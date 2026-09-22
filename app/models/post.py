"""Model POST — bài viết, chứa nhiều ảnh/video (Photo) con."""
from datetime import datetime
from app.extensions import db


class Post(db.Model):
    __tablename__ = "posts"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    caption = db.Column(
        db.Text,
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    # Nếu bài này là repost thì lưu ID bài viết gốc
    # Nếu bài viết bình thường thì để NULL
    original_post_id = db.Column(
        db.Integer,
        db.ForeignKey("posts.id"),
        nullable=True
    )