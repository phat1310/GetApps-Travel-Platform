"""Model PHOTO — 1 file ảnh/video thuộc về 1 Post.
Post có thể có nhiều Photo (tối đa 10, giới hạn kiểm tra ở route).
"""
from datetime import datetime
from app.extensions import db

class Photo(db.Model):
    __tablename__ = "photos"

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("posts.id"), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    media_type = db.Column(db.String(10), nullable=False, default="image")  # "image" hoặc "video"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)