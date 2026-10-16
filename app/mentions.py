"""Gắn thẻ người dùng trong bình luận: gõ @username -> hiện tên người, người được gắn nhận thông báo ở chuông.

Thiết kế an toàn:
  * Nội dung bình luận vẫn lưu CHỮ THUẦN "@username" (không lưu HTML). Tên hiển thị được dựng lúc hiển thị
    => người dùng đổi biệt danh thì mọi bình luận cũ tự đổi theo.
  * SERVER tự quét @username trong nội dung rồi mới tạo thông báo; không tin danh sách người được tag do trình duyệt gửi.
  * Khớp theo username đầy đủ (không phân biệt hoa/thường), ưu tiên chuỗi DÀI nhất ("@test_refactor" không bị hiểu thành "@test").
  * Hiển thị bằng markupsafe: phần chữ thường luôn được escape, chỉ thẻ <a> do server dựng mới là HTML.
  * Chỉ quét 5000 ký tự đầu, tối đa 5 người mỗi bình luận.
"""
import re
import unicodedata

from markupsafe import Markup, escape
from flask import url_for
from sqlalchemy import func

from app.extensions import db

MAX_MENTIONS = 5
SCAN_LIMIT = 5000
# '@' không đứng sau chữ/ký tự username (tránh bắt email a@b.com), username 3-64 ký tự
_MENTION_RE = re.compile(r"(?<![\w@.\-])@([\w.\-]{3,64})", re.UNICODE)


def display_name(user):
    return user.nickname or user.full_name or user.username


def _candidates(token):
    """Các username có thể từ một cụm sau '@', dài nhất trước: 'test.' -> 'test'; 'a.b' -> 'a.b', 'a'."""
    t = token.rstrip(".-")
    out = []
    if len(t) >= 3:
        out.append(t)
    for i in range(len(t) - 1, 2, -1):
        if t[i] in ".-":
            out.append(t[:i])
    return out


def find_mentions(text):
    """-> list[(start, end, User)] theo thứ tự xuất hiện (start là vị trí '@', end là sau ký tự cuối của username)."""
    from app.models import User
    text = (text or "")[:SCAN_LIMIT]
    if "@" not in text:
        return []
    found = []
    wanted = set()
    for m in _MENTION_RE.finditer(text):
        cands = _candidates(m.group(1))
        if cands:
            found.append((m.start(), cands))
            wanted.update(c.lower() for c in cands)
    if not wanted:
        return []
    users = {u.username.lower(): u for u in User.query.filter(func.lower(User.username).in_(wanted)).all()}
    out = []
    for start, cands in found:
        for c in cands:
            u = users.get(c.lower())
            if u:
                out.append((start, start + 1 + len(c), u))
                break
    return out


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
    """Gợi ý người để @: người mình theo dõi / theo dõi mình / vừa bình luận ở bài này lên trước, rồi tới mọi tài khoản khớp tên."""
    from app.models import User, Follow
    q = _norm((query or "").lstrip("@"))[:64]
    following = {f.followed_id for f in Follow.query.filter_by(follower_id=me_id).all()}
    followers = {f.follower_id for f in Follow.query.filter_by(followed_id=me_id).all()}
    warm = following | followers | set(extra_ids)
    users = User.query.filter(User.id != me_id).order_by(User.id.desc()).limit(1000).all()
    scored = []
    for u in users:
        names = [_norm(u.username), _norm(u.nickname), _norm(u.full_name)]
        if q:
            if not any(q in n for n in names if n):
                continue
            rank = 0 if names[0] == q else (1 if any(n.startswith(q) for n in names if n) else 2)
        else:
            if u.id not in warm:
                continue
            rank = 0
        scored.append((rank, 0 if u.id in warm else 1, u.username.lower(), u))
    scored.sort(key=lambda t: t[:3])
    return [{
        "username": u.username,
        "display": display_name(u),
        "avatar": u.avatar_url or "",
    } for _r, _w, _n, u in scored[:limit]]
