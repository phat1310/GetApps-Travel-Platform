"""Gắn thẻ người dùng trong bình luận: gõ @username HOẶC @Tên hiển thị (có dấu, có khoảng trắng đều được)
-> hiện tên người, bấm vào dẫn tới hồ sơ, người được gắn nhận thông báo ở chuông.

Thiết kế an toàn:
  * Nội dung bình luận vẫn lưu CHỮ THUẦN "@..." (không lưu HTML). Tên hiển thị được dựng lúc hiển thị
    => người dùng đổi biệt danh thì mọi bình luận cũ tự đổi theo.
  * SERVER tự quét lại trong nội dung rồi mới tạo thông báo; không tin danh sách người được tag do trình duyệt gửi.
  * Khớp theo username / biệt danh / họ tên đầy đủ (không phân biệt hoa/thường), ƯU TIÊN CHUỖI DÀI NHẤT trước
    ("Nguyễn Văn Mười" phải thắng "Nguyễn" dù cả 2 đều có thể là tên 1 ai đó).
  * Hiển thị bằng markupsafe: phần chữ thường luôn được escape, chỉ thẻ <a> do server dựng mới là HTML.
  * Chỉ quét 5000 ký tự đầu, tối đa 80 ký tự cho mỗi tên sau '@', tối đa 5 người mỗi bình luận.
"""
import re
import unicodedata

from markupsafe import Markup, escape
from flask import url_for

from app.extensions import db

MAX_MENTIONS = 5
SCAN_LIMIT = 5000
MAX_NAME_CHARS = 80
# '@' không đứng sau chữ/ký tự username (tránh bắt email a@b.com)
_AT_RE = re.compile(r"(?<![\w@.\-])@", re.UNICODE)


def display_name(user):
    return user.nickname or user.full_name or user.username


def _mention_candidates():
    """-> list[(tên_chuẩn_hoá_thường, độ_dài, user_id)] của TẤT CẢ username/biệt danh/họ tên trên hệ thống,
    sắp xếp DÀI NHẤT trước để so khớp "tham lam" đúng kiểu (vd "Nguyễn Văn Mười" thắng "Nguyễn Văn")."""
    from app.models import User
    rows = User.query.with_entities(User.id, User.username, User.nickname, User.full_name).all()
    out = []
    for uid, uname, nick, full in rows:
        for cand in (uname, nick, full):
            if not cand:
                continue
            norm = re.sub(r"\s+", " ", cand.strip())
            if len(norm) >= 2:
                out.append((norm.lower(), len(norm), uid))
    out.sort(key=lambda t: -t[1])
    return out


def find_mentions(text):
    """-> list[(start, end, User)] theo thứ tự xuất hiện (start là vị trí '@', end là sau ký tự cuối của tên).
    Khớp cả username thuần ("@phucsikai") lẫn tên hiển thị có dấu/khoảng trắng ("@Nguyễn Văn Mười")."""
    from app.models import User
    text = (text or "")[:SCAN_LIMIT]
    if "@" not in text:
        return []
    at_ends = [m.end() for m in _AT_RE.finditer(text)]   # vị trí ngay SAU dấu '@'
    if not at_ends:
        return []
    candidates = _mention_candidates()
    if not candidates:
        return []

    found = []
    for at_end in at_ends:
        rest_lower = text[at_end:at_end + MAX_NAME_CHARS].lower()
        for norm_lower, length, uid in candidates:
            if not rest_lower.startswith(norm_lower):
                continue
            # ranh giới: ký tự ngay sau tên không được là chữ/số (tránh "@An" ăn lẹm vào "Anh")
            nxt = rest_lower[length:length + 1]
            if nxt and (nxt.isalnum() or nxt in "._-"):
                continue
            found.append((at_end - 1, at_end + length, uid))
            break

    if not found:
        return []
    id_map = {u.id: u for u in User.query.filter(User.id.in_({uid for *_r, uid in found})).all()}
    return [(s, e, id_map[uid]) for s, e, uid in found if uid in id_map]


def strip_leading_self_mention(content, reply_to_user):
    """Nếu mention ĐẦU TIÊN trong nội dung (ngay vị trí 0) là tag tới ĐÚNG người đang được trả lời
    thì bỏ khi hiển thị (chỉ ảnh hưởng hiển thị, KHÔNG đổi dữ liệu đã lưu trong DB) — tránh lặp vì
    giao diện đã tự hiện thẻ '@người' phía trước nội dung rồi (người dùng có thói quen tự gõ thêm
    @tên khi trả lời sẽ ra "@@ten" nếu không lọc). `reply_to_user` là đối tượng User, không phải chuỗi."""
    if not content or not reply_to_user:
        return content
    ms = find_mentions(content)
    if ms and ms[0][0] == 0 and ms[0][2].id == reply_to_user.id:
        return content[ms[0][1]:].lstrip()
    return content


