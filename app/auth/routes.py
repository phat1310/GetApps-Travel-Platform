"""Routes AUTH — xử lý đăng ký, đăng nhập, đăng xuất, hồ sơ cá nhân (Profile),
follow/unfollow, onboarding, cài đặt, đổi mật khẩu, OTP khôi phục mật khẩu,
thông tin liên hệ, CSRF token, và đăng nhập Google OAuth.
Hỗ trợ song song cả giao diện HTML (Jinja2 + Flask-WTF + CSRF) lẫn API JSON (Postman/Mobile).
"""
import json
import os
import random
import re
import secrets
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename

from flask import (
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf.csrf import generate_csrf
from sqlalchemy import func, or_

from app.auth import auth_bp
from app.auth.forms import (
    ChangePasswordForm,
    EditProfileForm,
    ForgotPasswordForm,
    LoginForm,
    RegisterForm,
    ResetPasswordForm,
    SettingsForm,
)
from app.auth.utils import validate_password
from app.extensions import db, csrf
from app.models import (
    Comment,
    Follow,
    Itinerary,
    Like,
    Location,
    Notification,
    Photo,
    Post,
    SavedPost,
    User,
)

FIXED_TAGS = {"nguoi_du_lich", "dia_phuong", "phuot", "huong_dan_vien", "nguoi_noi_tieng"}

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


@auth_bp.route('/', methods=['GET'])
def index():
    """Trang chủ — chuyển hướng về dòng tin feed."""
    return redirect(url_for('locations.feed'))


@auth_bp.route('/explore', methods=['GET'])
def explore():
    """Trang Khám phá địa điểm & trải nghiệm du lịch cộng đồng."""
    locations = Location.query.all()
    recent_posts = Post.query.order_by(Post.created_at.desc()).limit(9).all()
    featured_plans = Itinerary.query.filter_by(visibility='public').order_by(Itinerary.created_at.desc()).limit(6).all()
    return render_template(
        'explore.html',
        locations=locations,
        recent_posts=recent_posts,
        featured_plans=featured_plans
    )


# =========================================================
# ĐĂNG KÝ
# =========================================================

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Đăng ký tài khoản người dùng mới (hỗ trợ song song HTML Form và JSON API)."""
    if current_user.is_authenticated:
        logout_user()

    if request.method == 'GET':
        form = RegisterForm()
        return render_template('auth/register.html', form=form)

    if request.is_json:
        data = request.get_json(silent=True) or {}
        username = (data.get('username') or '').strip()
        email = (data.get('email') or '').strip().lower()
        password = data.get('password') or ''
        role = data.get('role', 'traveler')

        if not username or not email or not password:
            return jsonify({"error": "Thiếu username/email/password"}), 400

        password_error = validate_password(password)
        if password_error:
            return jsonify({"error": password_error}), 400

        if User.query.filter_by(username=username).first():
            return jsonify({"error": "Username đã tồn tại"}), 400

        if User.query.filter_by(email=email).first():
            return jsonify({"error": "Email đã tồn tại"}), 400

        user = User(username=username, email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        return jsonify({
            "message": "Đăng ký thành công",
            "user_id": user.id,
            "profile_completed": user.profile_completed,
        }), 201

    form = RegisterForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        email = form.email.data.strip().lower()

        if User.query.filter_by(username=username).first():
            form.username.errors.append("Tên người dùng này đã được sử dụng")
            return render_template('auth/register.html', form=form), 400

        if User.query.filter_by(email=email).first():
            form.email.errors.append("Địa chỉ email này đã được đăng ký tài khoản")
            return render_template('auth/register.html', form=form), 400

        try:
            user = User(
                username=username,
                email=email,
                role=form.role.data
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()

            if current_user.is_authenticated:
                logout_user()

            flash("Đăng ký tài khoản thành công! Vui lòng đăng nhập để tiếp tục.", "success")
            return redirect(url_for('auth.login', registered='1'))
        except Exception as e:
            db.session.rollback()
            flash(f"Lỗi khi tạo tài khoản: {str(e)}", "error")
            return render_template('auth/register.html', form=form), 500

    return render_template('auth/register.html', form=form), 400 if form.errors else 200


# =========================================================
# ĐĂNG NHẬP
# =========================================================

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Đăng nhập tài khoản người dùng — hỗ trợ linh hoạt Username, Email (không phân biệt chữ hoa/thường) hoặc Số điện thoại."""
    if request.method == 'GET':
        if (request.args.get('registered') or request.args.get('switch')) and current_user.is_authenticated:
            logout_user()

        if current_user.is_authenticated:
            return redirect(url_for('locations.feed'))
        form = LoginForm()
        return render_template('auth/login.html', form=form)

    if request.is_json:
        data = request.get_json(silent=True) or {}
        raw_val = (data.get('username') or '').strip()
        password = data.get('password') or ''

        if not raw_val or not password:
            return jsonify({"error": "Sai username hoặc password"}), 401

        user = User.query.filter(
            or_(
                func.lower(User.username) == raw_val.lower(),
                func.lower(User.email) == raw_val.lower(),
                User.phone_number == raw_val
            )
        ).first()

        if not user or not user.check_password(password):
            return jsonify({"error": "Sai username hoặc password"}), 401

        if current_user.is_authenticated:
            logout_user()
        login_user(user)
        return jsonify({"message": "Đăng nhập thành công", "username": user.username})

    form = LoginForm()
    if form.validate_on_submit():
        login_val = form.username.data.strip()
        password = form.password.data

        user = User.query.filter(
            or_(
                func.lower(User.username) == login_val.lower(),
                func.lower(User.email) == login_val.lower(),
                User.phone_number == login_val
            )
        ).first()

        if not user or not user.check_password(password):
            flash("Tên đăng nhập hoặc mật khẩu không chính xác.", "error")
            return render_template('auth/login.html', form=form), 401

        if current_user.is_authenticated:
            logout_user()
        login_user(user, remember=form.remember_me.data)
        flash(f"Chào mừng trở lại, {user.nickname or user.username}!", "success")

        if not user.profile_completed:
            return redirect(url_for('auth.onboarding'))

        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)
        return redirect(url_for('locations.feed'))

    return render_template('auth/login.html', form=form), 400 if form.errors else 200


