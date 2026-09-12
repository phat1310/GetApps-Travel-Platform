"""
Blueprint AUTH — khu vực phụ trách: đăng ký, đăng nhập, đăng xuất, Follow/Unfollow.
Route viết trong routes.py cùng thư mục. Không thêm logic của module khác vào đây.
"""
from flask import Blueprint
auth_bp = Blueprint("auth", __name__)
from app.auth import routes  # noqa