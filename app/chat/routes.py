"""Routes CHAT — API JSON cho cửa sổ chat kiểu Messenger (polling) + tải tệp có kiểm tra quyền.

Quy tắc nhắn tin:
- Hai người ĐÃ follow nhau: nhắn tự do (hội thoại status="mutual").
- NGƯỜI LẠ: tìm theo tên (gợi ý gần giống, bỏ dấu, không phân biệt hoa thường/khoảng trắng) rồi nhắn.
  Tin đầu vào mục "Tin nhắn chờ" của người nhận (status="pending"): người gửi chỉ gửi được 1 tin chữ,
  chưa gửi được tệp, cho tới khi người nhận TRẢ LỜI (ngầm hiểu là đồng ý) -> status chuyển "accepted"
  và 2 bên nhắn tự do. Không có bước "chấp nhận/từ chối" riêng: người nhận không rep thì thôi, không
  bị chặn gì, vẫn tìm/nhắn lại người kia bình thường bất cứ lúc nào.
- Tài khoản riêng tư (is_private): người lạ chưa follow thì không nhắn được.
- Mọi route đều yêu cầu đăng nhập và kiểm tra người dùng có thuộc hội thoại hay không (chống IDOR).
- Tệp đính kèm lưu ở instance/chat_uploads/ với tên ngẫu nhiên, KHÔNG nằm trong static/.
  Ảnh/video được mở trực tiếp, mọi loại khác luôn bị ép tải về (tránh XSS qua .html/.svg).
- Tìm người lạ: tối thiểu 2 ký tự, tối đa 8 kết quả, giới hạn số lượt tìm mỗi phút (chống dò danh sách).
- Giai đoạn này chưa giới hạn dung lượng / loại tệp (sẽ bổ sung sau).
"""
import os
import re
import time
import unicodedata
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta

from flask import abort, current_app, jsonify, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from app.presence import presence_state
from app.chat import chat_bp
from app.extensions import db
from app.models import Follow, User
from app.models.chat import Conversation, Message, MessageReaction

ONLINE_WINDOW_SECONDS = 60       # last_seen trong vòng 60s => Online
LAST_SEEN_THROTTLE_SECONDS = 20  # chỉ ghi DB last_seen tối đa 1 lần / 20s
MAX_BODY_LENGTH = 4000
PAGE_SIZE = 30

SEARCH_MIN_CHARS = 2             # tìm người lạ: gõ tối thiểu 2 ký tự (sau khi bỏ khoảng trắng)
SEARCH_LIMIT = 8                 # tối đa 8 kết quả mỗi lần
SEARCH_RATE_MAX = 40             # tối đa 40 lượt tìm / 60 giây / người dùng
SEARCH_RATE_WINDOW = 60
SEARCH_SCAN_LIMIT = 20000        # số tài khoản tối đa quét khi tìm (đủ cho quy mô đồ án)
_search_hits = defaultdict(deque)

IMAGE_TYPES = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
    "gif": "image/gif", "webp": "image/webp", "bmp": "image/bmp",
}
VIDEO_TYPES = {
    "mp4": "video/mp4", "m4v": "video/mp4", "webm": "video/webm",
    "mov": "video/quicktime", "ogv": "video/ogg",
}


# =========================================================
# HÀM PHỤ
# =========================================================

def _upload_dir():
    path = os.path.join(current_app.instance_path, "chat_uploads")
    os.makedirs(path, exist_ok=True)
    return path


def _touch_last_seen():
    """Cập nhật last_seen của người đang đăng nhập (có throttle để đỡ ghi DB)."""
    now = datetime.utcnow()
    last = current_user.last_seen
    if last is None or (now - last).total_seconds() >= LAST_SEEN_THROTTLE_SECONDS:
        current_user.last_seen = now
        db.session.commit()


def _presence(user):
    """'on' | 'off' | 'hidden' (người đó — hoặc chính mình — đã tắt hiển thị trạng thái hoạt động)."""
    return presence_state(user, current_user)


def _is_online(user):
    return _presence(user) == "on"


