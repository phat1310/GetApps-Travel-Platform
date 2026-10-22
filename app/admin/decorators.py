"""
Decorator phân quyền cho khu vực admin.

QUAN TRỌNG (bài học Broken Access Control - OWASP A01:2021):
Việc ẨN nút/menu admin bằng CSS, JS, hay chỉ check ở template (Jinja {% if %})
KHÔNG phải là access control thật. Trình duyệt chỉ là giao diện — kẻ tấn công
có thể gõ thẳng URL (ví dụ /admin/users) mà không cần thấy nút nào cả.
Access control THẬT phải nằm ở phía SERVER, chạy trước khi route xử lý bất
kỳ logic nào — đó chính là việc decorator này làm.

Cờ DEMO_BAC_VULNERABLE (đọc từ config) chỉ dùng để QUAY DEMO kịch bản lỗ hổng
cho báo cáo/live demo: khi bật, decorator giả vờ "quên" check quyền để mô
phỏng đúng lỗi Missing Function Level Access Control. KHÔNG bao giờ để bật
cờ này khi nộp bài/deploy thật — xem README_SECURITY.md phần BAC.
"""
from functools import wraps
from flask import abort, current_app
from flask_login import current_user


def admin_required(f):
    """Chặn truy cập nếu chưa đăng nhập HOẶC is_admin != True. Trả về 403,
    không redirect về trang login (403 đúng ngữ nghĩa HTTP hơn: tài khoản đã
    xác thực nhưng không đủ quyền, khác với 401 = chưa xác thực)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        # ---- Khối demo lỗ hổng: CHỈ bật thủ công qua biến môi trường khi quay demo ----
        if current_app.config.get("DEMO_BAC_VULNERABLE"):
            return f(*args, **kwargs)
        # ---- Access control thật (luôn chạy khi DEMO_BAC_VULNERABLE=False) ----
        if not current_user.is_authenticated:
            abort(403)
        if not getattr(current_user, "is_admin", False):
            _log_denied()
            abort(403)
        if getattr(current_user, "is_banned", False):
            _log_denied()
            abort(403)
        return f(*args, **kwargs)
    return decorated


def _log_denied():
    """Ghi lại mọi lần bị 403 ở khu vực admin vào bảng security_logs — đây chính là
    nguồn dữ liệu ACCESS_DENIED_403 hiển thị ở /admin/security-logs (phần của Phát)."""
    try:
        from app.security_logging import log_security_event
        log_security_event(event_type="ACCESS_DENIED_403", severity="WARNING",
                            status_code=403, action_taken="BLOCKED")
    except Exception:
        pass
