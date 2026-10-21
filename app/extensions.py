from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Vui lòng đăng nhập để tiếp tục."
login_manager.login_message_category = "warning"
migrate = Migrate()
jwt = JWTManager()
csrf = CSRFProtect()

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