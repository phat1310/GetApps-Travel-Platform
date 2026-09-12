"""
Blueprint LOCATIONS — khu vực phụ trách: địa điểm (Place), upload ảnh (Photo).
Route viết trong routes.py cùng thư mục.
"""
from flask import Blueprint
locations_bp = Blueprint("locations", __name__)
from app.locations import routes  # noqa