"""Package PLANS — Quản lý Lịch trình du lịch chuyến đi (Itinerary / Plan).
"""
from flask import Blueprint

plans_bp = Blueprint('plans', __name__)

from app.plans import routes