def _avatar(user):
    if user.avatar_url:
        return user.avatar_url
    name = (user.nickname or user.full_name or user.username or "U")
    return f"https://ui-avatars.com/api/?name={name}&background=169fe3&color=fff"


def _user_dict(user):
    return {
        "id": user.id,
        "username": user.username,
        "display": user.nickname or user.full_name or user.username,
        "avatar": _avatar(user),
        "online": _is_online(user),
        "presence": _presence(user),
        "profile_url": url_for("auth.profile", username=user.username),
    }


def _norm(text):
    """Chuẩn hóa để so tên: bỏ dấu tiếng Việt, đ->d, bỏ MỌI khoảng trắng, không phân biệt hoa thường."""
    s = unicodedata.normalize("NFD", text or "").replace("đ", "d").replace("Đ", "D")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", "", s).lower()


def _rate_limited(user_id):
    now = time.monotonic()
    hits = _search_hits[user_id]
    while hits and now - hits[0] > SEARCH_RATE_WINDOW:
        hits.popleft()
    if len(hits) >= SEARCH_RATE_MAX:
        return True
    hits.append(now)
    return False


def _rel_sets():
    """(những người mình follow, những người follow mình) — nạp 1 lần cho cả request."""
    me = current_user.id
    following = {f.followed_id for f in Follow.query.filter_by(follower_id=me).all()}
    followers = {f.follower_id for f in Follow.query.filter_by(followed_id=me).all()}
    return following, followers


def _are_mutual(user_id, other_id):
    a = Follow.query.filter_by(follower_id=user_id, followed_id=other_id).first()
    b = Follow.query.filter_by(follower_id=other_id, followed_id=user_id).first()
    return bool(a and b)


def _pair(user_id, other_id):
    return (user_id, other_id) if user_id < other_id else (other_id, user_id)


def _get_conv_or_404(conv_id):
    conv = db.session.get(Conversation, conv_id)
    if not conv or not conv.has_member(current_user.id):
        abort(404)
    return conv


def _iso(dt):
    return dt.isoformat() + "Z" if dt else None


def _permissions(conv, other_id, sets=None):
    """Quyền của NGƯỜI ĐANG ĐĂNG NHẬP trong hội thoại này."""
    me = current_user.id
    following, followers = sets if sets else _rel_sets()
    mutual = other_id in following and other_id in followers
    st = conv.status or "mutual"
    is_request = (st == "pending" and conv.initiated_by != me and not mutual)
    perms = {"can_send": False, "can_attach": False, "note": "", "is_request": is_request,
             "awaiting": False, "status": st}
    if mutual or st == "accepted":
        perms.update(can_send=True, can_attach=True)
    elif st == "pending":
        if conv.initiated_by == me:
            perms["awaiting"] = True
            already = Message.query.filter_by(conversation_id=conv.id, sender_id=me).count()
            if already == 0:
                perms.update(can_send=True, note="Tin nhắn đầu tiên sẽ vào mục Tin nhắn chờ của họ. Chưa gửi được tệp.")
            else:
                perms["note"] = "Đang chờ người kia chấp nhận. Bạn chỉ gửi được 1 tin trước khi được chấp nhận."
        else:
            perms.update(can_send=True, can_attach=True)   # người nhận trả lời = chấp nhận
    else:  # "mutual" nhưng không còn follow nhau
        perms["note"] = "Hai bạn cần follow nhau để nhắn tin."
    return perms


def _hearts_for(message_ids):
    """{message_id: {"count": n, "mine": bool}} cho các tin có tim."""
    if not message_ids:
        return {}
    rows = (MessageReaction.query
            .filter(MessageReaction.message_id.in_(message_ids)).all())
    out = {}
    for r in rows:
        h = out.setdefault(r.message_id, {"count": 0, "mine": False})
        h["count"] += 1
        if r.user_id == current_user.id:
            h["mine"] = True
    return out


