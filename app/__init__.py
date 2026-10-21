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
                    if 'full_name' not in user_cols:
                        conn.execute(text("ALTER TABLE users ADD COLUMN full_name VARCHAR(150)"))
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
                    if 'last_seen' not in user_cols:
                        conn.execute(text("ALTER TABLE users ADD COLUMN last_seen DATETIME"))
                    if 'show_activity' not in user_cols:
                        conn.execute(text("ALTER TABLE users ADD COLUMN show_activity BOOLEAN NOT NULL DEFAULT 1"))
                    if 'profile_bg' not in user_cols:
                        conn.execute(text("ALTER TABLE users ADD COLUMN profile_bg VARCHAR(255)"))

                if 'conversations' in tables:
                    conv_cols = [col['name'] for col in inspector.get_columns('conversations')]
                    if 'status' not in conv_cols:
                        conn.execute(text("ALTER TABLE conversations ADD COLUMN status VARCHAR(10) NOT NULL DEFAULT 'mutual'"))
                    if 'initiated_by' not in conv_cols:
                        conn.execute(text("ALTER TABLE conversations ADD COLUMN initiated_by INTEGER REFERENCES users(id)"))

                if 'posts' in tables:
                    post_cols = [col['name'] for col in inspector.get_columns('posts')]
                    if 'visibility' not in post_cols:
                        conn.execute(text("ALTER TABLE posts ADD COLUMN visibility VARCHAR(10) DEFAULT 'public'"))
                    if 'repost_note' not in post_cols:
                        conn.execute(text("ALTER TABLE posts ADD COLUMN repost_note TEXT"))
                    if 'edited_at' not in post_cols:
                        conn.execute(text("ALTER TABLE posts ADD COLUMN edited_at DATETIME"))
                    if 'edit_media_added' not in post_cols:
                        conn.execute(text("ALTER TABLE posts ADD COLUMN edit_media_added INTEGER NOT NULL DEFAULT 0"))

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
                    if 'map_link' not in lodg_cols:
                        conn.execute(text("ALTER TABLE itinerary_lodgings ADD COLUMN map_link VARCHAR(500)"))

                if 'notifications' in tables:
                    notif_cols = [col['name'] for col in inspector.get_columns('notifications')]
                    if 'itinerary_id' not in notif_cols:
                        conn.execute(text("ALTER TABLE notifications ADD COLUMN itinerary_id INTEGER REFERENCES itineraries(id)"))

                conn.commit()
        except Exception:
            pass

        # Lưới an toàn: DB SQLite cũ thiếu BẤT KỲ cột nào (cho phép NULL) mà model đang có -> tự thêm.
        # Mỗi cột thử riêng, lỗi 1 cột không làm hỏng các cột còn lại (khối ALTER thủ công ở trên dừng ở lỗi đầu tiên).
        try:
            from sqlalchemy import inspect as _inspect, text as _text
            _insp = _inspect(db.engine)
            _existing = set(_insp.get_table_names())
            for _table in db.metadata.sorted_tables:
                if _table.name not in _existing:
                    continue
                _have = {c['name'] for c in _insp.get_columns(_table.name)}
                for _col in _table.columns:
                    if _col.name in _have or _col.primary_key or not _col.nullable:
                        continue
                    try:
                        _ctype = _col.type.compile(dialect=db.engine.dialect)
                        with db.engine.begin() as _c:
                            _c.execute(_text(f'ALTER TABLE "{_table.name}" ADD COLUMN "{_col.name}" {_ctype}'))
                    except Exception:
                        pass
        except Exception:
            pass

    from app.auth import auth_bp
    from app.locations import locations_bp
    from app.api import api_bp
    from app.plans import plans_bp
    from app.chat import chat_bp
    from app.ges_around import ges_around_bp
    from app.presence import init_presence
    init_presence(app)
    from app.mentions import render_mentions
    app.jinja_env.filters['mentions'] = render_mentions      # {{ comment.content | mentions }}
    from app import timeutil
    app.jinja_env.globals['time_tag'] = timeutil.time_tag      # {{ time_tag(created_at, edited_at) }}
    app.jinja_env.globals['edited_clock'] = timeutil.edited_clock

    @app.context_processor
    def inject_notification_badge():
        """Số thông báo CHƯA ĐỌC cho chấm đỏ ở quả chuông (hiển thị ngay khi tải trang)."""
        from flask_login import current_user
        try:
            if current_user.is_authenticated:
                from app.notifications import unread_count
                return {"notif_unread": unread_count(current_user.id)}
        except Exception:
            db.session.rollback()
        return {"notif_unread": 0}

    app.register_blueprint(auth_bp)
    app.register_blueprint(locations_bp, url_prefix="/locations")
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(plans_bp, url_prefix="/plans")
    app.register_blueprint(chat_bp, url_prefix="/chat")
    app.register_blueprint(ges_around_bp, url_prefix="/ges-around")

    csrf.exempt(api_bp)

    return app