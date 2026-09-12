from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
jwt = JWTManager()

@login_manager.user_loader
def load_user(user_id):
    from app.models import User
    return User.query.get(int(user_id))

"""
Extensions — khởi tạo các công cụ (db, login, migrate, jwt) ở dạng RỖNG,
chưa gắn vào app cụ thể. Việc gắn thật diễn ra trong app/__init__.py.
Tách riêng để tránh lỗi circular import giữa các Blueprint.
"""