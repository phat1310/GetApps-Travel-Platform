"""Blueprint CHAT — nhắn tin 1-1 giữa những người đã follow nhau."""
from flask import Blueprint

chat_bp = Blueprint("chat", __name__)

from app.chat import routes  # noqa: E402,F401
