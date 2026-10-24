from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter

def get_client_ip():
    """Lấy IP thực của client. Chỉ tin tưởng header proxy (CF-Connecting-IP, X-Forwarded-For)
    khi cấu hình TRUST_PROXY_HEADERS=1 (ví dụ chạy trong Docker đứng sau Cloudflare Tunnel / Nginx)
    để ngăn chặn lỗ hổng giả mạo IP (IP Spoofing) vượt qua Rate Limiting."""
    import os
    from flask import request, current_app
    trust_proxy = (
        os.environ.get("TRUST_PROXY_HEADERS", "0") == "1"
        or bool(current_app and current_app.config.get("TRUST_PROXY_HEADERS"))
    )
    if trust_proxy:
        if request.headers.get("CF-Connecting-IP"):
            return request.headers.get("CF-Connecting-IP").strip()
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.remote_addr or "127.0.0.1"

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Vui lòng đăng nhập để tiếp tục."
login_manager.login_message_category = "warning"
migrate = Migrate()
jwt = JWTManager()
csrf = CSRFProtect()
limiter = Limiter(
    key_func=get_client_ip,
    default_limits=["200 per minute", "2000 per hour"],
    storage_uri="memory://",
    strategy="fixed-window",
)

@login_manager.unauthorized_handler
def unauthorized():
    """Chưa đăng nhập mà dùng tính năng cần tài khoản: gọi từ JS (fetch/POST) -> JSON 401 để trang hiện khung
    "Cần đăng nhập"; mở trang bình thường -> chuyển tới trang đăng nhập (giữ ?next=)."""
    from flask import request, jsonify, redirect, url_for, flash
    fetch_mode = request.headers.get("Sec-Fetch-Mode", "navigate") != "navigate"
    if request.method != "GET" or fetch_mode or request.headers.get("X-Requested-With") == "XMLHttpRequest" \
            or request.accept_mimetypes.best == "application/json":
        return jsonify({"error": "Bạn cần đăng nhập để dùng tính năng này.", "login_required": True,
                        "login_url": url_for("auth.login")}), 401
    flash(login_manager.login_message, login_manager.login_message_category)
    return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))


@login_manager.user_loader
def load_user(user_id):
    from app.models import User
    return db.session.get(User, int(user_id))

"""
Extensions — khởi tạo các công cụ (db, login, migrate, jwt, csrf) ở dạng RỖNG,
chưa gắn vào app cụ thể. Việc gắn thật diễn ra trong app/__init__.py.
Tách riêng để tránh lỗi circular import giữa các Blueprint.
"""