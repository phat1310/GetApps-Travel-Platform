"""Model LỊCH TRÌNH (Itinerary) — kế hoạch du lịch nhiều ngày, nhiều chặng.
Reuse Like/Comment/Share/SavedPost hiện có (thêm itinerary_id) thay vì tạo bảng riêng."""
from datetime import datetime
from app.extensions import db

class Itinerary(db.Model):
    __tablename__ = "itineraries"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    cover_image = db.Column(db.String(255), nullable=True)
    location_id = db.Column(db.Integer, db.ForeignKey("locations.id"), nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    trip_type = db.Column(db.String(50), nullable=True)   # "2N1D", "Phượt"...
    participants_count = db.Column(db.Integer, nullable=True)
    budget_estimate = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    days = db.relationship("ItineraryDay", backref="itinerary",
                            cascade="all, delete-orphan", order_by="ItineraryDay.day_number")
    lodgings = db.relationship("ItineraryLodging", backref="itinerary",
                                cascade="all, delete-orphan")
    attachments = db.relationship("ItineraryAttachment", backref="itinerary",
                                   cascade="all, delete-orphan")


class ItineraryDay(db.Model):
    __tablename__ = "itinerary_days"

    id = db.Column(db.Integer, primary_key=True)
    itinerary_id = db.Column(db.Integer, db.ForeignKey("itineraries.id"), nullable=False)
    day_number = db.Column(db.Integer, nullable=False)   # 1, 2, 3...

    stops = db.relationship("ItineraryStop", backref="day",
                             cascade="all, delete-orphan", order_by="ItineraryStop.order_index")


class ItineraryStop(db.Model):
    __tablename__ = "itinerary_stops"

    id = db.Column(db.Integer, primary_key=True)
    day_id = db.Column(db.Integer, db.ForeignKey("itinerary_days.id"), nullable=False)
    order_index = db.Column(db.Integer, nullable=False, default=0)
    start_time = db.Column(db.Time, nullable=True)
    end_time = db.Column(db.Time, nullable=True)
    activity_name = db.Column(db.String(200), nullable=False)
    location_link = db.Column(db.String(500), nullable=True)
    price = db.Column(db.Integer, nullable=True)
    image_path = db.Column(db.String(255), nullable=True)
    note = db.Column(db.Text, nullable=True)   # di chuyển: ghi lộ trình / ăn uống: giá+số người+địa chỉ


class ItineraryLodging(db.Model):
    __tablename__ = "itinerary_lodgings"

    id = db.Column(db.Integer, primary_key=True)
    itinerary_id = db.Column(db.Integer, db.ForeignKey("itineraries.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    price_per_night = db.Column(db.Integer, nullable=True)
    booking_link = db.Column(db.String(500), nullable=True)
    note = db.Column(db.Text, nullable=True)


class ItineraryAttachment(db.Model):
    __tablename__ = "itinerary_attachments"

    id = db.Column(db.Integer, primary_key=True)
    itinerary_id = db.Column(db.Integer, db.ForeignKey("itineraries.id"), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255), nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)