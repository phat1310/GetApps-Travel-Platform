"""Model PHOTO — bản rút gọn cho sườn (chưa có album/tag/place, Thành viên mở rộng).
"""
from datetime import datetime
from app.extensions import db

class Photo(db.Model):
    __tablename__ = "photos"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    image_path = db.Column(db.String(255), nullable=False)
    caption = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    