# =========================================================
# ĐĂNG XUẤT
# =========================================================

@auth_bp.route("/logout", methods=["GET", "POST"])
@login_required
@csrf.exempt
def logout():
    """Đăng xuất người dùng."""
    logout_user()
    if request.is_json or (request.headers.get("X-Requested-With") == "XMLHttpRequest" and not request.accept_mimetypes.accept_html):
        return jsonify({"message": "Đăng xuất thành công"})
    flash("Bạn đã đăng xuất tài khoản an toàn.", "info")
    return redirect(url_for('auth.login'))


# =========================================================
# PROFILE CÁ NHÂN
# =========================================================

@auth_bp.route('/profile', methods=['GET'])
@auth_bp.route('/profile/<username>', methods=['GET'])
@login_required
def profile(username=None):
    """Trang cá nhân của chính mình hoặc người dùng khác."""
    if username:
        profile_user = User.query.filter_by(username=username).first_or_404()
    else:
        profile_user = current_user

    posts_count = Post.query.filter_by(user_id=profile_user.id).count()
    followers_count = Follow.query.filter_by(followed_id=profile_user.id).count()
    following_count = Follow.query.filter_by(follower_id=profile_user.id).count()
    is_following = bool(
        Follow.query.filter_by(follower_id=current_user.id, followed_id=profile_user.id).first()
    ) if current_user.id != profile_user.id else False

    raw_posts = Post.query.filter_by(user_id=profile_user.id).order_by(Post.created_at.desc()).all()
    user_posts = []
    for p in raw_posts:
        photos = Photo.query.filter_by(post_id=p.id).all()
        likes_cnt = Like.query.filter_by(post_id=p.id).count()
        cmts_cnt = Comment.query.filter_by(post_id=p.id).count()
        user_posts.append({
            "id": p.id,
            "caption": p.caption,
            "photos": photos,
            "likes_count": likes_cnt,
            "comments_count": cmts_cnt
        })

    saved_posts = []
    if profile_user.id == current_user.id:
        saved_items = SavedPost.query.filter_by(user_id=current_user.id).order_by(SavedPost.id.desc()).all()
        for item in saved_items:
            sp = Post.query.get(item.post_id)
            if sp:
                photos = Photo.query.filter_by(post_id=sp.id).all()
                likes_cnt = Like.query.filter_by(post_id=sp.id).count()
                cmts_cnt = Comment.query.filter_by(post_id=sp.id).count()
                saved_posts.append({
                    "id": sp.id,
                    "caption": sp.caption,
                    "photos": photos,
                    "likes_count": likes_cnt,
                    "comments_count": cmts_cnt
                })

    edit_form = EditProfileForm(obj=profile_user) if profile_user.id == current_user.id else None

    return render_template(
        'auth/profile.html',
        profile_user=profile_user,
        posts_count=posts_count,
        followers_count=followers_count,
        following_count=following_count,
        is_following=is_following,
        user_posts=user_posts,
        saved_posts=saved_posts,
        edit_form=edit_form
    )


