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

@login_manager.user_loader
def load_user(user_id):
    from app.models import User
    return db.session.get(User, int(user_id))

"""
Extensions — khởi tạo các công cụ (db, login, migrate, jwt, csrf) ở dạng RỖNG,
chưa gắn vào app cụ thể. Việc gắn thật diễn ra trong app/__init__.py.
Tách riêng để tránh lỗi circular import giữa các Blueprint.
"""