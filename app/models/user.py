"""Model USER — định nghĩa bảng người dùng.
role là nhãn tự khai (local/traveler/creator/owner/user), KHÔNG dùng để phân quyền.
phone_number là thông tin liên hệ tự nhập, KHÔNG xác thực OTP (ngoài phạm vi đồ án).
"""
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="user")
    avatar_url = db.Column(db.String(255), nullable=True)
    bio = db.Column(db.String(255), nullable=True)
    phone_number = db.Column(db.String(20), nullable=True)
    nickname = db.Column(db.String(64), nullable=True)
    profile_tag = db.Column(db.String(64), default="#nguoidulich", nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'