@auth_bp.route('/profile/edit', methods=['POST'])
@login_required
def edit_profile():
    """Chỉnh sửa thông tin cá nhân (Bio, số điện thoại, vai trò)."""
    form = EditProfileForm()
    if form.validate_on_submit():
        current_user.bio = form.bio.data.strip() if form.bio.data else None
        current_user.phone_number = form.phone_number.data.strip() if form.phone_number.data else None
        current_user.role = form.role.data
        db.session.commit()
        flash("Cập nhật hồ sơ cá nhân thành công!", "success")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{error}", "error")

    return redirect(url_for('auth.profile'))


# =========================================================
# FOLLOW / UNFOLLOW USER
# =========================================================

@auth_bp.route("/follow/<int:user_id>", methods=["POST"])
@login_required
def follow(user_id):
    """Theo dõi người dùng khác và tạo thông báo (Notification)."""
    if current_user.id == user_id:
        return jsonify({"error": "Không thể tự follow chính mình"}), 400

    followed_user = db.session.get(User, user_id)
    if not followed_user:
        return jsonify({"error": "Không tìm thấy user"}), 404

    existing = Follow.query.filter_by(
        follower_id=current_user.id, followed_id=user_id).first()
    if existing:
        return jsonify({"error": "Đã follow rồi"}), 400

    new_follow = Follow(
        follower_id=current_user.id,
        followed_id=user_id
    )
    db.session.add(new_follow)

    notification = Notification(
        user_id=user_id,
        actor_id=current_user.id,
        notification_type="follow",
        post_id=None
    )
    db.session.add(notification)

    db.session.commit()
    return jsonify({"message": f"Đã follow user {user_id}"}), 201


@auth_bp.route("/unfollow/<int:user_id>", methods=["POST"])
@login_required
def unfollow(user_id):
    """Hủy theo dõi người dùng."""
    follow_record = Follow.query.filter_by(
        follower_id=current_user.id,
        followed_id=user_id
    ).first()

    if not follow_record:
        return jsonify({"error": "Chưa follow user này"}), 400

    db.session.delete(follow_record)
    db.session.commit()
    return jsonify({"message": f"Đã unfollow user {user_id}"})


# =========================================================
# CÀI ĐẶT TÀI KHOẢN — BẢN CỦA KHÁNH (khớp mockup, giữ nguyên /settings)
# =========================================================

@auth_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings_page():
    if request.method == "POST":
        return settings()
    return render_template("settings.html")


# =========================================================
# CÀI ĐẶT TÀI KHOẢN — BẢN CỦA PHÁT (chuyển qua /profile/settings để khỏi đụng route trên)
# =========================================================

