"""Model GES_PLACE — địa điểm cho tính năng GEs Around (ăn uống / giải trí / tham quan).

Nguồn: © OpenStreetMap contributors (ODbL) + Overture Maps Foundation (CDLA-Permissive-2.0 / Apache-2.0 / ODbL
tuỳ theme). Dữ liệu được nạp (seed) từ app/data/ges_places.csv.gz ở lần tìm kiếm đầu tiên khi bảng còn trống.
price_min/price_max để NULL = chưa có giá thật, hệ thống dùng ước tính theo loại hình (xem ges_around/config.py).
Không lưu bất kỳ toạ độ nào của người dùng.
"""
from app.extensions import db


class GesPlace(db.Model):
    __tablename__ = "ges_places"

    id = db.Column(db.String(24), primary_key=True)           # 'osm-n123' | 'ov-<hash>'
    name = db.Column(db.String(200), nullable=False)
    grp = db.Column(db.String(12), nullable=False, index=True)  # an_uong | giai_tri | tham_quan
    kind = db.Column(db.String(80), nullable=False, default="")
    lat = db.Column(db.Float, nullable=False, index=True)
    lon = db.Column(db.Float, nullable=False)
    src = db.Column(db.String(10), nullable=False, default="osm")  # osm | overture | manual
    brand = db.Column(db.String(120), nullable=True)
    addr = db.Column(db.String(200), nullable=True)
    hours = db.Column(db.String(200), nullable=True)
    web = db.Column(db.String(300), nullable=True)
    pop = db.Column(db.Integer, nullable=False, default=0)      # 0..2 độ "nổi tiếng/đủ thông tin" để xếp hạng
    price_min = db.Column(db.Integer, nullable=True)            # VND/người, NULL = chưa biết
    price_max = db.Column(db.Integer, nullable=True)
