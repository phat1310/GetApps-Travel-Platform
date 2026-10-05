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
            tables = inspector.get_table_names()
            with db.engine.connect() as conn:
                if 'users' in tables:
                    user_cols = [col['name'] for col in inspector.get_columns('users')]
                    if 'nickname' not in user_cols:
                        conn.execute(text("ALTER TABLE users ADD COLUMN nickname VARCHAR(64)"))
                    if 'profile_tag' not in user_cols:
                        conn.execute(text("ALTER TABLE users ADD COLUMN profile_tag VARCHAR(64) DEFAULT '#nguoidulich'"))
                    if 'secondary_email' not in user_cols:
                        conn.execute(text("ALTER TABLE users ADD COLUMN secondary_email VARCHAR(120)"))
                    if 'google_id' not in user_cols:
                        conn.execute(text("ALTER TABLE users ADD COLUMN google_id VARCHAR(64)"))
                    if 'tags' not in user_cols:
                        conn.execute(text("ALTER TABLE users ADD COLUMN tags VARCHAR(255) DEFAULT ''"))
                    if 'profile_completed' not in user_cols:
                        conn.execute(text("ALTER TABLE users ADD COLUMN profile_completed BOOLEAN DEFAULT 0"))
                    if 'is_private' not in user_cols:
                        conn.execute(text("ALTER TABLE users ADD COLUMN is_private BOOLEAN DEFAULT 0"))

                if 'posts' in tables:
                    post_cols = [col['name'] for col in inspector.get_columns('posts')]
                    if 'visibility' not in post_cols:
                        conn.execute(text("ALTER TABLE posts ADD COLUMN visibility VARCHAR(10) DEFAULT 'public'"))

                if 'shares' in tables:
                    share_cols = [col['name'] for col in inspector.get_columns('shares')]
                    if 'itinerary_id' not in share_cols:
                        conn.execute(text("ALTER TABLE shares ADD COLUMN itinerary_id INTEGER REFERENCES itineraries(id)"))

                if 'likes' in tables:
                    like_cols = [col['name'] for col in inspector.get_columns('likes')]
                    if 'itinerary_id' not in like_cols:
                        conn.execute(text("ALTER TABLE likes ADD COLUMN itinerary_id INTEGER REFERENCES itineraries(id)"))

                if 'comments' in tables:
                    cmt_cols = [col['name'] for col in inspector.get_columns('comments')]
                    if 'itinerary_id' not in cmt_cols:
                        conn.execute(text("ALTER TABLE comments ADD COLUMN itinerary_id INTEGER REFERENCES itineraries(id)"))

                if 'itineraries' in tables:
                    itin_cols = [col['name'] for col in inspector.get_columns('itineraries')]
                    if 'location_id' not in itin_cols:
                        conn.execute(text("ALTER TABLE itineraries ADD COLUMN location_id INTEGER REFERENCES locations(id)"))
                    if 'trip_type' not in itin_cols:
                        conn.execute(text("ALTER TABLE itineraries ADD COLUMN trip_type VARCHAR(50)"))
                    if 'participants_count' not in itin_cols:
                        conn.execute(text("ALTER TABLE itineraries ADD COLUMN participants_count INTEGER"))
                    if 'budget_estimate' not in itin_cols:
                        conn.execute(text("ALTER TABLE itineraries ADD COLUMN budget_estimate INTEGER"))

                if 'itinerary_stops' in tables:
                    stop_cols = [col['name'] for col in inspector.get_columns('itinerary_stops')]
                    if 'activity_name' not in stop_cols:
                        conn.execute(text("ALTER TABLE itinerary_stops ADD COLUMN activity_name VARCHAR(200)"))
                    if 'location_link' not in stop_cols:
                        conn.execute(text("ALTER TABLE itinerary_stops ADD COLUMN location_link VARCHAR(500)"))
                    if 'start_time' not in stop_cols:
                        conn.execute(text("ALTER TABLE itinerary_stops ADD COLUMN start_time TIME"))
                    if 'end_time' not in stop_cols:
                        conn.execute(text("ALTER TABLE itinerary_stops ADD COLUMN end_time TIME"))
                    if 'price' not in stop_cols:
                        conn.execute(text("ALTER TABLE itinerary_stops ADD COLUMN price INTEGER"))
                    if 'image_path' not in stop_cols:
                        conn.execute(text("ALTER TABLE itinerary_stops ADD COLUMN image_path VARCHAR(255)"))
                    if 'note' not in stop_cols:
                        conn.execute(text("ALTER TABLE itinerary_stops ADD COLUMN note TEXT"))

                if 'saved_posts' in tables:
                    sp_cols = [col['name'] for col in inspector.get_columns('saved_posts')]
                    if 'itinerary_id' not in sp_cols:
                        conn.execute(text("ALTER TABLE saved_posts ADD COLUMN itinerary_id INTEGER REFERENCES itineraries(id)"))

                if 'itinerary_lodgings' in tables:
                    lodg_cols = [col['name'] for col in inspector.get_columns('itinerary_lodgings')]
                    if 'itinerary_id' not in lodg_cols:
                        conn.execute(text("ALTER TABLE itinerary_lodgings ADD COLUMN itinerary_id INTEGER REFERENCES itineraries(id)"))
                    if 'name' not in lodg_cols:
                        conn.execute(text("ALTER TABLE itinerary_lodgings ADD COLUMN name VARCHAR(200)"))
                    if 'note' not in lodg_cols:
                        conn.execute(text("ALTER TABLE itinerary_lodgings ADD COLUMN note TEXT"))
                    if 'booking_link' not in lodg_cols:
                        conn.execute(text("ALTER TABLE itinerary_lodgings ADD COLUMN booking_link VARCHAR(500)"))

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