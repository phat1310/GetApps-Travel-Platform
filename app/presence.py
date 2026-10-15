"""PRESENCE — trạng thái Online/Offline hiển thị trên mọi avatar.

Dấu hiệu online = users.last_seen còn mới (cập nhật định kỳ qua /chat/api/poll từ mọi trang).
Quyền riêng tư: user tắt "Hiện trạng thái hoạt động" (show_activity = False) => ai cũng thấy
trạng thái 'hidden' (chỉ avatar, không chấm, không chữ Online/Offline). Đây là hai chiều như Facebook:
người tắt cũng không thấy trạng thái của người khác.
"""
from datetime import datetime, timedelta

ONLINE_WINDOW_SECONDS = 60


def raw_online(user):
    if not user or not user.last_seen:
        return False
    return (datetime.utcnow() - user.last_seen) <= timedelta(seconds=ONLINE_WINDOW_SECONDS)


def presence_state(user, viewer=None):
    """'on' | 'off' | 'hidden'. viewer=None => chỉ xét cài đặt của chính user đó."""
    if user is None:
        return "hidden"
    if getattr(user, "show_activity", True) is False:
        return "hidden"
    if viewer is not None and getattr(viewer, "is_authenticated", False) and getattr(viewer, "show_activity", True) is False \
            and viewer.id != user.id:
        return "hidden"
    return "on" if raw_online(user) else "off"


def init_presence(app):
    """Đăng ký hàm dùng trong Jinja: {{ presence_state(user, current_user) }}."""
    app.jinja_env.globals["presence_state"] = presence_state
