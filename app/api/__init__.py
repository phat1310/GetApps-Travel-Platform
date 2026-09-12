"""
Blueprint API — khu vực phụ trách: REST API có JWT (feed, upload, like, profile).
Route viết trong routes.py cùng thư mục.
"""
from flask import Blueprint
api_bp = Blueprint("api", __name__)
from app.api import routes  # noqa