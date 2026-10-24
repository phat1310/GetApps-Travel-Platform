"""Thông báo (chuông) — một chỗ duy nhất tạo thông báo để mọi nơi dùng chung luật.

Luật chung:
  * Không tự thông báo cho chính mình (tự like / tự bình luận bài của mình).
  * Không tạo trùng: nếu cùng người, cùng loại, cùng đối tượng mà thông báo cũ CHƯA ĐỌC thì bỏ qua
    (chống spam bấm tim / bỏ tim liên tục làm đầy chuông của người khác).
  * Hàm chỉ db.session.add — nơi gọi tự commit chung transaction với hành động chính.
"""
from app.extensions import db
from app.models.notification import Notification

# "share" chỉ còn để đọc dữ liệu cũ: chia sẻ bằng cách khác (copy link, tải về) KHÔNG còn báo cho chủ bài.
# Chỉ "repost" (đăng lại) mới báo, và trỏ tới bài đăng lại của người đó.
# "post_removed" / "itinerary_removed": admin xóa bài/lịch trình do nghi ngờ vi phạm.
# "post_locked" / "itinerary_locked": admin KHÓA (ẩn, không xóa) bài/lịch trình do nghi ngờ vi phạm.
# LUÔN tạo với post_id=None, itinerary_id=None (đối tượng sắp/đã bị xóa, hoặc đang bị khóa nên
# không được trỏ tới nó) để tránh bị cascade "all, delete-orphan" xóa luôn thông báo theo
# (xem Notification.post/itinerary) và để thông báo vẫn còn dù bài đã bị ẩn.
KINDS = (
    "like", "comment", "repost", "follow", "mention",
    "post_removed", "itinerary_removed", "post_locked", "itinerary_locked",
)


def notify(user_id, actor_id, kind, post_id=None, itinerary_id=None):
    if kind not in KINDS or not user_id or user_id == actor_id:
        return None
    dup = Notification.query.filter_by(
        user_id=user_id, actor_id=actor_id, notification_type=kind,
        post_id=post_id, itinerary_id=itinerary_id, is_read=False,
    ).first()
    if dup:
        return None
    n = Notification(user_id=user_id, actor_id=actor_id, notification_type=kind,
                     post_id=post_id, itinerary_id=itinerary_id)
    db.session.add(n)
    return n


_MODERATION_KINDS = ("post_removed", "itinerary_removed", "post_locked", "itinerary_locked")


def notify_moderation(user_id, actor_id, kind):
    """Thông báo hành động kiểm duyệt của admin (xóa/khóa bài hoặc lịch trình nghi vi phạm)
    — LUÔN tạo mới, không dedup như notify() thường, vì mỗi lần xóa/khóa là 1 sự việc thật
    riêng biệt (post_id để trống nên không thể phân biệt bằng post_id/itinerary_id như các
    loại thông báo khác)."""
    if kind not in _MODERATION_KINDS or not user_id:
        return None
    n = Notification(user_id=user_id, actor_id=actor_id, notification_type=kind,
                      post_id=None, itinerary_id=None)
    db.session.add(n)
    return n


def unread_count(user_id):
    return Notification.query.filter(
        Notification.user_id == user_id, Notification.is_read.is_(False),
        Notification.notification_type != "share",           # thông báo "chia sẻ" kiểu cũ không còn hiển thị -> không đếm
    ).count()
