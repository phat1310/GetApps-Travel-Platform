"""DISCOVERY — làm sạch điểm đến, địa điểm nổi bật, gợi ý kết nối, quyền xem bài.

Tách riêng khỏi routes.py để các nhánh (Phát: plans, Trúc: auth) chỉ cần import vài hàm nhỏ.
"""
import re
import unicodedata

from sqlalchemy import func, or_

from app.extensions import db


# ------------------------------------------------------------------
# 1. LÀM SẠCH ĐIỂM ĐẾN LỊCH TRÌNH
# ------------------------------------------------------------------

def clean_destination(raw):
    """'#ĐàLạt' -> 'Đà Lạt' ; 'Đà Lạt, Lâm Đồng' -> 'Đà Lạt' ; 'HạLong' -> 'Hạ Long'.

    Bỏ '#', lấy phần trước dấu phẩy đầu tiên, tách chữ dính liền kiểu CamelCase, gọn khoảng trắng.
    Trả '' nếu không còn gì.
    """
    if not raw:
        return ""
    s = str(raw).replace("#", " ")
    s = re.split(r"[,;/|]", s, maxsplit=1)[0]
    out = []
    prev = ""
    for ch in s:
        if prev and prev.islower() and ch.isupper():
            out.append(" ")
        out.append(ch)
        prev = ch
    s = re.sub(r"\s+", " ", "".join(out)).strip()
    return s[:120]


def link_destination(destination):
    """Trả về Location (tạo mới nếu chưa có) cho 1 điểm đến lịch trình, hoặc None."""
    from app.locations.utils import get_or_create_location
    name = clean_destination(destination)
    return get_or_create_location(name) if name else None


# ------------------------------------------------------------------
# 2. ĐỊA ĐIỂM NỔI BẬT = số bài đăng + số lịch trình công khai
# ------------------------------------------------------------------

def popular_locations(limit=10):
    from app.models import Post, Itinerary, Location
    from app.models.post import post_extra_locations

    hidden = hidden_account_ids() or [0]
    posts = {}
    q = (db.session.query(Post.location_id, func.count(Post.id))
         .filter(Post.location_id.isnot(None), Post.original_post_id.is_(None), Post.visibility == "public",
                 Post.user_id.notin_(hidden))
         .group_by(Post.location_id))
    for lid, n in q:
        posts[lid] = posts.get(lid, 0) + n
    q = (db.session.query(post_extra_locations.c.location_id, func.count(Post.id))
         .join(Post, Post.id == post_extra_locations.c.post_id)
         .filter(Post.original_post_id.is_(None), Post.visibility == "public", Post.user_id.notin_(hidden))
         .group_by(post_extra_locations.c.location_id))
    for lid, n in q:
        posts[lid] = posts.get(lid, 0) + n

    plans = {}
    q = (db.session.query(Itinerary.location_id, func.count(Itinerary.id))
         .filter(Itinerary.location_id.isnot(None), or_(Itinerary.visibility == "public", Itinerary.visibility.is_(None)),
                 Itinerary.user_id.notin_(hidden))
         .group_by(Itinerary.location_id))
    for lid, n in q:
        plans[lid] = n

    ids = set(posts) | set(plans)
    if not ids:
        return []
    locs = {l.id: l for l in Location.query.filter(Location.id.in_(ids)).all()}
    rows = []
    for lid in ids:
        loc = locs.get(lid)
        if not loc:
            continue
        p, i = posts.get(lid, 0), plans.get(lid, 0)
        rows.append({"id": loc.id, "name": loc.name, "address": loc.address, "posts": p, "plans": i, "score": p + i})
    rows.sort(key=lambda r: (-r["score"], r["name"].lower()))
    return rows[:limit]


# ------------------------------------------------------------------
# 3. QUYỀN XEM BÀI (private = CHỈ chủ bài; tài khoản riêng tư = cần follow)
# ------------------------------------------------------------------

def following_ids(user_id):
    from app.models import Follow
    return {f.followed_id for f in Follow.query.filter_by(follower_id=user_id).all()}


def root_post(post):
    """Bài gốc thật sự của một repost (đi ngược chuỗi repost-của-repost). None nếu gốc đã bị xóa."""
    from app.models import Post
    seen = set()
    cur = post
    while cur is not None and cur.original_post_id and cur.id not in seen:
        seen.add(cur.id)
        cur = db.session.get(Post, cur.original_post_id)
    return cur


