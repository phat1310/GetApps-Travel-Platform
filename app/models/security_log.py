"""Model SECURITY_LOG — nhật ký sự kiện bảo mật (Audit Log), dùng chung cho
toàn bộ module bảo mật của team: 429 Rate Limit (Phát), SQL Injection (Tuấn),
XSS (Trúc), 403 Access Denied / Broken Access Control (Khánh).

Schema theo đúng đề xuất của Phát (10_Bao_Cao_Rate_Limiting_DDoS...pdf, mục 4.2).
Hiển thị tại /admin/security-logs — xem app/admin/routes.py.
"""

from datetime import datetime
from app.extensions import db


class SecurityLog(db.Model):
    __tablename__ = 'security_logs'

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    ip_address = db.Column(db.String(45), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Loại sự kiện: DDOS_RATE_LIMIT, BRUTE_FORCE_AUTH, SQLI_DETECTED, XSS_DETECTED, ACCESS_DENIED_403
    event_type = db.Column(db.String(50), nullable=False, index=True)
    severity = db.Column(db.String(20), default='WARNING')  # INFO, WARNING, CRITICAL
    endpoint = db.Column(db.String(255), nullable=False)
    http_method = db.Column(db.String(10), nullable=False)
    status_code = db.Column(db.Integer, nullable=False)

    # Chi tiết: payload nghi vấn (KHÔNG lưu mật khẩu/token thật), user-agent
    payload_snippet = db.Column(db.Text, nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    action_taken = db.Column(db.String(50), default='BLOCKED')  # BLOCKED, LOGGED_ONLY

    user = db.relationship('User', foreign_keys=[user_id])

    def __repr__(self):
        return f'<SecurityLog {self.event_type} {self.ip_address} {self.status_code}>'
