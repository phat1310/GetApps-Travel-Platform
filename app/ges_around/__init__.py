"""Package GES_AROUND — "Có thời gian rảnh? Để GEs dẫn lối!"

Người dùng chọn thời gian rảnh, vị trí (khu vực HCM mới hoặc GPS), nhu cầu, phương tiện, ngân sách
→ trả về địa điểm gần đó mà đi-chơi-về kịp trong thời gian rảnh. Chỉ đường mở Google Maps (không nhúng bản đồ).
"""
from flask import Blueprint

ges_around_bp = Blueprint('ges_around', __name__)

from app.ges_around import routes  # noqa: E402,F401
