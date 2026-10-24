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
# LUÔN tạo với post_id=None, itinerary_id=None (đối tượng sắp/đã bị xóa) để tránh bị
# cascade "all, delete-orphan" xóa luôn thông báo theo (xem Notification.post/itinerary).
KINDS = ("like", "comment", "repost", "follow", "mention", "post_removed", "itinerary_removed")


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


def notify_removal(user_id, actor_id, kind):
    """Thông báo admin đã xóa bài/lịch trình (nghi ngờ vi phạm) — LUÔN tạo mới, không
    dedup như notify() thường, vì mỗi lần xóa là 1 sự việc thật riêng biệt (post_id để
    trống nên không thể phân biệt bằng post_id/itinerary_id như các loại thông báo khác)."""
    if kind not in ("post_removed", "itinerary_removed") or not user_id:
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