def _reply_preview(msg):
    """Trích dẫn gọn tin nhắn gốc mà `msg` đang trả lời (nếu có)."""
    if not msg.reply_to_id:
        return None
    orig = db.session.get(Message, msg.reply_to_id)
    if not orig:
        return None
    if orig.is_deleted:
        text = "Tin nhắn đã được thu hồi"
    elif orig.body:
        text = orig.body
    elif orig.file_path:
        text = {"image": "[Ảnh]", "video": "[Video]"}.get(orig.file_kind) or f"[Tệp] {orig.file_name}"
    else:
        text = ""
    sender = db.session.get(User, orig.sender_id)
    return {
        "id": orig.id,
        "text": text[:140],
        "sender_name": (sender.nickname or sender.username) if sender else "",
        "mine": orig.sender_id == current_user.id,
    }


def _message_dict(msg, hearts=None):
    deleted = bool(msg.is_deleted)
    data = {
        "id": msg.id,
        "mine": msg.sender_id == current_user.id,
        "body": "Tin nhắn đã được thu hồi" if deleted else (msg.body or ""),
        "read": bool(msg.is_read),
        "at": _iso(msg.created_at),
        "file": None,
        "deleted": deleted,
        "hearts": (hearts or {}).get(msg.id, {"count": 0, "mine": False}),
        "reply_to": None if deleted else _reply_preview(msg),
    }
    if msg.file_path and not deleted:
        data["file"] = {
            "url": url_for("chat.download_file", message_id=msg.id),
            "name": msg.file_name or "tệp",
            "size": msg.file_size or 0,
            "kind": msg.file_kind or "file",
        }
    return data


def _serialize_messages(msgs):
    hearts = _hearts_for([m.id for m in msgs])
    return [_message_dict(m, hearts) for m in msgs]


def _last_preview(msg):
    if not msg:
        return None
    if msg.is_deleted:
        text = "Tin nhắn đã được thu hồi"
    elif msg.body:
        text = msg.body
    elif msg.file_path:
        text = {"image": "[Ảnh]", "video": "[Video]"}.get(msg.file_kind) or f"[Tệp] {msg.file_name}"
    else:
        text = ""
    return {"text": text[:120], "mine": msg.sender_id == current_user.id, "at": _iso(msg.created_at)}


def _unread_by_conv(conv_ids):
    if not conv_ids:
        return {}
    rows = (
        db.session.query(Message.conversation_id, func.count(Message.id))
        .filter(
            Message.conversation_id.in_(conv_ids),
            Message.sender_id != current_user.id,
            Message.is_read.is_(False),
        )
        .group_by(Message.conversation_id)
        .all()
    )
    return {cid: n for cid, n in rows}


def _last_ids(conv_ids):
    if not conv_ids:
        return {}
    return dict(
        db.session.query(Message.conversation_id, func.max(Message.id))
        .filter(Message.conversation_id.in_(conv_ids))
        .group_by(Message.conversation_id).all()
    )


def _visible_conversations():
    """Hội thoại của mình, trừ yêu cầu chưa có tin nào (người lạ mới bấm mở, chưa thật sự nhắn gì)."""
    me = current_user.id
    convs = (
        Conversation.query
        .filter(or_(Conversation.user_a_id == me, Conversation.user_b_id == me))
        .order_by(Conversation.last_message_at.desc())
        .all()
    )
    last_ids = _last_ids([c.id for c in convs])
    keep = []
    for c in convs:
        incoming = c.initiated_by is not None and c.initiated_by != me
        if incoming and c.status == "pending" and not last_ids.get(c.id):
            continue
        keep.append(c)
    return keep, last_ids


def _conversation_dict(conv, other, unread_map, sets=None):
    last = Message.query.filter_by(conversation_id=conv.id).order_by(Message.id.desc()).first()
    data = {
        "id": conv.id,
        "user": _user_dict(other),
        "last": _last_preview(last),
        "last_id": last.id if last else 0,
        "unread": unread_map.get(conv.id, 0),
    }
    data.update(_permissions(conv, other.id, sets))
    return data


def _clean_filename(name):
    name = (name or "tep").replace("\\", "/").split("/")[-1]
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip() or "tep"
    if len(name) > 150:
        base, dot, ext = name.rpartition(".")
        name = (base[:140] + dot + ext[:8]) if dot else name[:150]
    return name


