"""
Application Factory — nơi "ráp" toàn bộ ứng dụng lại thành 1 app Flask chạy được.
Mọi extension (db, login, migrate, jwt) và mọi Blueprint (auth, locations, api)
đều được gắn vào app TẠI ĐÂY, không gắn ở đâu khác.
Nếu thêm Blueprint mới, nhớ import + register_blueprint() thêm 1 dòng ở đây.
"""

from flask import Flask
from app.config import Config
from app.extensions import db, login_manager, migrate, jwt

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    with app.app_context():
        from app import models  # để Flask-Migrate thấy được model
        db.create_all()

    from app.auth import auth_bp
    from app.locations import locations_bp
    from app.api import api_bp
    from app.plans import plans_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(locations_bp, url_prefix="/locations")
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(plans_bp, url_prefix="/plans")

    return app
