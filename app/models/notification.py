"""Model NOTIFICATION — thông báo tương tác của người dùng."""

from datetime import datetime
from app.extensions import db


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    actor_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    notification_type = db.Column(
        db.String(20),
        nullable=False
    )

    post_id = db.Column(
        db.Integer,
        db.ForeignKey("posts.id"),
        nullable=True
    )

    is_read = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    # Thông báo về LỊCH TRÌNH (post_id để trống). Xóa bài/lịch trình thì xóa luôn thông báo của nó.
    itinerary_id = db.Column(
        db.Integer,
        db.ForeignKey("itineraries.id"),
        nullable=True,
        index=True
    )

    actor = db.relationship("User", foreign_keys=[actor_id])
    post = db.relationship(
        "Post", foreign_keys=[post_id],
        backref=db.backref("notifications", cascade="all, delete-orphan")
    )
    itinerary = db.relationship(
        "Itinerary", foreign_keys=[itinerary_id],
        backref=db.backref("notifications", cascade="all, delete-orphan")
    )
