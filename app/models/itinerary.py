"""Model ITINERARY / PLAN — Quản lý Lịch trình du lịch phân cấp.
Gồm:
- Itinerary (Lịch trình tổng quan)
- ItineraryDay (Từng ngày trong chuyến đi)
- ItineraryStop (Các điểm dừng chân / tham quan theo ngày)
- ItineraryLodging (Nơi lưu trú / khách sạn theo ngày)
"""
from datetime import datetime
from app.extensions import db


class Itinerary(db.Model):
    """Lịch trình du lịch tổng quan."""
    __tablename__ = "itineraries"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    destination = db.Column(db.String(150), nullable=False)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    estimated_budget = db.Column(db.Float, default=0.0)
    currency = db.Column(db.String(10), default="VND")
    visibility = db.Column(db.String(20), default="public")  # 'public' hoặc 'private'
    cover_image = db.Column(db.String(255), nullable=True)
    attachment_file = db.Column(db.String(255), nullable=True)  # .pdf, .docx, .xlsx, .pptx
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    author = db.relationship("User", backref=db.backref("itineraries", lazy=True, cascade="all, delete-orphan"))
    days = db.relationship("ItineraryDay", backref="itinerary", lazy="select", cascade="all, delete-orphan", order_by="ItineraryDay.day_number")

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
                cost += float(s.estimated_cost or 0.0)
            for l in d.lodgings:
                cost += float(l.price_per_night or 0.0)
        return cost if cost > 0 else (self.estimated_budget or 0.0)

    def to_dict(self):
        """Chuyển đổi thành từ điển JSON phục vụ API."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "author_username": self.author.username if self.author else None,
            "author_avatar": self.author.avatar_url if self.author else None,
            "title": self.title,
            "destination": self.destination,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "total_days": self.total_days,
            "estimated_budget": self.estimated_budget,
            "currency": self.currency,
            "visibility": self.visibility,
            "cover_image": self.cover_image,
            "attachment_file": self.attachment_file,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
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

    # Relationships
    stops = db.relationship("ItineraryStop", backref="day", lazy="select", cascade="all, delete-orphan", order_by="ItineraryStop.order_index")
    lodgings = db.relationship("ItineraryLodging", backref="day", lazy="select", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "itinerary_id": self.itinerary_id,
            "day_number": self.day_number,
            "date": self.date.isoformat() if self.date else None,
            "title": self.title,
            "note": self.note,
            "stops": [s.to_dict() for s in self.stops],
            "lodgings": [l.to_dict() for l in self.lodgings]
        }


# Alias PlanDay
PlanDay = ItineraryDay


class ItineraryStop(db.Model):
    """Điểm dừng chân / Tham quan / Ẩm thực trong ngày."""
    __tablename__ = "itinerary_stops"

    id = db.Column(db.Integer, primary_key=True)
    day_id = db.Column(db.Integer, db.ForeignKey("itinerary_days.id"), nullable=False)
    order_index = db.Column(db.Integer, default=1)
    location_name = db.Column(db.String(150), nullable=False)
    address = db.Column(db.String(255), nullable=True)
    arrival_time = db.Column(db.String(20), nullable=True)  # "08:30"
    estimated_cost = db.Column(db.Float, default=0.0)
    transportation = db.Column(db.String(50), nullable=True)  # Xe máy, Taxi, Đi bộ, v.v.
    notes = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "day_id": self.day_id,
            "order_index": self.order_index,
            "location_name": self.location_name,
            "address": self.address,
            "arrival_time": self.arrival_time,
            "estimated_cost": self.estimated_cost,
            "transportation": self.transportation,
            "notes": self.notes
        }


# Alias PlanStop / PlanItem
PlanStop = ItineraryStop
PlanItem = ItineraryStop


class ItineraryLodging(db.Model):
    """Nơi lưu trú / Khách sạn / Homestay của ngày."""
    __tablename__ = "itinerary_lodgings"

    id = db.Column(db.Integer, primary_key=True)
    day_id = db.Column(db.Integer, db.ForeignKey("itinerary_days.id"), nullable=False)
    hotel_name = db.Column(db.String(150), nullable=False)
    address = db.Column(db.String(255), nullable=True)
    check_in_time = db.Column(db.String(20), nullable=True)
    price_per_night = db.Column(db.Float, default=0.0)
    booking_reference = db.Column(db.String(100), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "day_id": self.day_id,
            "hotel_name": self.hotel_name,
            "address": self.address,
            "check_in_time": self.check_in_time,
            "price_per_night": self.price_per_night,
            "booking_reference": self.booking_reference
        }


# Alias PlanLodging
PlanLodging = ItineraryLodging