def _safe_ext(name):
    ext = name.rpartition(".")[2].lower() if "." in name else ""
    return ext if re.fullmatch(r"[a-z0-9]{1,8}", ext) else ""


# =========================================================
# API HỘI THOẠI
# =========================================================

@chat_bp.route("/api/conversations", methods=["GET"])
@login_required
def list_conversations():
    _touch_last_seen()
    convs, _ = _visible_conversations()
    unread_map = _unread_by_conv([c.id for c in convs])
    sets = _rel_sets()
    others = {u.id: u for u in User.query.filter(
        User.id.in_([c.other_user_id(current_user.id) for c in convs] or [0])).all()}
    items = []
    for c in convs:
        other = others.get(c.other_user_id(current_user.id))
        if other:
            items.append(_conversation_dict(c, other, unread_map, sets))
    return jsonify({"conversations": items})


@chat_bp.route("/api/open", methods=["POST"])
@login_required
def open_conversation():
    """Mở (hoặc tạo) hội thoại với 1 người. Người lạ => tạo yêu cầu chờ (trừ tài khoản riêng tư chưa follow)."""
    data = request.get_json(silent=True) or {}
    try:
        other_id = int(data.get("user_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Thiếu người nhận"}), 400
    if other_id == current_user.id:
        return jsonify({"error": "Không thể tự nhắn tin cho chính mình"}), 400
    other = db.session.get(User, other_id)
    if not other:
        return jsonify({"error": "Người dùng không tồn tại"}), 404

    a, b = _pair(current_user.id, other_id)
    conv = Conversation.query.filter_by(user_a_id=a, user_b_id=b).first()
    sets = _rel_sets()
    if not conv:
        following, followers = sets
        mutual = other_id in following and other_id in followers
        if mutual:
            conv = Conversation(user_a_id=a, user_b_id=b, status="mutual")
        else:
            if other.is_private and other_id not in following:
                return jsonify({"error": "Tài khoản này ở chế độ riêng tư, bạn cần theo dõi họ trước khi nhắn tin"}), 403
            conv = Conversation(user_a_id=a, user_b_id=b, status="pending", initiated_by=current_user.id)
        db.session.add(conv)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            conv = Conversation.query.filter_by(user_a_id=a, user_b_id=b).first()
            if not conv:
                return jsonify({"error": "Không tạo được hội thoại"}), 500
    unread_map = _unread_by_conv([conv.id])
    return jsonify({"conversation": _conversation_dict(conv, other, unread_map, sets)})


@chat_bp.route("/api/conversations/<int:conv_id>/messages", methods=["GET"])
@login_required
def get_messages(conv_id):
    conv = _get_conv_or_404(conv_id)
    after_id = request.args.get("after_id", type=int)
    before_id = request.args.get("before_id", type=int)
    limit = min(max(request.args.get("limit", PAGE_SIZE, type=int), 1), 100)

    # Query trực tiếp (relationship dynamic có thể đè order_by)
    q = Message.query.filter_by(conversation_id=conv.id)
    if after_id:
        msgs = q.filter(Message.id > after_id).order_by(Message.id.asc()).limit(200).all()
        has_more = False
    else:
        if before_id:
            q = q.filter(Message.id < before_id)
        rows = q.order_by(Message.id.desc()).limit(limit + 1).all()
        has_more = len(rows) > limit
        msgs = list(reversed(rows[:limit]))

    other = db.session.get(User, conv.other_user_id(current_user.id))
    payload = {
        "messages": _serialize_messages(msgs),
        "has_more": has_more,
        "online": _is_online(other),
        "presence": _presence(other),
    }
    payload.update(_permissions(conv, other.id) if other else {"can_send": False, "can_attach": False})
    return jsonify(payload)


