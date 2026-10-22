"""
log_security_event() — điểm ghi nhận DUY NHẤT cho mọi sự kiện bảo mật trong hệ thống.
Mọi module (Rate Limiting của Phát, SQLi của Tuấn, XSS của Trúc, Access Control của
Khánh) đều gọi hàm này thay vì tự viết logic ghi DB riêng — đảm bảo trang
/admin/security-logs đọc được dữ liệu đồng nhất từ 1 nguồn.

Cách dùng (ví dụ cho từng người):

    from app.security_logging import log_security_event

    # Phát — trong @app.errorhandler(429) hoặc hook của Flask-Limiter:
    log_security_event(event_type="DDOS_RATE_LIMIT", severity="WARNING",
                        status_code=429, action_taken="BLOCKED")

    # Tuấn — khi phát hiện payload nghi SQL Injection (vd trong 1 input-sanitizer check):
    log_security_event(event_type="SQLI_DETECTED", severity="CRITICAL",
                        status_code=400, payload_snippet=raw_input[:200],
                        action_taken="BLOCKED")

    # Trúc — khi phát hiện thẻ <script>/on-event trong input trước khi escape:
    log_security_event(event_type="XSS_DETECTED", severity="CRITICAL",
                        status_code=400, payload_snippet=raw_input[:200],
                        action_taken="LOGGED_ONLY")  # vd nếu chỉ escape chứ không chặn hẳn

    # Khánh — đã gọi sẵn trong app/admin/decorators.py khi admin_required chặn 403.
"""
from flask import request, has_request_context
from flask_login import current_user

from app.extensions import db
from app.models.security_log import SecurityLog

VALID_EVENT_TYPES = {
    "DDOS_RATE_LIMIT",
    "BRUTE_FORCE_AUTH",
    "SQLI_DETECTED",
    "XSS_DETECTED",
    "ACCESS_DENIED_403",
}
VALID_SEVERITIES = {"INFO", "WARNING", "CRITICAL"}


def log_security_event(event_type, severity="WARNING", status_code=403,
                        payload_snippet=None, action_taken="BLOCKED"):
    """Ghi 1 dòng vào bảng security_logs. Tự lấy IP/endpoint/method/user hiện tại
    từ request context — người gọi chỉ cần truyền phần đặc thù của sự kiện.
    Không bao giờ raise exception ra ngoài (an toàn gọi từ error handler) — lỗi ghi log
    không được phép làm sập request chính."""
    ip = "0.0.0.0"
    endpoint = "/internal"
    http_method = "INTERNAL"
    user_agent = None
    user_id = None

    if has_request_context():
        try:
            from app.extensions import get_client_ip
            ip = get_client_ip()
        except Exception:
            ip = request.remote_addr or "0.0.0.0"
        endpoint = request.path
        http_method = request.method
        user_agent = (request.headers.get("User-Agent") or "")[:255] or None
        if getattr(current_user, "is_authenticated", False):
            user_id = getattr(current_user, "id", None)

    try:
        entry = SecurityLog(
            ip_address=ip,
            user_id=user_id,
            event_type=event_type if event_type in VALID_EVENT_TYPES else "UNKNOWN",
            severity=severity if severity in VALID_SEVERITIES else "WARNING",
            endpoint=endpoint,
            http_method=http_method,
            status_code=status_code,
            # Cắt ngắn + không bao giờ log mật khẩu/token — payload_snippet chỉ nên
            # chứa phần input nghi vấn (vd query string lạ), KHÔNG log nguyên request.form.
            payload_snippet=(payload_snippet or "")[:500] or None,
            user_agent=user_agent,
            action_taken=action_taken,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()
