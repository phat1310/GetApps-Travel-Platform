"""Giờ đăng bài / lịch trình — lưu UTC trong database, hiển thị giờ Việt Nam (UTC+7).

Quy tắc (dùng chung bài đăng + lịch trình, cả phía server lẫn JS trong base.html):
  - dưới 1 phút            -> "Vừa xong"
  - 1 – 59 phút            -> "5 phút trước"
  - 1 – 24 giờ             -> "3 giờ trước"   (tối đa 24 giờ trước)
  - từ 24 giờ 01 phút      -> "14/10/2026"
Kèm giờ đăng theo UTC+7: "5 phút trước · 17:25 UTC+7".
Nếu đã chỉnh sửa: "Đã cập nhật 3 phút trước · 17:28 UTC+7" (tính theo thời điểm cập nhật).
"""
from datetime import datetime, timedelta

from markupsafe import Markup, escape

VN_OFFSET = timedelta(hours=7)


def _utcnow():
    return datetime.utcnow()


def to_vn(dt):
    """datetime naive UTC -> datetime naive giờ VN."""
    return dt + VN_OFFSET


def relative_label(dt, now=None):
    """'Vừa xong' / 'x phút trước' / 'x giờ trước' / 'dd/mm/yyyy'."""
    now = now or _utcnow()
    secs = (now - dt).total_seconds()
    if secs < 60:                       # kể cả giờ máy lệch nhẹ (secs < 0)
        return "Vừa xong"
    if secs < 3600:
        return f"{int(secs // 60)} phút trước"
    if secs <= 24 * 3600:
        return f"{int(secs // 3600)} giờ trước"
    return to_vn(dt).strftime("%d/%m/%Y")


def clock_label(dt):
    return to_vn(dt).strftime("%H:%M") + " UTC+7"


def full_label(dt, now=None, prefix=""):
    """'<prefix>5 phút trước · 17:25 UTC+7'."""
    return f"{prefix}{relative_label(dt, now)} · {clock_label(dt)}"


def time_tag(created_at, edited_at=None, prefix="", css="ges-time"):
    """<span> có data-ts để JS tự cập nhật mỗi phút. Đã chỉnh sửa -> 'Đã cập nhật ...' theo giờ cập nhật."""
    if not created_at:
        return Markup("")
    if edited_at and edited_at > created_at:
        dt, pre = edited_at, "Đã cập nhật "
    else:
        dt, pre = created_at, prefix
    return Markup('<span class="{}" data-ts="{}" data-prefix="{}">{}</span>').format(
        css, dt.strftime("%Y-%m-%dT%H:%M:%S") + "Z", pre, full_label(dt, prefix=pre))


def edited_clock(dt, now=None):
    """'17:28 UTC+7' (cùng ngày VN) hoặc '17:28 14/10/2026 UTC+7' (ngày khác)."""
    now = now or _utcnow()
    v = to_vn(dt)
    if v.date() == to_vn(now).date():
        return v.strftime("%H:%M") + " UTC+7"
    return v.strftime("%H:%M %d/%m/%Y") + " UTC+7"
