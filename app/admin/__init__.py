"""
Blueprint ADMIN — khu vực quản trị: dashboard, quản lý user, quản lý post.
Mọi route trong đây PHẢI có @login_required + @admin_required (xem decorators.py).
Thiếu 1 trong 2 decorator đó = lỗ hổng Broken Access Control (OWASP A01:2021).
"""
from flask import Blueprint

admin_bp = Blueprint("admin", __name__, template_folder="../templates/admin")

from app.admin import routes  # noqa
