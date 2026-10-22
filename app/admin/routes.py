"""
Routes khu vực ADMIN.

Mọi route dưới đây đều có cả @login_required (Flask-Login: phải đăng nhập)
và @admin_required (app/admin/decorators.py: phải là admin) — 2 lớp này
chính là phần chống Broken Access Control (BAC) của module bảo mật.

Hành động thay đổi dữ liệu (toggle quyền, ban, xóa) đều dùng POST + CSRF
token (Flask-WTF CSRFProtect đã bật global trong app/extensions.py), KHÔNG
dùng GET — để tránh bị gọi "nhầm" qua link/ảnh (CSRF qua GET là lỗi hay gặp).
"""
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.admin import admin_bp
from app.admin.decorators import admin_required
from app.extensions import db
from app.models.user import User
from app.models.post import Post
from app.models.security_log import SecurityLog


# ---------------------------------------------------------------- Dashboard
@admin_bp.route("/")
@login_required
@admin_required
def dashboard():
    stats = {
        "total_users": User.query.count(),
        "total_admins": User.query.filter_by(is_admin=True).count(),
        "total_banned": User.query.filter_by(is_banned=True).count(),
        "total_posts": Post.query.count(),
    }
    return render_template("admin/dashboard.html", stats=stats)


# -------------------------------------------------------------- Quản lý User
@admin_bp.route("/users")
@login_required
@admin_required
def users():
    q = request.args.get("q", "").strip()
    query = User.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(User.username.ilike(like), User.email.ilike(like))
        )
    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(User.id.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template("admin/users.html", users=pagination.items, pagination=pagination, q=q)


@admin_bp.route("/users/<int:user_id>/toggle-admin", methods=["POST"])
@login_required
@admin_required
def toggle_admin(user_id):
    target = User.query.get_or_404(user_id)
    if target.id == current_user.id:
        flash("Không thể tự bỏ quyền admin của chính mình (tránh tự khóa quyền truy cập).", "warning")
        return redirect(url_for("admin.users"))

    target.is_admin = not target.is_admin
    db.session.commit()
    flash(
        f"Đã {'cấp' if target.is_admin else 'gỡ'} quyền admin cho {target.username}.",
        "success",
    )
    return redirect(request.referrer or url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/toggle-ban", methods=["POST"])
@login_required
@admin_required
def toggle_ban(user_id):
    target = User.query.get_or_404(user_id)
    if target.id == current_user.id:
        flash("Không thể tự khóa tài khoản của chính mình.", "warning")
        return redirect(url_for("admin.users"))

    target.is_banned = not target.is_banned
    db.session.commit()
    flash(
        f"Đã {'khóa' if target.is_banned else 'mở khóa'} tài khoản {target.username}.",
        "success",
    )
    return redirect(request.referrer or url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    target = User.query.get_or_404(user_id)
    if target.id == current_user.id:
        flash("Không thể tự xóa tài khoản của chính mình.", "warning")
        return redirect(url_for("admin.users"))

    username = target.username
    db.session.delete(target)
    db.session.commit()
    flash(f"Đã xóa tài khoản {username}.", "success")
    return redirect(url_for("admin.users"))


# -------------------------------------------------------------- Quản lý Post
@admin_bp.route("/posts")
@login_required
@admin_required
def posts():
    q = request.args.get("q", "").strip()
    query = Post.query.join(User, Post.user_id == User.id)
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(Post.caption.ilike(like), User.username.ilike(like))
        )
    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(Post.id.desc()).paginate(page=page, per_page=20, error_out=False)

    # Post không có sẵn relationship tới User (xem app/models/post.py) -> tra cứu
    # username theo user_id bằng 1 dict, tránh N+1 query trong template.
    author_ids = {p.user_id for p in pagination.items}
    authors = {u.id: u for u in User.query.filter(User.id.in_(author_ids)).all()} if author_ids else {}

    return render_template(
        "admin/posts.html", posts=pagination.items, pagination=pagination, q=q, authors=authors
    )


@admin_bp.route("/posts/<int:post_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    flash(f"Đã xóa bài viết #{post_id}.", "success")
    return redirect(request.referrer or url_for("admin.posts"))


# ------------------------------------------------------ Nhật ký An ninh (Phát)
EVENT_TYPE_LABELS = {
    "DDOS_RATE_LIMIT": "DDoS / Rate Limit",
    "BRUTE_FORCE_AUTH": "Brute-force đăng nhập",
    "SQLI_DETECTED": "SQL Injection",
    "XSS_DETECTED": "XSS",
    "ACCESS_DENIED_403": "Truy cập bị từ chối (403)",
}


@admin_bp.route("/security-logs")
@login_required
@admin_required
def security_logs():
    from datetime import datetime, timedelta

    event_type = request.args.get("event_type", "").strip()
    query = SecurityLog.query
    if event_type in EVENT_TYPE_LABELS:
        query = query.filter_by(event_type=event_type)

    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(SecurityLog.timestamp.desc()).paginate(page=page, per_page=25, error_out=False)

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_q = SecurityLog.query.filter(SecurityLog.timestamp >= today_start)
    kpi = {
        "total_today": today_q.count(),
        "rate_limit_today": today_q.filter_by(event_type="DDOS_RATE_LIMIT").count(),
        "suspicious_today": today_q.filter(
            SecurityLog.event_type.in_(["SQLI_DETECTED", "XSS_DETECTED"])
        ).count(),
    }
    top_ips = (
        db.session.query(SecurityLog.ip_address, db.func.count(SecurityLog.id).label("cnt"))
        .filter(SecurityLog.timestamp >= today_start)
        .group_by(SecurityLog.ip_address)
        .order_by(db.text("cnt DESC"))
        .limit(3)
        .all()
    )

    return render_template(
        "admin/security_logs.html",
        logs=pagination.items,
        pagination=pagination,
        kpi=kpi,
        top_ips=top_ips,
        event_type=event_type,
        event_labels=EVENT_TYPE_LABELS,
    )


@admin_bp.route("/security-logs/clear", methods=["POST"])
@login_required
@admin_required
def clear_security_logs():
    """Xóa nhật ký DEMO — dùng để dọn sạch log trước khi chạy lại kịch bản tấn công mẫu
    trước mặt giảng viên (đề xuất của Phát, mục 4.3). KHÔNG dùng để xóa bằng chứng thật."""
    count = SecurityLog.query.delete()
    db.session.commit()
    flash(f"Đã xóa {count} dòng nhật ký (demo reset).", "success")
    return redirect(url_for("admin.security_logs"))
