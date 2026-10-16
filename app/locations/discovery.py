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
    # Gộp phường/xã về tỉnh/thành cha (chỉ cộng số liệu công khai đã lọc ở trên nên không lộ nội dung riêng tư)
    top = {lid: (locs[lid].parent_id or lid) for lid in ids if lid in locs}
    need = {t for t in top.values() if t not in locs}
    if need:
        locs.update({l.id: l for l in Location.query.filter(Location.id.in_(list(need))).all()})
    agg_p, agg_i = {}, {}
    for lid, t in top.items():
        agg_p[t] = agg_p.get(t, 0) + posts.get(lid, 0)
        agg_i[t] = agg_i.get(t, 0) + plans.get(lid, 0)
    posts, plans, ids = agg_p, agg_i, set(agg_p)
    rows = []
    for lid in ids:
        loc = locs.get(lid)
        if not loc:
            continue
        p, i = posts.get(lid, 0), plans.get(lid, 0)
        rows.append({"id": loc.id, "code": loc.code, "name": loc.name, "address": loc.address, "posts": p, "plans": i, "score": p + i})
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


# ------------------------------------------------------------------
# 6. NGƯỜI ĐÃ THẢ TIM + THẺ HỒ SƠ Ở BẢNG TIN
# ------------------------------------------------------------------

def likers_of(user_id):
    """Những người đã thả tim BẤT KỲ bài viết nào của `user_id` — mỗi người đúng 1 dòng (không tính chính chủ).

    Trả [(liker_id, số_bài_đã_tim, lần_tim_gần_nhất)], người tim gần đây nhất ở đầu.
    GROUP BY người tim nên 1 người tim 10 bài vẫn chỉ là 1 dòng; DISTINCT post_id đề phòng dữ liệu trùng."""
    from app.models import Like, Post
    last = func.max(Like.created_at)
    return (db.session.query(Like.user_id, func.count(func.distinct(Like.post_id)), last)
            .join(Post, Post.id == Like.post_id)
            .filter(Post.user_id == user_id, Like.user_id != user_id)
            .group_by(Like.user_id)
            .order_by(last.desc(), Like.user_id.desc())
            .all())


def liker_count(user_id):
    """Số NGƯỜI (không phải số lượt) đã thả tim bài viết của `user_id`."""
    from app.models import Like, Post
    return (db.session.query(func.count(func.distinct(Like.user_id)))
            .join(Post, Post.id == Like.post_id)
            .filter(Post.user_id == user_id, Like.user_id != user_id)
            .scalar()) or 0


def _title_and_desc(caption):
    """Tách nội dung bài thành tiêu đề (dòng đầu, gọn) + mô tả (phần còn lại)."""
    lines = [l.strip() for l in (caption or "").splitlines() if l.strip()]
    if not lines:
        return "", ""
    first, rest = lines[0], lines[1:]
    if len(first) > 70:
        cut = first[:70].rsplit(" ", 1)[0] or first[:70]
        rest = [first[len(cut):].strip()] + rest
        first = cut.rstrip(",.;: ") + "…"
    return first, " ".join(x for x in rest if x)[:220]


def profile_card(user):
    """Dữ liệu cho thẻ hồ sơ của CHÍNH MÌNH ở bảng tin: số liệu + bài viết gốc mới nhất (kể cả bài riêng tư — thẻ chỉ chủ thấy)."""
    from app.models import Follow, Location, Photo, Post
    from app.timeutil import relative_label
    latest = (Post.query.filter_by(user_id=user.id, original_post_id=None)
              .order_by(Post.created_at.desc(), Post.id.desc()).first())
    last = None
    if latest is not None:
        title, desc = _title_and_desc(latest.caption)
        loc = db.session.get(Location, latest.location_id) if latest.location_id else None
        photo = (Photo.query.filter_by(post_id=latest.id).filter(Photo.media_type != "video")
                 .order_by(Photo.id.asc()).first())
        if not title:
            title = "Bài viết có ảnh/video" if Photo.query.filter_by(post_id=latest.id).first() else "Bài viết"
        if not desc and loc:
            desc = loc.name
        last = {
            "id": latest.id, "title": title, "desc": desc,
            "thumb": (photo.file_path or "").replace("static/", "", 1) if photo else None,
            "when": relative_label(latest.created_at) if latest.created_at else "",
            "private": latest.visibility == "private",
        }
    return {
        "posts": Post.query.filter_by(user_id=user.id).count(),
        "likers": liker_count(user.id),
        "following": Follow.query.filter_by(follower_id=user.id).count(),
        "followers": Follow.query.filter_by(followed_id=user.id).count(),
        "latest": last,
    }
