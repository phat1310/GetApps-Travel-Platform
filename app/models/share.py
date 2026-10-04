"""Model SHARE — chia sẻ một bài viết Post hoặc Itinerary."""

from datetime import datetime
from app.extensions import db


class Share(db.Model):
    __tablename__ = "shares"

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
        db.UniqueConstraint("user_id", "post_id", name="unique_share"),
        db.UniqueConstraint("user_id", "itinerary_id", name="unique_share_itinerary"),
        db.CheckConstraint("(post_id IS NOT NULL) != (itinerary_id IS NOT NULL)", name="chk_share_target"),
    )
