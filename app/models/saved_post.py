"""Model SAVED POST — bài viết hoặc lịch trình được người dùng lưu lại."""

from datetime import datetime
from app.extensions import db


class SavedPost(db.Model):
    __tablename__ = "saved_posts"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    post_id = db.Column(
        db.Integer,
        db.ForeignKey("posts.id"),
        nullable=True
    )

    itinerary_id = db.Column(
        db.Integer,
        db.ForeignKey("itineraries.id"),
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    __table_args__ = (
        db.UniqueConstraint("user_id", "post_id", name="unique_saved_post"),
        db.UniqueConstraint("user_id", "itinerary_id", name="unique_saved_itinerary"),
        db.CheckConstraint("(post_id IS NOT NULL) != (itinerary_id IS NOT NULL)", name="chk_saved_target"),
    )
