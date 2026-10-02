"""Model LOCATION — định nghĩa địa điểm được gắn nhãn trong bài đăng.
"""
from datetime import datetime
from app.extensions import db

class Location(db.Model):
    __tablename__ = "locations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    address = db.Column(db.String(255), nullable=True)
    map_link = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Location {self.name}>'