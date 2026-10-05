"""Model SHARE — các hình thức chia sẻ (copy_link/download/repost) một bài viết Post hoặc Itinerary."""
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
        nullable=True
    )

    itinerary_id = db.Column(
        db.Integer,
        db.ForeignKey("itineraries.id"),
        nullable=True
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

    __table_args__ = (
        db.UniqueConstraint("user_id", "post_id", "share_type", name="unique_share_type_post"),
        db.UniqueConstraint("user_id", "itinerary_id", "share_type", name="unique_share_type_itinerary"),
        db.CheckConstraint("(post_id IS NOT NULL) != (itinerary_id IS NOT NULL)", name="chk_share_target"),
    )
