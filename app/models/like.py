"""Model LIKE — áp dụng cho Post hoặc Itinerary.
Mở rộng thêm để áp dụng cho Plan sau khi nhận bàn giao.
"""
from datetime import datetime
from app.extensions import db

class Like(db.Model):
    __tablename__ = "likes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("posts.id"), nullable=True)          # ① đổi False -> True
    itinerary_id = db.Column(db.Integer, db.ForeignKey("itineraries.id"), nullable=True)  # ② THIẾU — bạn chưa khai báo cột này

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("user_id", "post_id", name="unique_like"),
        db.UniqueConstraint("user_id", "itinerary_id", name="unique_like_itinerary"),
        db.CheckConstraint("(post_id IS NOT NULL) != (itinerary_id IS NOT NULL)", name="chk_like_target"),
    )