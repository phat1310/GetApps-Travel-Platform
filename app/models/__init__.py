"""Nơi tập hợp import tất cả model — Flask-Migrate dựa vào đây để phát hiện bảng.
Thêm model mới thì thêm 1 dòng import ở đây, không thêm ở đâu khác.
"""
from app.models.user import User
from app.models.follow import Follow
from app.models.post import Post
from app.models.photo import Photo
from app.models.like import Like