@chat_bp.route("/api/conversations/<int:conv_id>/messages", methods=["POST"])
@login_required
def send_message(conv_id):
    conv = _get_conv_or_404(conv_id)
    other_id = conv.other_user_id(current_user.id)
    perms = _permissions(conv, other_id)
    if not perms["can_send"]:
        return jsonify({"error": perms["note"] or "Bạn không thể nhắn tin trong cuộc trò chuyện này"}), 403

    body = (request.form.get("body") or "").strip()
    if len(body) > MAX_BODY_LENGTH:
        return jsonify({"error": f"Tin nhắn tối đa {MAX_BODY_LENGTH} ký tự"}), 400
    upload = request.files.get("file")
    has_file = bool(upload and upload.filename)
    if has_file and not perms["can_attach"]:
        return jsonify({"error": "Chưa gửi được tệp cho đến khi người kia chấp nhận tin nhắn của bạn"}), 403
    if not body and not has_file:
        return jsonify({"error": "Tin nhắn trống"}), 400

    reply_to_id = request.form.get("reply_to_id", type=int)
    if reply_to_id:
        orig = db.session.get(Message, reply_to_id)
        if not orig or orig.conversation_id != conv.id:
            reply_to_id = None  # chỉ cho reply tin nhắn thật sự nằm trong đúng hội thoại này

    msg = Message(conversation_id=conv.id, sender_id=current_user.id, body=body or None, reply_to_id=reply_to_id)

    if has_file:
        original = _clean_filename(upload.filename)
        ext = _safe_ext(original)
        stored = uuid.uuid4().hex + (f".{ext}" if ext else "")
        path = os.path.join(_upload_dir(), stored)
        upload.save(path)
        msg.file_path = stored
        msg.file_name = original
        msg.file_size = os.path.getsize(path)
        msg.file_kind = "image" if ext in IMAGE_TYPES else ("video" if ext in VIDEO_TYPES else "file")

    if perms["is_request"]:
        conv.status = "accepted"   # người nhận trả lời tin nhắn chờ = chấp nhận
    conv.last_message_at = datetime.utcnow()
    db.session.add(msg)
    db.session.commit()
    return jsonify({"message": _message_dict(msg), "permissions": _permissions(conv, other_id)}), 201


@chat_bp.route("/api/conversations/<int:conv_id>/read", methods=["POST"])
@login_required
def mark_read(conv_id):
    conv = _get_conv_or_404(conv_id)
    (Message.query
        .filter(Message.conversation_id == conv.id,
                Message.sender_id != current_user.id,
                Message.is_read.is_(False))
        .update({"is_read": True}, synchronize_session=False))
    db.session.commit()
    return jsonify({"ok": True})


# =========================================================
# THẢ TIM
# =========================================================

@chat_bp.route("/api/messages/<int:message_id>/heart", methods=["POST"])
@login_required
def toggle_heart(message_id):
    msg = db.session.get(Message, message_id)
    if not msg:
        abort(404)
    conv = db.session.get(Conversation, msg.conversation_id)
    if not conv or not conv.has_member(current_user.id):
        abort(404)
    existing = MessageReaction.query.filter_by(message_id=msg.id, user_id=current_user.id).first()
    if existing:
        db.session.delete(existing)
    else:
        db.session.add(MessageReaction(message_id=msg.id, user_id=current_user.id))
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()   # bấm 2 lần cùng lúc: coi như đã thả
    return jsonify({"hearts": _hearts_for([msg.id]).get(msg.id, {"count": 0, "mine": False})})


@chat_bp.route("/api/conversations/<int:conv_id>/hearts", methods=["GET"])
@login_required
def conversation_hearts(conv_id):
    conv = _get_conv_or_404(conv_id)
    ids = [m_id for (m_id,) in db.session.query(Message.id).filter_by(conversation_id=conv.id).all()]
    return jsonify({"hearts": {str(k): v for k, v in _hearts_for(ids).items()}})


# =========================================================
# XÓA (THU HỒI) TIN NHẮN — chỉ người gửi, giữ lại dòng tin nhắn (tombstone), không xóa hẳn khỏi lịch sử
# =========================================================

