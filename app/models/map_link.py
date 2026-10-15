"""Model MAP_LINK — liên kết Google Maps gắn vào bài viết hoặc lịch trình.

Mỗi dòng thuộc về ĐÚNG MỘT chủ sở hữu: post_id HOẶC itinerary_id (ràng buộc CHECK).
Giới hạn số lượng (bài viết 2, lịch trình 5) được kiểm tra ở server trong
app/locations/maplinks.py — giao diện chỉ là lớp tiện ích, không phải lớp bảo vệ.
"""
from datetime import datetime
from app.extensions import db


class MapLink(db.Model):
    __tablename__ = "map_links"

    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(500), nullable=False)
    label = db.Column(db.String(60), nullable=False, default="")
    position = db.Column(db.Integer, nullable=False, default=0)

    post_id = db.Column(db.Integer, db.ForeignKey("posts.id"), nullable=True, index=True)
    itinerary_id = db.Column(db.Integer, db.ForeignKey("itineraries.id"), nullable=True, index=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Xóa bài viết / lịch trình thì xóa luôn các link của nó
    post = db.relationship(
        "Post",
        backref=db.backref("map_links", cascade="all, delete-orphan", order_by="MapLink.position"),
    )
    itinerary = db.relationship(
        "Itinerary",
        backref=db.backref("map_links", cascade="all, delete-orphan", order_by="MapLink.position"),
    )

    __table_args__ = (
        db.CheckConstraint(
            "(post_id IS NOT NULL AND itinerary_id IS NULL) OR (post_id IS NULL AND itinerary_id IS NOT NULL)",
            name="ck_map_links_one_owner",
        ),
    )

    # --- Dùng trong template: luôn kiểm tra lại URL khi HIỂN THỊ (phòng dữ liệu cũ/bị sửa tay trong DB) ---
    @property
    def safe_url(self):
        from app.locations.maplinks import check_map_url
        url, err = check_map_url(self.url)
        return None if err else url

    @property
    def text(self):
        return (self.label or "").strip() or "Xem trên Google Maps"

    def to_dict(self):
        return {"url": self.safe_url, "label": self.label or "", "text": self.text}

    def __repr__(self):
        return f"<MapLink {self.id} {self.label!r}>"