def mentioned_users(text, limit=MAX_MENTIONS):
    """Danh sách User duy nhất được @ trong text (tối đa `limit`)."""
    seen, out = set(), []
    for _s, _e, u in find_mentions(text):
        if u.id not in seen:
            seen.add(u.id)
            out.append(u)
            if len(out) >= limit:
                break
    return out


def render_mentions(text):
    """Chuỗi bình luận -> Markup an toàn: chữ thường escape, @username thật -> link tới hồ sơ hiện tên người."""
    text = "" if text is None else str(text)
    ms = find_mentions(text)
    if not ms:
        return escape(text)
    out, pos, seen = [], 0, 0
    for start, end, u in ms:
        if start < pos:
            continue
        seen += 1
        out.append(escape(text[pos:start]))
        if seen <= MAX_MENTIONS:
            out.append(Markup('<a href="{}" class="mention" title="@{}">@{}</a>').format(
                url_for("auth.profile", username=u.username), u.username, display_name(u)))
        else:
            out.append(escape(text[start:end]))
        pos = end
    out.append(escape(text[pos:]))
    return Markup("").join(out)


def can_view_for(user_id, post=None, itinerary=None):
    """Người được tag có quyền xem bài / lịch trình đó không? (không có quyền => KHÔNG gửi thông báo, tránh lộ nội dung riêng tư)"""
    if post is not None:
        from app.locations.discovery import can_view_post, following_ids
        if post.visibility != "private" and not post.original_post_id:
            return True
        return can_view_post(post, user_id, following_ids(user_id))
    if itinerary is not None:
        return itinerary.visibility != "private" or itinerary.user_id == user_id
    return False


def notify_mentions(text, actor_id, owner_id, post=None, itinerary=None):
    """Tạo thông báo 'mention' cho người được @ (trừ chính mình, trừ người không xem được).
    Trả về set user_id đã được thông báo — để nơi gọi bỏ thông báo 'comment' trùng cho chủ bài."""
    from app.notifications import notify
    notified = set()
    for u in mentioned_users(text):
        if u.id == actor_id or not can_view_for(u.id, post=post, itinerary=itinerary):
            continue
        notify(u.id, actor_id, "mention",
               post_id=post.id if post is not None else None,
               itinerary_id=itinerary.id if itinerary is not None else None)
        notified.add(u.id)
    return notified


def _norm(s):
    s = unicodedata.normalize("NFD", s or "").replace("đ", "d").replace("Đ", "D")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", "", s).lower()


def suggest(me_id, query, limit=8, extra_ids=()):
    """Gợi ý người để @ — TẤT CẢ tài khoản trên web đều tag được, thứ tự ưu tiên:
         1. người MÌNH ĐANG THEO DÕI  2. người theo dõi mình / vừa bình luận ở bài này  3. mọi người còn lại.
    Trong mỗi nhóm: trùng đúng username > bắt đầu bằng từ khóa > có chứa. q rỗng (vừa gõ '@'): vẫn hiện tất cả theo thứ tự trên.
    Chỉ đọc vài cột nhẹ (không nạp cả hàng User) nên quét hết được bảng người dùng; so khớp bỏ dấu, không phân biệt hoa/thường."""
    from app.models import User, Follow
    q = _norm((query or "").lstrip("@"))[:64]
    following = {r[0] for r in db.session.query(Follow.followed_id).filter(Follow.follower_id == me_id).all()}
    followers = {r[0] for r in db.session.query(Follow.follower_id).filter(Follow.followed_id == me_id).all()}
    warm = followers | set(extra_ids)
    rows = db.session.query(User.id, User.username, User.nickname, User.full_name, User.avatar_url).filter(User.id != me_id).all()
    scored = []
    for uid, uname, nick, full, avatar in rows:
        names = [_norm(uname), _norm(nick), _norm(full)]
        tier = 0 if uid in following else (1 if uid in warm else 2)
        if q:
            if not any(q in n for n in names if n):
                continue
            rank = 0 if names[0] == q else (1 if any(n.startswith(q) for n in names if n) else 2)
        else:
            rank = 0                      # vừa gõ '@': hiện tất cả, người đang theo dõi xếp đầu rồi tới A-Z
        scored.append((tier, rank, (uname or "").lower(), uname, nick, full, avatar))
    scored.sort(key=lambda t: t[:3])
    return [{
        "username": uname,
        "display": nick or full or uname,
        "avatar": avatar or "",
        "following": tier == 0,
    } for tier, _r, _n, uname, nick, full, avatar in scored[:limit]]


def notify_new_mentions(old_text, new_text, actor_id, post=None, itinerary=None):
    """Khi SỬA nội dung: chỉ báo cho người MỚI được tag (đã tag từ trước thì không báo lại)."""
    before = {u.id for u in mentioned_users(old_text)}
    from app.notifications import notify
    done = set()
    for u in mentioned_users(new_text):
        if u.id in before or u.id == actor_id or not can_view_for(u.id, post=post, itinerary=itinerary):
            continue
        notify(u.id, actor_id, "mention", post_id=post.id if post is not None else None,
               itinerary_id=itinerary.id if itinerary is not None else None)
        done.add(u.id)
    return done