@chat_bp.route("/api/messages/<int:message_id>", methods=["DELETE"])
@login_required
def delete_message(message_id):
    msg = db.session.get(Message, message_id)
    if not msg:
        abort(404)
    conv = db.session.get(Conversation, msg.conversation_id)
    if not conv or not conv.has_member(current_user.id):
        abort(404)
    if msg.sender_id != current_user.id:
        return jsonify({"error": "Bạn chỉ có thể thu hồi tin nhắn của chính mình"}), 403
    if msg.is_deleted:
        return jsonify({"message": _message_dict(msg)})

    if msg.file_path:
        path = os.path.join(_upload_dir(), msg.file_path)
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
        msg.file_path = None
        msg.file_name = None
        msg.file_kind = None
        msg.file_size = None

    msg.body = None
    msg.is_deleted = True
    db.session.commit()
    return jsonify({"message": _message_dict(msg)})


# =========================================================
# POLLING (số đỏ, tin mới, online, tim)
# =========================================================

@chat_bp.route("/api/poll", methods=["GET"])
@login_required
def poll():
    """Nhẹ, gọi định kỳ từ mọi trang: cập nhật last_seen + trả số người chưa đọc."""
    _touch_last_seen()
    convs, last_ids = _visible_conversations()
    conv_ids = [c.id for c in convs]
    unread_map = _unread_by_conv(conv_ids)
    sets = _rel_sets()
    other_ids = [c.other_user_id(current_user.id) for c in convs]
    others = {u.id: u for u in User.query.filter(User.id.in_(other_ids or [0])).all()}
    # id tin MỚI NHẤT của mình mà người kia đã đọc -> để hiện "Đã xem"
    seen_ids = dict(
        db.session.query(Message.conversation_id, func.max(Message.id))
        .filter(Message.conversation_id.in_(conv_ids or [0]),
                Message.sender_id == current_user.id,
                Message.is_read.is_(True))
        .group_by(Message.conversation_id).all()
    )
    # tổng số tim mỗi hội thoại (đổi => cửa sổ tải lại tim)
    heart_counts = dict(
        db.session.query(Message.conversation_id, func.count(MessageReaction.id))
        .join(MessageReaction, MessageReaction.message_id == Message.id)
        .filter(Message.conversation_id.in_(conv_ids or [0]))
        .group_by(Message.conversation_id).all()
    )
    items = []
    people = 0
    requests = 0
    for c in convs:
        oid = c.other_user_id(current_user.id)
        perms = _permissions(c, oid, sets)
        unread = unread_map.get(c.id, 0)
        if perms["is_request"]:
            requests += 1
        elif unread > 0:
            people += 1   # đếm theo SỐ NGƯỜI, không theo số tin; tin nhắn chờ KHÔNG tính vào số đỏ
        items.append({
            "id": c.id,
            "unread": unread,
            "last_id": last_ids.get(c.id, 0),
            "seen_id": seen_ids.get(c.id, 0),
            "hearts": heart_counts.get(c.id, 0),
            "online": _is_online(others.get(oid)),
            "presence": _presence(others.get(oid)),
            "request": perms["is_request"],
            "can_send": perms["can_send"],
            "can_attach": perms["can_attach"],
            "note": perms["note"],
            "awaiting": perms["awaiting"],
            "status": perms["status"],
        })
    from app.notifications import unread_count
    return jsonify({"unread_people": people, "requests": requests, "conversations": items,
                    "notif_unread": unread_count(current_user.id)})


# =========================================================
# TÌM NGƯỜI ĐỂ NHẮN
# =========================================================