@auth_bp.route('/profile/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """Giao diện & Xử lý Cài đặt tài khoản người dùng theo Proposal GEs."""
    form = SettingsForm()

    if request.method == 'GET':
        form.nickname.data = current_user.nickname or current_user.username
        form.profile_tag.data = current_user.profile_tag or "#nguoidulich"
        form.email.data = current_user.email
        form.phone_number.data = current_user.phone_number or ""
        form.bio.data = current_user.bio or ""
        form.avatar_url.data = current_user.avatar_url or ""
        return render_template('auth/settings.html', form=form)

    if request.is_json:
        data = request.get_json(silent=True) or {}
        email = (data.get('email') or '').strip().lower()
        if email and email != current_user.email.lower():
            if User.query.filter(func.lower(User.email) == email, User.id != current_user.id).first():
                return jsonify({"error": "Địa chỉ email này đã được sử dụng bởi tài khoản khác"}), 400
            current_user.email = email

        if 'nickname' in data:
            current_user.nickname = data['nickname'].strip() if data['nickname'] else None
        if 'profile_tag' in data:
            tag = data['profile_tag'].strip()
            if tag and not tag.startswith('#'):
                tag = f"#{tag}"
            current_user.profile_tag = tag or "#nguoidulich"
        if 'phone_number' in data:
            current_user.phone_number = data['phone_number'].strip() if data['phone_number'] else None
        if 'bio' in data:
            current_user.bio = data['bio'].strip() if data['bio'] else None
        if 'avatar_url' in data:
            current_user.avatar_url = data['avatar_url'].strip() if data['avatar_url'] else None

        db.session.commit()
        return jsonify({
            "message": "Cập nhật cài đặt thành công",
            "nickname": current_user.nickname or current_user.username,
            "profile_tag": current_user.profile_tag,
            "email": current_user.email,
            "phone_number": current_user.phone_number,
            "bio": current_user.bio,
            "avatar_url": current_user.avatar_url
        })

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        if email != current_user.email.lower():
            existing = User.query.filter(func.lower(User.email) == email, User.id != current_user.id).first()
            if existing:
                flash("Địa chỉ email này đã được sử dụng bởi tài khoản khác.", "error")
                return render_template('auth/settings.html', form=form), 400
            current_user.email = email

        current_user.nickname = form.nickname.data.strip() if form.nickname.data else None
        tag = form.profile_tag.data.strip() if form.profile_tag.data else "#nguoidulich"
        if tag and not tag.startswith('#'):
            tag = f"#{tag}"
        current_user.profile_tag = tag

        current_user.phone_number = form.phone_number.data.strip() if form.phone_number.data else None
        current_user.bio = form.bio.data.strip() if form.bio.data else None
        if form.avatar_url.data:
            current_user.avatar_url = form.avatar_url.data.strip()

        db.session.commit()
        flash("Cập nhật thông tin cài đặt thành công!", "success")
        return redirect(url_for('auth.settings'))

    return render_template('auth/settings.html', form=form), 400 if form.errors else 200


@auth_bp.route('/api/profile/tag', methods=['POST'])
@login_required
@csrf.exempt
def update_profile_tag():
    """API cập nhật nhanh nhãn hồ sơ từ modal Chọn Nhãn Hồ Sơ."""
    data = request.get_json(silent=True) if request.is_json else request.form
    data = data or {}
    tag = (data.get('tag') or '').strip()
    if not tag:
        return jsonify({"error": "Nhãn không được để trống"}), 400

    if not tag.startswith('#'):
        tag = f"#{tag}"

    current_user.profile_tag = tag
    db.session.commit()
    return jsonify({"message": "Cập nhật nhãn thành công", "tag": current_user.profile_tag})


@auth_bp.route('/api/profile/avatar', methods=['POST'])
@login_required
@csrf.exempt
def update_profile_avatar():
    """API cập nhật ảnh đại diện: hỗ trợ upload trực tiếp từ thiết bị lẫn đường dẫn URL."""
    if 'avatar_file' in request.files or 'file' in request.files or 'avatar' in request.files:
        uploaded_file = request.files.get('avatar_file') or request.files.get('file') or request.files.get('avatar')
        if uploaded_file and uploaded_file.filename:
            filename = secure_filename(uploaded_file.filename)
            ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
            allowed_exts = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'}
            if ext not in allowed_exts:
                return jsonify({"error": "Định dạng file không hỗ trợ. Vui lòng chọn ảnh JPG, PNG, WEBP hoặc GIF"}), 400

            unique_filename = f"avatar_{current_user.id}_{secrets.token_hex(6)}.{ext}"
            upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'avatars')
            os.makedirs(upload_dir, exist_ok=True)
            file_path = os.path.join(upload_dir, unique_filename)
            uploaded_file.save(file_path)

            current_user.avatar_url = f"/static/uploads/avatars/{unique_filename}"
            db.session.commit()
            return jsonify({
                "message": "Cập nhật ảnh đại diện thành công",
                "avatar_url": current_user.avatar_url
            })

    data = request.get_json(silent=True) if request.is_json else request.form
    data = data or {}
    avatar_url = (data.get('avatar_url') or '').strip()
    if not avatar_url:
        return jsonify({"error": "Vui lòng chọn file ảnh từ thiết bị hoặc nhập đường dẫn ảnh hợp lệ"}), 400

    current_user.avatar_url = avatar_url
    db.session.commit()
    return jsonify({"message": "Cập nhật ảnh đại diện thành công", "avatar_url": current_user.avatar_url})


# =========================================================
# ONBOARDING & THÔNG TIN LIÊN HỆ (DEV PACK)
# =========================================================

