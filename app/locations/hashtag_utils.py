"""Utils HASHTAG — chuẩn hóa hashtag và tìm/tạo hashtag.
"#Đà Lạt", "#dalat", "DALAT" đều quy về "dalat" (bỏ dấu, chữ thường, chỉ giữ a-z 0-9 _).
"""
import re
import unicodedata

from app.extensions import db
from app.models.hashtag import Hashtag

MAX_HASHTAGS_PER_POST = 3
MAX_HASHTAG_LENGTH = 30


def normalize_hashtag(raw: str) -> str:
    text = unicodedata.normalize("NFD", (raw or "").strip())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.replace("đ", "d").replace("Đ", "D").lower()
    return re.sub(r"[^a-z0-9_]", "", text)


def parse_hashtags(raw_values):
    """raw_values: list chuỗi lấy từ request.form.getlist("hashtags").
    Mỗi chuỗi có thể chứa nhiều hashtag, ngăn cách bằng dấu cách, dấu phẩy hoặc #.
    Trả về (danh sách hashtag đã chuẩn hóa, không trùng, giữ thứ tự; thông báo lỗi hoặc None).
    """
    names = []
    for raw in raw_values:
        for part in re.split(r"[,\s#]+", raw or ""):
            name = normalize_hashtag(part)
            if not name:
                continue
            if len(name) > MAX_HASHTAG_LENGTH:
                return None, f"Mỗi hashtag tối đa {MAX_HASHTAG_LENGTH} ký tự"
            if name not in names:
                names.append(name)

    if len(names) > MAX_HASHTAGS_PER_POST:
        return None, f"Tối đa {MAX_HASHTAGS_PER_POST} hashtag mỗi bài viết"
    return names, None


def get_or_create_hashtag(name: str) -> Hashtag:
    """Tìm hashtag theo tên, chưa có thì tạo. KHÔNG commit, để nằm trong cùng
    transaction với bài viết (bài lỗi thì hashtag cũng rollback)."""
    tag = Hashtag.query.filter_by(name=name).first()
    if tag:
        return tag
    tag = Hashtag(name=name)
    db.session.add(tag)
    return tag

from sqlalchemy import func
from app.models.hashtag import post_hashtags

DEFAULT_TRENDING_HASHTAGS = [
    "nguoidulich",
    "khongquangcao",
    "dalat",
    "travelreview",
    "checkin",
    "vietnam",
    "dulich",
    "phuot",
    "foodreview",
    "homestay",
]


def get_top_hashtags(limit=10):
    """Lấy danh sách tối đa `limit` hashtag được sử dụng nhiều nhất trong hệ thống.
    Nếu chưa đủ dữ liệu thực tế hoặc ngoài app context, bù thêm các hashtag du lịch phổ biến mặc định."""
    names = []
    from flask import has_app_context
    if has_app_context():
        try:
            rows = (
                db.session.query(Hashtag.name, func.count(post_hashtags.c.post_id).label("cnt"))
                .join(post_hashtags, Hashtag.id == post_hashtags.c.hashtag_id)
                .group_by(Hashtag.id, Hashtag.name)
                .order_by(db.desc("cnt"), Hashtag.id.asc())
                .limit(limit)
                .all()
            )
            names = [r[0] for r in rows if r[0]]
        except Exception:
            db.session.rollback()
            names = []

    for d in DEFAULT_TRENDING_HASHTAGS:
        if len(names) >= limit:
            break
        if d not in names:
            names.append(d)

    return [f"#{n}" if not n.startswith("#") else n for n in names[:limit]]

