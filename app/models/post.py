"""Model POST — bài viết, chứa nhiều ảnh/video (Photo) con."""

from datetime import datetime
from app.extensions import db


post_extra_locations = db.Table(
    "post_extra_locations",
    db.Column(
        "post_id",
        db.Integer,
        db.ForeignKey("posts.id"),
        primary_key=True
    ),
    db.Column(
        "location_id",
        db.Integer,
        db.ForeignKey("locations.id"),
        primary_key=True
    ),
)


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

    visibility = db.Column(
        db.String(10),
        nullable=False,
        default="public"
    )

    location_id = db.Column(
        db.Integer,
        db.ForeignKey("locations.id"),
        nullable=True
    )

    extra_locations = db.relationship(
        "Location",
        secondary=post_extra_locations
    )

    # Nếu đây là bài repost, lưu ID của bài viết gốc
    original_post_id = db.Column(
        db.Integer,
        db.ForeignKey("posts.id"),
        nullable=True
    )

    # Ghi chú của người đăng lại (chỉ dùng cho repost)
    repost_note = db.Column(
        db.Text,
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    # Thời điểm chủ bài chỉnh sửa nội dung lần gần nhất (None = chưa từng sửa)
    edited_at = db.Column(db.DateTime, nullable=True)

    # Số ảnh/video đã thêm bằng chức năng Chỉnh sửa (tối đa 2 trong cả vòng đời bài)
    edit_media_added = db.Column(db.Integer, nullable=False, default=0, server_default="0")

    # Admin KHÓA bài (nghi ngờ vi phạm) -> ẩn khỏi mọi nơi (feed/profile/chi tiết) với
    # TẤT CẢ người dùng khác, trừ admin và chính chủ bài. Không xóa dữ liệu, có thể mở khóa lại.
    is_hidden = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