@auth_bp.route("/onboarding", methods=["GET", "POST"])
@login_required
def onboarding():
    """Thiết lập hồ sơ ban đầu sau khi đăng ký theo Slide 23 của Proposal."""
    if request.method == "GET":
        if current_user.profile_completed:
            return redirect(url_for("locations.feed"))
        return render_template("auth/onboarding.html")

    # Xử lý POST (hỗ trợ cả JSON API lẫn Form HTML)
    if request.is_json:
        data = request.get_json(silent=True) or {}
        nickname = data.get("nickname")
        avatar_url = data.get("avatar_url")
        tags = data.get("tags", [])
    else:
        nickname = request.form.get("nickname")
        avatar_url = request.form.get("avatar_url")
        tags = request.form.getlist("tags")
        if not tags and request.form.get("tag"):
            tags = [request.form.get("tag")]

        # Hỗ trợ upload ảnh đại diện trực tiếp từ thiết bị
        if "avatar_file" in request.files or "file" in request.files or "avatar" in request.files:
            uploaded_file = request.files.get("avatar_file") or request.files.get("file") or request.files.get("avatar")
            if uploaded_file and uploaded_file.filename:
                ext = uploaded_file.filename.rsplit(".", 1)[-1].lower() if "." in uploaded_file.filename else "png"
                if ext in {"png", "jpg", "jpeg", "webp", "gif"}:
                    unique_filename = f"avatar_{current_user.id}_{secrets.token_hex(6)}.{ext}"
                    upload_dir = os.path.join(current_app.root_path, "static", "uploads", "avatars")
                    os.makedirs(upload_dir, exist_ok=True)
                    uploaded_file.save(os.path.join(upload_dir, unique_filename))
                    avatar_url = f"/static/uploads/avatars/{unique_filename}"

    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    if not isinstance(tags, list):
        if request.is_json:
            return jsonify({"error": "tags phải là một danh sách"}), 400
        flash("Danh sách nhãn không hợp lệ", "error")
        return render_template("auth/onboarding.html"), 400

    if len(tags) > 3:
        if request.is_json:
            return jsonify({"error": "Chỉ được chọn tối đa 3 nhãn"}), 400
        flash("Chỉ được chọn tối đa 3 nhãn", "error")
        return render_template("auth/onboarding.html"), 400

    invalid_tags = [t for t in tags if t not in FIXED_TAGS]
    if invalid_tags:
        if request.is_json:
            return jsonify({
                "error": f"Nhãn không hợp lệ: {', '.join(invalid_tags)}",
                "allowed_tags": sorted(FIXED_TAGS),
            }), 400
        flash(f"Nhãn không hợp lệ: {', '.join(invalid_tags)}", "error")
        return render_template("auth/onboarding.html"), 400

    if nickname:
        current_user.nickname = nickname.strip()
    if avatar_url:
        current_user.avatar_url = avatar_url.strip()
    if tags:
        current_user.tags = ",".join(tags)
        tag_map = {
            "nguoi_du_lich": "#nguoidulich",
            "dia_phuong": "#dandiaphuong",
            "phuot": "#daphuot",
            "huong_dan_vien": "#huongdanvien",
            "nguoi_noi_tieng": "#nguoidanoitieng"
        }
        current_user.profile_tag = tag_map.get(tags[0], f"#{tags[0]}")

    current_user.profile_completed = True
    db.session.commit()

    if request.is_json:
        return jsonify({
            "message": "Hoàn tất onboarding",
            "user": {
                "id": current_user.id,
                "nickname": current_user.nickname,
                "avatar_url": current_user.avatar_url,
                "tags": current_user.tags,
                "profile_completed": current_user.profile_completed,
            },
        })

    flash("Hồ sơ đã được thiết lập thành công! Chào mừng bạn đến với GEs.", "success")
    return redirect(url_for("locations.feed"))


@auth_bp.route("/onboarding/skip", methods=["GET", "POST"])
@login_required
def onboarding_skip():
    """Bỏ qua bước onboarding và hoàn tất profile mặc định."""
    current_user.profile_completed = True
    db.session.commit()
    return redirect(url_for("locations.feed"))


@auth_bp.route("/notifications", methods=["GET"])
@login_required
def notifications_page():
    """Giao diện danh sách thông báo hoạt động của người dùng."""
    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(
        Notification.created_at.desc()
    ).limit(50).all()

    # Đánh dấu đã đọc
    for n in notifications:
        n.is_read = True
    db.session.commit()

    return render_template("auth/notifications.html", notifications=notifications)


@auth_bp.route("/settings/contact", methods=["POST"])
@login_required
def update_contact():
    """Cập nhật thông tin liên hệ: số điện thoại và email phụ."""
    data = request.get_json(silent=True) or {}
    phone_number = data.get("phone_number")
    secondary_email = data.get("secondary_email")

    if not phone_number and not secondary_email:
        return jsonify({"error": "Cần cung cấp phone_number hoặc secondary_email"}), 400

    if secondary_email:
        if "@" not in secondary_email or "." not in secondary_email:
            return jsonify({"error": "secondary_email không hợp lệ"}), 400

        if secondary_email == current_user.email:
            return jsonify({"error": "secondary_email không được trùng với email chính"}), 400

        existing = User.query.filter(
            (User.email == secondary_email) | (User.secondary_email == secondary_email)
        ).filter(User.id != current_user.id).first()
        if existing:
            return jsonify({"error": "Email này đã được dùng bởi tài khoản khác"}), 400

        current_user.secondary_email = secondary_email

    if phone_number:
        current_user.phone_number = phone_number

    db.session.commit()

    return jsonify({
        "message": "Cập nhật thông tin liên hệ thành công",
        "user": {
            "phone_number": current_user.phone_number,
            "secondary_email": current_user.secondary_email,
        },
    })