def account_hidden(author_id, viewer_id, follow_set):
    """True nếu tác giả để TÀI KHOẢN riêng tư và người xem không phải chính chủ / chưa follow."""
    if author_id is None or author_id == viewer_id:
        return False
    from app.models import User
    author = db.session.get(User, author_id)
    if author is None or not getattr(author, "is_private", False):
        return False
    return author_id not in (follow_set or ())


def can_view_post(post, viewer_id, follow_set):
    """Quyền xem 1 bài.

    - Chủ bài luôn xem được.
    - Bài đặt 'riêng tư' (private) -> CHỈ chủ bài thấy, kể cả follower cũng không.
    - Tác giả để tài khoản riêng tư -> chỉ người đang follow mới thấy bài công khai.
    - Repost: phải xem được cả bài gốc thật sự (gốc bị xóa/riêng tư/tài khoản kín -> ẩn).
    """
    if post.user_id != viewer_id:
        if post.visibility == "private":
            return False
        if account_hidden(post.user_id, viewer_id, follow_set):
            return False
    if post.original_post_id:
        src = root_post(post)
        if src is None:
            return False
        if src.user_id != viewer_id:
            if src.visibility == "private":
                return False
            if account_hidden(src.user_id, viewer_id, follow_set):
                return False
    return True


def can_view_itinerary(it, viewer_id, follow_set):
    """Quyền xem 1 lịch trình: chủ luôn thấy; 'private' chỉ chủ; tài khoản kín -> cần follow."""
    if it.user_id == viewer_id:
        return True
    if (it.visibility or "public") == "private":
        return False
    return not account_hidden(it.user_id, viewer_id, follow_set)


def viewer_follow_set(viewer_id):
    """Tập id người mà viewer đang follow (rỗng nếu chưa đăng nhập)."""
    return following_ids(viewer_id) if viewer_id else set()


def hidden_account_ids():
    """Id các tài khoản đang để riêng tư (dùng để loại khỏi thống kê chung)."""
    from app.models import User
    return [u.id for u in User.query.filter_by(is_private=True).with_entities(User.id).all()]


# ------------------------------------------------------------------
# 4. GỢI Ý KẾT NỐI — 5 người
# ------------------------------------------------------------------

def suggest_users(me_id, limit=5):
    """Người đã đăng ≥1 bài công khai (gốc) xếp theo tổng tim + bình luận; chưa ai đăng thì lấy
    những người đăng ký sớm nhất. Luôn loại bản thân và người đã follow; bù cho đủ `limit`."""
    from app.models import User, Post, Like, Comment

    skip = following_ids(me_id) | {me_id}

    base = (Post.original_post_id.is_(None), Post.visibility == "public", Post.user_id.notin_(hidden_account_ids() or [0]))
    post_cnt = dict(db.session.query(Post.user_id, func.count(Post.id)).filter(*base).group_by(Post.user_id).all())
    likes = dict(db.session.query(Post.user_id, func.count(Like.id))
                 .join(Like, Like.post_id == Post.id).filter(*base).group_by(Post.user_id).all())
    cmts = dict(db.session.query(Post.user_id, func.count(Comment.id))
                .join(Comment, Comment.post_id == Post.id).filter(*base).group_by(Post.user_id).all())

    active = [uid for uid in post_cnt if uid not in skip]
    active.sort(key=lambda uid: (-(likes.get(uid, 0) + cmts.get(uid, 0)), -post_cnt[uid], uid))
    chosen = active[:limit]

    if len(chosen) < limit:
        rest = (User.query.filter(~User.id.in_(list(skip | set(chosen)) or [0]))
                .order_by(User.created_at.asc(), User.id.asc()).limit(limit - len(chosen)).all())
        chosen += [u.id for u in rest]

    users = {u.id: u for u in User.query.filter(User.id.in_(chosen or [0])).all()}
    return [users[i] for i in chosen if i in users]


# ------------------------------------------------------------------
# tiện ích chuẩn hóa tên (tìm kiếm không dấu)
# ------------------------------------------------------------------

def norm_text(text):
    s = unicodedata.normalize("NFD", text or "").replace("đ", "d").replace("Đ", "D")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", "", s).lower()
