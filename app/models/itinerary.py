"""Model LỊCH TRÌNH (Itinerary / Plan) — kế hoạch du lịch nhiều ngày, nhiều chặng.
Hợp nhất đầy đủ giữa Backend CRUD của nhóm và Giao diện Lịch trình của Phát.
Gồm:
- Itinerary (Lịch trình tổng quan)
- ItineraryDay (Từng ngày trong chuyến đi)
- ItineraryStop (Các điểm dừng chân / tham quan / hoạt động theo ngày)
- ItineraryLodging (Nơi lưu trú / khách sạn / homestay)
- ItineraryAttachment (File đính kèm chuyến đi)
"""
from datetime import datetime
from app.extensions import db


class Itinerary(db.Model):
    """Lịch trình du lịch tổng quan."""
    __tablename__ = "itineraries"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    destination = db.Column(db.String(150), nullable=True, default="")
    description = db.Column(db.Text, nullable=True)
    cover_image = db.Column(db.String(255), nullable=True)
    location_id = db.Column(db.Integer, db.ForeignKey("locations.id"), nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    trip_type = db.Column(db.String(50), nullable=True)   # "2N1D", "Phượt"...
    participants_count = db.Column(db.Integer, nullable=True)
    budget_estimate = db.Column(db.Integer, nullable=True)
    estimated_budget = db.Column(db.Float, default=0.0)
    currency = db.Column(db.String(10), default="VND")
    visibility = db.Column(db.String(20), default="public")  # 'public' hoặc 'private'
    attachment_file = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    author = db.relationship("User", backref=db.backref("itineraries", lazy=True, cascade="all, delete-orphan"))
    days = db.relationship("ItineraryDay", backref="itinerary", lazy="select",
                            cascade="all, delete-orphan", order_by="ItineraryDay.day_number")
    lodgings = db.relationship("ItineraryLodging", backref="itinerary", lazy="select",
                                cascade="all, delete-orphan")
    attachments = db.relationship("ItineraryAttachment", backref="itinerary", lazy="select",
                                   cascade="all, delete-orphan")

    @property
    def total_days(self):
        """Tính tổng số ngày của chuyến đi."""
        if self.start_date and self.end_date:
            delta = (self.end_date - self.start_date).days + 1
            return max(delta, 1)
        return len(self.days) if self.days else 1

    @property
    def total_cost(self):
        """Tổng chi phí thực tế tính từ tất cả điểm dừng và lưu trú."""
        cost = 0.0
        for d in self.days:
            for s in d.stops:
                cost += float(s.estimated_cost or s.price or 0.0)
            for l in getattr(d, 'lodgings', []):
                cost += float(l.price_per_night or 0.0)
        if cost > 0:
            return cost
        return float(self.estimated_budget or self.budget_estimate or 0.0)

    def to_dict(self):
        """Chuyển đổi thành từ điển JSON phục vụ API."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "author_username": self.author.username if self.author else None,
            "author_avatar": self.author.avatar_url if self.author else None,
            "title": self.title,
            "destination": self.destination or "",
            "location_id": self.location_id,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "total_days": self.total_days,
            "trip_type": self.trip_type,
            "participants_count": self.participants_count,
            "estimated_budget": self.estimated_budget or self.budget_estimate,
            "currency": self.currency,
            "visibility": self.visibility,
            "cover_image": self.cover_image,
            "attachment_file": self.attachment_file,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "map_links": [m.to_dict() for m in (getattr(self, "map_links", None) or []) if m.safe_url],
            "days_count": len(self.days),
            "days": [d.to_dict() for d in self.days]
        }


# Alias Plan tương đương Itinerary để khớp với cả tài liệu thiết kế lẫn phân công nhóm
Plan = Itinerary


class ItineraryDay(db.Model):
    """Một ngày cụ thể trong hành trình (Ngày 1, Ngày 2...)."""
    __tablename__ = "itinerary_days"

    id = db.Column(db.Integer, primary_key=True)
    itinerary_id = db.Column(db.Integer, db.ForeignKey("itineraries.id"), nullable=False)
    day_number = db.Column(db.Integer, nullable=False, default=1)
    date = db.Column(db.Date, nullable=True)
    title = db.Column(db.String(150), nullable=True)  # Vd: "Khám phá trung tâm & Chợ đêm"
    note = db.Column(db.Text, nullable=True)
    distance_km = db.Column(db.Float, nullable=True)        # Khoảng cách di chuyển trong ngày (người dùng tự nhập)
    estimated_duration = db.Column(db.String(50), nullable=True)  # Thời gian dự kiến trong ngày, vd "~ 6 giờ"

    # Relationships
    stops = db.relationship("ItineraryStop", backref="day", lazy="select",
                             cascade="all, delete-orphan", order_by="ItineraryStop.order_index")
    lodgings = db.relationship("ItineraryLodging", backref="day", lazy="select",
                                cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "itinerary_id": self.itinerary_id,
            "day_number": self.day_number,
            "date": self.date.isoformat() if self.date else None,
            "title": self.title,
            "note": self.note,
            "distance_km": self.distance_km,
            "estimated_duration": self.estimated_duration,
            "stops": [s.to_dict() for s in self.stops],
            "lodgings": [l.to_dict() for l in self.lodgings]
        }


PlanDay = ItineraryDay


class ItineraryStop(db.Model):
    """Điểm dừng chân / Tham quan / Hoạt động trong ngày."""
    __tablename__ = "itinerary_stops"

    id = db.Column(db.Integer, primary_key=True)
    day_id = db.Column(db.Integer, db.ForeignKey("itinerary_days.id"), nullable=False)
    order_index = db.Column(db.Integer, default=0)
    location_name = db.Column(db.String(200), nullable=True)
    activity_name = db.Column(db.String(200), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    location_link = db.Column(db.String(500), nullable=True)
    arrival_time = db.Column(db.String(20), nullable=True)  # "08:30"
    start_time = db.Column(db.Time, nullable=True)
    end_time = db.Column(db.Time, nullable=True)
    estimated_cost = db.Column(db.Float, default=0.0)
    price = db.Column(db.Integer, nullable=True)
    transportation = db.Column(db.String(50), nullable=True)  # Xe máy, Taxi, Đi bộ, v.v.
    image_path = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    note = db.Column(db.Text, nullable=True)
    stop_type = db.Column(db.String(20), nullable=True)      # "food" | "sight" | "rest" | None (mặc định tham quan)
    suggested_food = db.Column(db.String(200), nullable=True)  # Món gợi ý (chỉ khi stop_type == "food")
    open_hours = db.Column(db.String(50), nullable=True)       # Giờ mở cửa dạng "07:00 - 22:00" (chỉ khi stop_type == "food")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.location_name and self.activity_name:
            self.location_name = self.activity_name
        elif not self.activity_name and self.location_name:
            self.activity_name = self.location_name
        if not self.notes and self.note:
            self.notes = self.note
        elif not self.note and self.notes:
            self.note = self.notes

    @property
    def safe_map_url(self):
        """Link Google Maps của chặng — kiểm tra lại khi HIỂN THỊ (dữ liệu cũ / sửa tay trong DB)."""
        from app.locations.maplinks import check_map_url
        if not self.location_link:
            return None
        url, err = check_map_url(self.location_link)
        return None if err else url

    def to_dict(self):
        return {
            "id": self.id,
            "day_id": self.day_id,
            "order_index": self.order_index,
            "location_name": self.location_name or self.activity_name,
            "activity_name": self.activity_name or self.location_name,
            "address": self.address,
            "location_link": self.location_link,
            "arrival_time": self.arrival_time,
            "estimated_cost": self.estimated_cost or self.price or 0.0,
            "transportation": self.transportation,
            "image_path": self.image_path,
            "notes": self.notes or self.note,
            "stop_type": self.stop_type,
            "suggested_food": self.suggested_food,
            "open_hours": self.open_hours
        }

    @property
    def type_label(self):
        return {"food": "Ăn uống", "sight": "Tham quan", "rest": "Nghỉ ngơi"}.get(self.stop_type, "Tham quan")

    @property
    def type_badge_class(self):
        return {"food": "pp-badge-food", "sight": "pp-badge-sight", "rest": "pp-badge-rest"}.get(self.stop_type, "pp-badge-sight")

    @property
    def type_icon_class(self):
        return {"food": "bi-cup-hot-fill", "sight": "bi-camera-fill", "rest": "bi-moon-stars-fill"}.get(self.stop_type, "bi-geo-alt-fill")


PlanStop = ItineraryStop
PlanItem = ItineraryStop


class ItineraryLodging(db.Model):
    """Nơi lưu trú / Khách sạn / Homestay."""
    __tablename__ = "itinerary_lodgings"

    id = db.Column(db.Integer, primary_key=True)
    itinerary_id = db.Column(db.Integer, db.ForeignKey("itineraries.id"), nullable=True)
    day_id = db.Column(db.Integer, db.ForeignKey("itinerary_days.id"), nullable=True)
    hotel_name = db.Column(db.String(200), nullable=True)
    name = db.Column(db.String(200), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    check_in_time = db.Column(db.String(20), nullable=True)
    check_out_time = db.Column(db.String(20), nullable=True)
    guest_count = db.Column(db.Integer, nullable=True)
    price_per_night = db.Column(db.Float, default=0.0)
    booking_reference = db.Column(db.String(100), nullable=True)
    booking_link = db.Column(db.String(500), nullable=True)
    map_link = db.Column(db.String(500), nullable=True)      # link Google Maps (dài hơn cột address)
    note = db.Column(db.Text, nullable=True)

    @property
    def safe_map_url(self):
        from app.locations.maplinks import check_map_url
        for cand in (self.map_link, self.address):          # dữ liệu cũ của Phát lưu link trong address
            if cand:
                url, err = check_map_url(cand)
                if not err:
                    return url
        return None

    @property
    def safe_booking_url(self):
        from app.locations.maplinks import check_web_url, looks_like_link
        raw = self.booking_link or ""
        if not looks_like_link(raw):
            return None
        url, err = check_web_url(raw)
        return None if err else url

    @property
    def booking_text(self):
        return None if self.safe_booking_url else (self.booking_link or None)

    @property
    def address_text(self):
        """Địa chỉ dạng chữ (không phải link)."""
        from app.locations.maplinks import looks_like_link
        a = self.address or ""
        return None if (not a or looks_like_link(a)) else a

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.name and self.hotel_name:
            self.name = self.hotel_name
        elif not self.hotel_name and self.name:
            self.hotel_name = self.name
        if not self.booking_link and self.booking_reference:
            self.booking_link = self.booking_reference
        elif not self.booking_reference and self.booking_link:
            self.booking_reference = self.booking_link

    def to_dict(self):
        return {
            "id": self.id,
            "day_id": self.day_id,
            "hotel_name": self.hotel_name or self.name,
            "name": self.name or self.hotel_name,
            "address": self.address,
            "check_in_time": self.check_in_time,
            "check_out_time": self.check_out_time,
            "guest_count": self.guest_count,
            "price_per_night": self.price_per_night,
            "booking_reference": self.booking_reference or self.booking_link,
            "booking_link": self.booking_link or self.booking_reference,
            "map_link": self.safe_map_url,
            "note": self.note
        }


PlanLodging = ItineraryLodging


class ItineraryAttachment(db.Model):
    """File đính kèm / tài liệu chuyến đi."""
    __tablename__ = "itinerary_attachments"

    id = db.Column(db.Integer, primary_key=True)
    itinerary_id = db.Column(db.Integer, db.ForeignKey("itineraries.id"), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255), nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