@auth_bp.route("/csrf-token", methods=["GET"])
def csrf_token():
    """Lấy CSRF token cho AJAX/Single Page requests."""
    return jsonify({"csrf_token": generate_csrf()})


# =========================================================
# ĐỔI MẬT KHẨU
# =========================================================

@auth_bp.route('/change-password', methods=['GET', 'POST'])
@auth_bp.route('/settings/password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Đổi mật khẩu người dùng (hỗ trợ cả Web Form và JSON API)."""
    form = ChangePasswordForm()

    if request.is_json:
        data = request.get_json(silent=True) or {}
        old_password = data.get('old_password') or data.get('current_password', '')
        new_password = data.get('new_password', '')

        if not old_password or not new_password:
            return jsonify({"error": "Thiếu old_password/new_password"}), 400

        if not current_user.check_password(old_password):
            return jsonify({"error": "Mật khẩu cũ không đúng"}), 401

        if old_password == new_password:
            return jsonify({"error": "Mật khẩu mới phải khác mật khẩu cũ"}), 400

        password_error = validate_password(new_password)
        if password_error:
            return jsonify({"error": password_error}), 400

        current_user.set_password(new_password)
        db.session.commit()
        return jsonify({"message": "Đổi mật khẩu thành công"}), 200

    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            form.current_password.errors.append("Mật khẩu hiện tại không chính xác")
            return render_template('auth/change_password.html', form=form), 400

        if form.current_password.data == form.new_password.data:
            form.new_password.errors.append("Mật khẩu mới không được trùng với mật khẩu cũ")
            return render_template('auth/change_password.html', form=form), 400

        current_user.set_password(form.new_password.data)
        db.session.commit()
        flash("Đổi mật khẩu thành công! Mật khẩu mới của bạn đã có hiệu lực.", "success")
        return redirect(url_for('auth.profile'))

    return render_template('auth/change_password.html', form=form), 400 if form.errors else 200


# =========================================================
# QUÊN MẬT KHẨU & KHÔI PHỤC BẰNG OTP
# =========================================================

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Yêu cầu khôi phục mật khẩu qua Email hoặc Số điện thoại (SĐT)."""
    if current_user.is_authenticated:
        return redirect(url_for('locations.feed'))

    form = ForgotPasswordForm()

    if request.is_json:
        data = request.get_json(silent=True) or {}
        target = (data.get('target') or '').strip()
        method = data.get('method') or ('email' if '@' in target else 'phone')

        if not target:
            return jsonify({"error": "Vui lòng cung cấp Email hoặc Số điện thoại"}), 400

        user = None
        if '@' in target or method == 'email':
            user = User.query.filter_by(email=target).first()
            if not user:
                user = User.query.filter_by(phone_number=target).first()
        else:
            user = User.query.filter_by(phone_number=target).first()
            if not user:
                user = User.query.filter_by(email=target).first()

        if not user:
            return jsonify({"error": "Không tìm thấy tài khoản tương ứng với thông tin đã nhập"}), 404

        otp_code = f"{random.randint(100000, 999999)}"
        session['reset_user_id'] = user.id
        session['reset_otp'] = otp_code
        session['reset_target'] = target
        session['reset_method'] = method
        session['reset_expires_at'] = (datetime.utcnow() + timedelta(minutes=10)).timestamp()

        masked_target = target[:3] + "***" + target[-3:] if len(target) > 6 else target
        return jsonify({
            "message": f"Mã xác nhận OTP đã được gửi đến {masked_target}",
            "otp": otp_code,
            "target": masked_target
        }), 200

    if form.validate_on_submit():
        target = form.target.data.strip()
        method = form.method.data

        user = None
        if method == 'email' or '@' in target:
            user = User.query.filter_by(email=target).first()
            if not user:
                user = User.query.filter_by(phone_number=target).first()
        else:
            user = User.query.filter_by(phone_number=target).first()
            if not user:
                user = User.query.filter_by(email=target).first()

        if not user:
            channel_name = "Email" if (method == 'email' or '@' in target) else "Số điện thoại"
            form.target.errors.append(f"Không tìm thấy tài khoản nào gắn với {channel_name} này.")
            return render_template('auth/forgot_password.html', form=form), 400

        otp_code = f"{random.randint(100000, 999999)}"
        session['reset_user_id'] = user.id
        session['reset_otp'] = otp_code
        session['reset_target'] = target
        session['reset_method'] = method
        session['reset_expires_at'] = (datetime.utcnow() + timedelta(minutes=10)).timestamp()

        masked_target = target[:3] + "***" + target[-3:] if len(target) > 6 else target
        channel_label = "Email" if (method == 'email' or '@' in target) else "Số điện thoại"
        flash(f"Mã xác nhận OTP đã được gửi đến {channel_label} {masked_target}. (Mã kiểm thử: {otp_code} — có hiệu lực 10 phút)", "info")

        return redirect(url_for('auth.reset_password'))

    return render_template('auth/forgot_password.html', form=form)


@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    """Xác thực mã OTP và Đặt lại mật khẩu mới."""
    if current_user.is_authenticated:
        return redirect(url_for('locations.feed'))

    user_id = session.get('reset_user_id')
    stored_otp = session.get('reset_otp')
    expires_at = session.get('reset_expires_at', 0)
    target = session.get('reset_target', '')
    method = session.get('reset_method', 'email')

    if not user_id or not stored_otp:
        flash("Vui lòng gửi yêu cầu khôi phục mật khẩu trước.", "warning")
        return redirect(url_for('auth.forgot_password'))

    if datetime.utcnow().timestamp() > expires_at:
        session.pop('reset_user_id', None)
        session.pop('reset_otp', None)
        session.pop('reset_expires_at', None)
        session.pop('reset_target', None)
        flash("Mã xác nhận OTP đã hết hạn (quá 10 phút). Vui lòng yêu cầu mã mới.", "error")
        return redirect(url_for('auth.forgot_password'))

    form = ResetPasswordForm()

    if request.is_json:
        data = request.get_json(silent=True) or {}
        otp = (data.get('otp') or '').strip()
        new_pwd = data.get('new_password', '')
        confirm_pwd = data.get('confirm_new_password', '')

        if otp != stored_otp:
            return jsonify({"error": "Mã xác thực OTP không chính xác"}), 400

        if new_pwd != confirm_pwd:
            return jsonify({"error": "Mật khẩu xác nhận không khớp"}), 400

        if len(new_pwd) < 8 or not re.search(r'[A-Z]', new_pwd) or not re.search(r'[a-z]', new_pwd) or not re.search(r'[@$!%*?&#^()_+\-=\[\]{};:\'",.<>\/\\|`~]', new_pwd):
            return jsonify({"error": "Mật khẩu mới phải từ 8 ký tự, gồm chữ hoa, chữ thường và ký tự đặc biệt"}), 400

        user = db.session.get(User, user_id)
        if not user:
            return jsonify({"error": "Tài khoản không tồn tại"}), 404

        if user.check_password(new_pwd):
            return jsonify({"error": "Mật khẩu mới không được trùng với mật khẩu cũ"}), 400

        user.set_password(new_pwd)
        db.session.commit()

        session.pop('reset_user_id', None)
        session.pop('reset_otp', None)
        session.pop('reset_expires_at', None)
        session.pop('reset_target', None)
        session.pop('reset_method', None)

        return jsonify({"message": "Đặt lại mật khẩu thành công"}), 200

    if form.validate_on_submit():
        if form.otp.data.strip() != stored_otp:
            form.otp.errors.append("Mã xác thực OTP không chính xác.")
            return render_template('auth/reset_password.html', form=form, target=target, method=method), 400

        user = db.session.get(User, user_id)
        if not user:
            flash("Tài khoản không tồn tại hoặc đã bị xóa.", "error")
            return redirect(url_for('auth.forgot_password'))

        if user.check_password(form.new_password.data):
            form.new_password.errors.append("Mật khẩu mới không được trùng với mật khẩu cũ.")
            return render_template('auth/reset_password.html', form=form, target=target, method=method), 400

        user.set_password(form.new_password.data)
        db.session.commit()

        session.pop('reset_user_id', None)
        session.pop('reset_otp', None)
        session.pop('reset_expires_at', None)
        session.pop('reset_target', None)
        session.pop('reset_method', None)

        flash("Đặt lại mật khẩu thành công! Bạn có thể đăng nhập bằng mật khẩu mới.", "success")
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', form=form, target=target, method=method), 400 if form.errors else 200


@auth_bp.route('/resend-otp', methods=['POST'])
def resend_otp():
    """Gửi lại mã xác nhận OTP mới."""
    user_id = session.get('reset_user_id')
    target = session.get('reset_target')
    method = session.get('reset_method', 'email')

    if not user_id or not target:
        if request.is_json:
            return jsonify({"error": "Không tìm thấy phiên khôi phục mật khẩu hợp lệ"}), 400
        flash("Vui lòng thực hiện yêu cầu khôi phục mật khẩu từ đầu.", "warning")
        return redirect(url_for('auth.forgot_password'))

    new_otp = f"{random.randint(100000, 999999)}"
    session['reset_otp'] = new_otp
    session['reset_expires_at'] = (datetime.utcnow() + timedelta(minutes=10)).timestamp()

    masked_target = target[:3] + "***" + target[-3:] if len(target) > 6 else target
    channel_label = "Email" if method == 'email' else "Số điện thoại"

    if request.is_json:
        return jsonify({
            "message": f"Đã gửi lại mã OTP đến {masked_target}",
            "otp": new_otp
        }), 200

    flash(f"Mã OTP mới đã được gửi lại tới {channel_label} {masked_target}. (Mã kiểm thử: {new_otp})", "info")
    return redirect(url_for('auth.reset_password'))


# ===========================================================================
# ĐĂNG NHẬP BẰNG GOOGLE (OAuth 2.0 Authorization Code) — chỉ dùng urllib chuẩn
# ===========================================================================

def _google_exchange_code(code, redirect_uri):
    """Đổi authorization code lấy access_token từ Google."""
    body = urllib.parse.urlencode({
        "code": code,
        "client_id": current_app.config["GOOGLE_CLIENT_ID"],
        "client_secret": current_app.config["GOOGLE_CLIENT_SECRET"],
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }).encode()
    req = urllib.request.Request(GOOGLE_TOKEN_URL, data=body, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def _google_get_userinfo(access_token):
    """Lấy thông tin người dùng (sub, email, name, picture) từ Google."""
    req = urllib.request.Request(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def _unique_username(base):
    """Sinh username chưa bị dùng, thêm số phía sau nếu trùng."""
    base = (base or "user")[:50]
    username = base
    n = 1
    while User.query.filter_by(username=username).first():
        n += 1
        username = f"{base}{n}"
    return username


@auth_bp.route("/auth/google/login", methods=["GET"])
def google_login():
    """Khởi động quy trình đăng nhập Google OAuth."""
    if not current_app.config.get("GOOGLE_CLIENT_ID") or not current_app.config.get("GOOGLE_CLIENT_SECRET"):
        return jsonify({"error": "Chưa cấu hình GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET trong .env"}), 500

    state = secrets.token_urlsafe(32)
    session["google_oauth_state"] = state

    params = urllib.parse.urlencode({
        "client_id": current_app.config["GOOGLE_CLIENT_ID"],
        "redirect_uri": url_for("auth.google_callback", _external=True),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
    })
    return redirect(f"{GOOGLE_AUTH_URL}?{params}")


@auth_bp.route("/auth/google/callback", methods=["GET"])
def google_callback():
    """Xử lý phản hồi từ Google sau khi người dùng đồng ý đăng nhập."""
    if request.args.get("error"):
        return jsonify({"error": "Bạn đã hủy đăng nhập Google"}), 400

    expected_state = session.pop("google_oauth_state", None)
    if not expected_state or request.args.get("state") != expected_state:
        return jsonify({"error": "State không hợp lệ, vui lòng đăng nhập lại"}), 400

    code = request.args.get("code")
    if not code:
        return jsonify({"error": "Thiếu authorization code"}), 400

    redirect_uri = url_for("auth.google_callback", _external=True)
    try:
        token = _google_exchange_code(code, redirect_uri)
        userinfo = _google_get_userinfo(token["access_token"])
    except urllib.error.HTTPError as e:
        current_app.logger.error("Google HTTPError %s: %s", e.code, e.read().decode(errors="replace"))
        return jsonify({"error": "Google từ chối yêu cầu, vui lòng thử lại"}), 502
    except (urllib.error.URLError, KeyError, ValueError) as e:
        current_app.logger.error("Google OAuth lỗi: %r", e)
        return jsonify({"error": "Không kết nối được với Google, vui lòng thử lại"}), 502

    google_id = userinfo.get("sub")
    email = userinfo.get("email")
    if not google_id or not email or not userinfo.get("email_verified"):
        return jsonify({"error": "Tài khoản Google chưa có email đã xác minh"}), 400

    user = User.query.filter_by(google_id=google_id).first()

    if not user:
        user = User.query.filter_by(email=email).first()
        if user:
            user.google_id = google_id
        else:
            user = User(
                username=_unique_username(email.split("@")[0]),
                email=email,
                google_id=google_id,
                avatar_url=userinfo.get("picture"),
                nickname=userinfo.get("name"),
            )
            user.set_password(secrets.token_urlsafe(32))
            db.session.add(user)
        db.session.commit()

    login_user(user)
    return jsonify({
        "message": "Đăng nhập Google thành công",
        "user_id": user.id,
        "username": user.username,
        "profile_completed": user.profile_completed,
    })