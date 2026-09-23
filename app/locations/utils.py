"""Utils LOCATIONS — chuẩn hóa tên địa điểm để gộp các cách gõ khác nhau
về cùng 1 địa điểm trong database (vd: "Đà Lạt", "da lat", "DALAT").
"""
import unicodedata


def normalize_location_name(raw_name: str) -> str:
    """Trả về slug đã chuẩn hóa: bỏ dấu, viết thường, nối bằng dấu gạch ngang."""
    nfkd = unicodedata.normalize("NFD", raw_name.strip())
    no_accent = "".join(c for c in nfkd if unicodedata.category(c) != "Mn")
    no_accent = no_accent.replace("đ", "d").replace("Đ", "D")
    slug = "-".join(no_accent.lower().split())
    return slug


def get_or_create_location(raw_name: str, map_link: str = None):
    """Tìm địa điểm theo tên đã chuẩn hóa; nếu chưa có thì tạo mới.
    Trả về None nếu raw_name rỗng (bài đăng không gắn địa điểm).
    """
    from sqlalchemy.exc import IntegrityError
    from app.extensions import db
    from app.models import Location

    if not raw_name or not raw_name.strip():
        return None

    slug = normalize_location_name(raw_name)
    location = Location.query.filter_by(slug=slug).first()
    if location:
        return location  # đã tồn tại — giữ nguyên map_link cũ, không ghi đè

    try:
        location = Location(name=raw_name.strip(), slug=slug, map_link=map_link)
        db.session.add(location)
        db.session.commit()
        return location
    except IntegrityError:
        db.session.rollback()
        return Location.query.filter_by(slug=slug).first()