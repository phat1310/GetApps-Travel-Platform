"""Model COMMENT — bình luận của người dùng trên một Post hoặc Itinerary."""

from datetime import datetime
from app.extensions import db


class Comment(db.Model):
    __tablename__ = "comments"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )
    post_id = db.Column(
        db.Integer,
        db.ForeignKey("posts.id"),
        nullable=True          # ← đổi từ False thành True
    )
    itinerary_id = db.Column(                           # ← THÊM MỚI, đặt ngay sau post_id
        db.Integer,
        db.ForeignKey("itineraries.id"),
        nullable=True
    )
    parent_id = db.Column(                              # ← THÊM MỚI: trả lời 1 bình luận khác (chỉ 1 cấp, không lồng sâu hơn)
        db.Integer,
        db.ForeignKey("comments.id"),
        nullable=True
    )
    reply_to_id = db.Column(                            # ← THÊM MỚI: khi trả lời 1 reply (không phải bình luận gốc),
        db.Integer,                                     #   lưu đúng reply đó để hiện tag "@ai" + báo đúng người,
        db.ForeignKey("comments.id"),                   #   còn parent_id vẫn luôn trỏ về bình luận gốc (giữ lồng 1 cấp)
        nullable=True
    )
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    __table_args__ = (                                  # ← THÊM MỚI, đặt sau created_at, cùng cấp thụt lề với các Column
        db.CheckConstraint(
            "(post_id IS NOT NULL) != (itinerary_id IS NOT NULL)",
            name="chk_comment_target"
        ),
    )


class CommentLike(db.Model):
    """Lượt thả tim của 1 người vào 1 bình luận (mỗi người tối đa 1 tim / bình luận)."""
    __tablename__ = "comment_likes"

    id = db.Column(db.Integer, primary_key=True)
    comment_id = db.Column(db.Integer, db.ForeignKey("comments.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("comment_id", "user_id", name="unique_comment_like"),
    )