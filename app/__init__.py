"""
Application Factory — nơi "ráp" toàn bộ ứng dụng lại thành 1 app Flask chạy được.
Mọi extension (db, login, migrate, jwt, csrf) và mọi Blueprint (auth, locations, api)
đều được gắn vào app TẠI ĐÂY, không gắn ở đâu khác.
Nếu thêm Blueprint mới, nhớ import + register_blueprint() thêm 1 dòng ở đây.
"""

from flask import Flask
from app.config import Config
from app.extensions import db, login_manager, migrate, jwt, csrf


def create_app(config_override=None):
    app = Flask(__name__)
    app.config.from_object(Config)

    # Cho phép test ghi đè config trước khi khởi tạo database
    if config_override:
        app.config.update(config_override)

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    csrf.init_app(app)

    with app.app_context():
        from app import models  # để Flask-Migrate thấy được model
        db.create_all()
        # Đảm bảo an toàn tương thích ngược cho DB SQLite cũ nếu thiếu cột mới
        try:
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            if 'users' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('users')]
                if 'nickname' not in columns:
                    with db.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE users ADD COLUMN nickname VARCHAR(64)"))
                        conn.commit()
                if 'profile_tag' not in columns:
                    with db.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE users ADD COLUMN profile_tag VARCHAR(64) DEFAULT '#nguoidulich'"))
                        conn.commit()
        except Exception:
            pass

    from app.auth import auth_bp
    from app.locations import locations_bp
    from app.api import api_bp
    from app.plans import plans_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(locations_bp, url_prefix="/locations")
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(plans_bp, url_prefix="/plans")

    csrf.exempt(api_bp)

    return app