@chat_bp.route("/api/search", methods=["GET"])
@login_required
def search_users():
    """Tìm người để nhắn.
    - Chưa gõ / gõ dưới 2 ký tự: chỉ gợi ý những người ĐÃ follow nhau.
    - Gõ từ 2 ký tự: gợi ý MỌI tài khoản có tên (username / nickname / họ tên) khớp hoặc gần giống,
      kể cả người lạ và người trùng tên. Khớp đúng xếp trước, rồi bắt đầu bằng, rồi chứa.
    """
    me = current_user.id
    q = (request.args.get("q") or "").strip()
    nq = _norm(q)
    following, followers = _rel_sets()
    mutual = (following & followers) - {me}

    if len(nq) < SEARCH_MIN_CHARS:
        if not mutual:
            return jsonify({"users": [], "min_chars": SEARCH_MIN_CHARS})
        query = User.query.filter(User.id.in_(mutual))
        if nq:
            like = f"%{q}%"
            query = query.filter(or_(User.username.ilike(like), User.full_name.ilike(like), User.nickname.ilike(like)))
        users = query.order_by(User.username.asc()).limit(SEARCH_LIMIT).all()
        out = []
        for u in users:
            d = _user_dict(u)
            d.update(relation="friend", followers=0, can_message=True, note="")
            out.append(d)
        return jsonify({"users": out, "min_chars": SEARCH_MIN_CHARS})

    if _rate_limited(me):
        return jsonify({"error": "Bạn tìm kiếm quá nhanh, hãy thử lại sau ít giây"}), 429

    rows = (db.session.query(User.id, User.username, User.nickname, User.full_name)
            .filter(User.id != me).limit(SEARCH_SCAN_LIMIT).all())
    scored = []
    for uid, username, nickname, full_name in rows:
        best = None
        for field in (username, nickname, full_name):
            n = _norm(field)
            if not n:
                continue
            if n == nq:
                sc = 0
            elif n.startswith(nq):
                sc = 1
            elif nq in n:
                sc = 2
            else:
                continue
            best = sc if best is None else min(best, sc)
        if best is not None:
            scored.append((best, 0 if uid in mutual else 1, (username or "").lower(), uid))
    scored.sort()
    top_ids = [uid for _, _, _, uid in scored[:SEARCH_LIMIT]]
    if not top_ids:
        return jsonify({"users": [], "min_chars": SEARCH_MIN_CHARS})

    by_id = {u.id: u for u in User.query.filter(User.id.in_(top_ids)).all()}
    follower_counts = dict(
        db.session.query(Follow.followed_id, func.count(Follow.id))
        .filter(Follow.followed_id.in_(top_ids)).group_by(Follow.followed_id).all()
    )
    out = []
    for uid in top_ids:
        u = by_id.get(uid)
        if not u:
            continue
        d = _user_dict(u)
        is_friend = uid in mutual
        can_message, note = True, ""
        if not is_friend and u.is_private and uid not in following:
            can_message, note = False, "Tài khoản riêng tư"
        d.update(relation="friend" if is_friend else "stranger",
                 followers=follower_counts.get(uid, 0), can_message=can_message, note=note)
        out.append(d)
    return jsonify({"users": out, "min_chars": SEARCH_MIN_CHARS})


# =========================================================
# TẢI TỆP (có kiểm tra quyền)
# =========================================================

@chat_bp.route("/api/presence", methods=["GET"])
@login_required
def presence_batch():
    """Trạng thái Online/Offline cho nhiều người một lúc (trang Bảng tin, Hồ sơ, danh sách follow...)."""
    _touch_last_seen()
    ids = []
    for part in (request.args.get("ids") or "").split(","):
        part = part.strip()
        if part.isdigit():
            ids.append(int(part))
        if len(ids) >= 60:
            break
    users = User.query.filter(User.id.in_(ids or [0])).all()
    return jsonify({"presence": {str(u.id): presence_state(u, current_user) for u in users}})


@chat_bp.route("/file/<int:message_id>", methods=["GET"])
@login_required
def download_file(message_id):
    msg = db.session.get(Message, message_id)
    if not msg or not msg.file_path:
        abort(404)
    conv = db.session.get(Conversation, msg.conversation_id)
    if not conv or not conv.has_member(current_user.id):
        abort(404)  # không tiết lộ là file có tồn tại hay không

    path = os.path.join(_upload_dir(), os.path.basename(msg.file_path))
    if not os.path.isfile(path):
        abort(404)

    ext = _safe_ext(msg.file_path)
    inline_type = IMAGE_TYPES.get(ext) or VIDEO_TYPES.get(ext)
    resp = send_file(
        path,
        mimetype=inline_type or "application/octet-stream",
        as_attachment=inline_type is None,   # chỉ ảnh/video mới mở trực tiếp
        download_name=msg.file_name or "tep",
        conditional=True,
        max_age=0,
    )
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Cache-Control"] = "private, no-store"
    return resp
