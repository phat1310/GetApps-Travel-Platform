"""Model LIKE — bản rút gọn, chỉ áp dụng cho Photo.
Cần mở rộng thêm để áp dụng cho Plan sau khi nhận bàn giao.
"""
from datetime import datetime
from app.extensions import db

class Like(db.Model):
    __tablename__ = "likes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    photo_id = db.Column(db.Integer, db.ForeignKey("photos.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("user_id", "photo_id", name="unique_like"),
    )