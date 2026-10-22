"""Script CHẠY MỘT LẦN: nối lịch trình cũ vào bảng Location và gộp địa điểm trùng.

Cách dùng (từ thư mục gốc dự án, đã bật venv):
    python scripts/link_itinerary_locations.py            # chạy THỬ, chỉ in ra, không ghi DB
    python scripts/link_itinerary_locations.py --apply    # ghi thật vào DB

Việc làm:
  1. Với mỗi Itinerary chưa có location_id: làm sạch destination (bỏ '#', cắt phần sau dấu phẩy,
     tách 'HạLong' -> 'Hạ Long') rồi gắn vào Location (tạo mới nếu chưa có).
  2. Gộp các Location bị tách đôi do cách gõ ('HạLong' / 'Hạ Long'): chuyển bài viết, lịch trình,
     địa điểm phụ sang bản chuẩn rồi xóa bản trùng.
Nên sao lưu file .db (instance/*.db) trước khi chạy với --apply.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import Itinerary, Location, Post
from app.models.post import post_extra_locations
from app.locations.discovery import clean_destination
from app.locations.utils import normalize_location_name


def main(apply):
    app = create_app()
    with app.app_context():
        tag = "GHI THẬT" if apply else "CHẠY THỬ (không ghi DB)"
        print(f"=== {tag} ===")

        # --- 1. Nối lịch trình cũ ---
        linked = 0
        for it in Itinerary.query.filter(Itinerary.location_id.is_(None)).all():
            name = clean_destination(it.destination)
            if not name:
                continue
            slug = normalize_location_name(name)
            loc = Location.query.filter_by(slug=slug).first()
            if loc is None:
                loc = Location(name=name, slug=slug)
                db.session.add(loc)
                db.session.flush()
                print(f"  + tạo địa điểm mới: {name!r}")
            it.location_id = loc.id
            linked += 1
            print(f"  lịch trình #{it.id} {it.destination!r} -> {loc.name!r}")
        print(f"Đã nối {linked} lịch trình.")

        # --- 2. Gộp địa điểm trùng (tên bị dính chữ / có dấu phẩy...) ---
        merged = 0
        for loc in Location.query.order_by(Location.id).all():
            if db.session.get(Location, loc.id) is None:
                continue
            clean = clean_destination(loc.name)
            if not clean or clean == loc.name:
                continue
            new_slug = normalize_location_name(clean)
            target = Location.query.filter(Location.slug == new_slug, Location.id != loc.id).first()
            if target is None:
                print(f"  đổi tên địa điểm #{loc.id}: {loc.name!r} -> {clean!r}")
                loc.name, loc.slug = clean, new_slug
                continue
            print(f"  gộp địa điểm #{loc.id} {loc.name!r} vào #{target.id} {target.name!r}")
            Post.query.filter_by(location_id=loc.id).update({"location_id": target.id})
            Itinerary.query.filter_by(location_id=loc.id).update({"location_id": target.id})
            # địa điểm phụ của bài viết: chuyển sang bản chuẩn (tránh trùng khóa chính)
            rows = db.session.execute(post_extra_locations.select().where(post_extra_locations.c.location_id == loc.id)).fetchall()
            for r in rows:
                exists = db.session.execute(post_extra_locations.select().where(
                    (post_extra_locations.c.post_id == r.post_id) & (post_extra_locations.c.location_id == target.id))).first()
                if not exists:
                    db.session.execute(post_extra_locations.insert().values(post_id=r.post_id, location_id=target.id))
            db.session.execute(post_extra_locations.delete().where(post_extra_locations.c.location_id == loc.id))
            db.session.delete(loc)
            merged += 1
        print(f"Đã gộp {merged} địa điểm trùng.")

        if apply:
            db.session.commit()
            print("Đã ghi vào database.")
        else:
            db.session.rollback()
            print("Chưa ghi gì. Thêm --apply để ghi thật.")


if __name__ == "__main__":
    main("--apply" in sys.argv)
