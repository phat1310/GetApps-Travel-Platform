"""Routes AUTH — xử lý đăng ký, đăng nhập, đăng xuất, hồ sơ cá nhân (Profile) và follow/unfollow.
Hỗ trợ song song cả giao diện HTML (Jinja2 + Flask-WTF + CSRF) lẫn API JSON (Postman/Mobile).
"""
import re
from flask import request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from app.auth import auth_bp
from app.auth.forms import LoginForm, RegisterForm, EditProfileForm
from app.extensions import db
from app.models import User, Follow, Post, Photo, Like, Comment, SavedPost

@auth_bp.route('/', methods=['GET'])
def index():
    """Trang chủ — chuyển hướng về dòng tin feed."""
    return redirect(url_for('locations.feed'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Đăng ký tài khoản người dùng mới."""
    if request.method == 'GET':
        if current_user.is_authenticated:
            return redirect(url_for('locations.feed'))
        form = RegisterForm()
        return render_template('auth/register.html', form=form)

    # 1. Nếu client gửi JSON (API / Automation tests)
    if request.is_json:
        data = request.get_json() or {}
        username = (data.get('username') or '').strip()
        email = (data.get('email') or '').strip().lower()
        password = data.get('password') or ''
        role = data.get('role', 'traveler')

        if not username or not email or not password:
            return jsonify({"error": "Thiếu username/email/password"}), 400

        if len(password) < 8 or not re.search(r'[A-Z]', password) or not re.search(r'[a-z]', password) or not re.search(r'[@$!%*?&#^()_+\-=\[\]{};:\'",.<>\/\\|`~]', password):
            return jsonify({"error": "Mật khẩu phải từ 8 ký tự, gồm chữ hoa, chữ thường và ký tự đặc biệt"}), 400

        if User.query.filter_by(username=username).first():
            return jsonify({"error": "Username đã tồn tại"}), 400

        if User.query.filter_by(email=email).first():
            return jsonify({"error": "Email đã tồn tại"}), 400

        user = User(username=username, email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        return jsonify({"message": "Đăng ký thành công", "user_id": user.id}), 201

    # 2. Xử lý Form HTML (Flask-WTF)
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

            # Thông báo thành công và chuyển hướng về trang /login để người dùng đăng nhập lại
            flash("Đăng ký tài khoản thành công! Vui lòng đăng nhập để tiếp tục.", "success")
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash(f"Lỗi khi tạo tài khoản: {str(e)}", "error")
            return render_template('auth/register.html', form=form), 500

    return render_template('auth/register.html', form=form), 400 if form.errors else 200

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Đăng nhập tài khoản người dùng."""
    if request.method == 'GET':
        if current_user.is_authenticated:
            return redirect(url_for('locations.feed'))
        form = LoginForm()
        return render_template('auth/login.html', form=form)

    # 1. Nếu client gửi JSON (API / Automation tests)
    if request.is_json:
        data = request.get_json() or {}
        username = data.get('username')
        password = data.get('password')

        user = User.query.filter(
            (User.username == username) | (User.email == username)
        ).first()

        if not user or not user.check_password(password):
            return jsonify({"error": "Sai username hoặc password"}), 401

        login_user(user)
        return jsonify({"message": "Đăng nhập thành công", "username": user.username})

    # 2. Xử lý Form HTML (Flask-WTF)
    form = LoginForm()
    if form.validate_on_submit():
        login_val = form.username.data.strip()
        password = form.password.data

        user = User.query.filter(
            (User.username == login_val) | (User.email == login_val.lower())
        ).first()

        if not user or not user.check_password(password):
            flash("Tên đăng nhập hoặc mật khẩu không chính xác.", "error")
            return render_template('auth/login.html', form=form), 401

        login_user(user, remember=form.remember_me.data)
        flash(f"Chào mừng trở lại, {user.username}!", "success")

        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)
        return redirect(url_for('locations.feed'))

    return render_template('auth/login.html', form=form), 400 if form.errors else 200

@auth_bp.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    """Đăng xuất người dùng."""
    logout_user()
    if request.accept_mimetypes.accept_html and not request.is_json:
        flash("Bạn đã đăng xuất tài khoản an toàn.", "info")
        return redirect(url_for('auth.login'))
    return jsonify({"message": "Đăng xuất thành công"})

@auth_bp.route('/profile', methods=['GET'])
@auth_bp.route('/profile/<username>', methods=['GET'])
@login_required
def profile(username=None):
    """Trang cá nhân của chính mình hoặc người dùng khác."""
    if username:
        profile_user = User.query.filter_by(username=username).first_or_404()
    else:
        profile_user = current_user

    # Thống kê số lượng
    posts_count = Post.query.filter_by(user_id=profile_user.id).count()
    followers_count = Follow.query.filter_by(followed_id=profile_user.id).count()
    following_count = Follow.query.filter_by(follower_id=profile_user.id).count()
    is_following = bool(
        Follow.query.filter_by(follower_id=current_user.id, followed_id=profile_user.id).first()
    ) if current_user.id != profile_user.id else False

    # Danh sách bài viết của user
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

    # Danh sách bài viết đã lưu (chỉ hiện khi xem hồ sơ của chính mình)
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

@auth_bp.route("/follow/<int:user_id>", methods=["POST"])
@login_required
def follow(user_id):
    """Theo dõi người dùng khác."""
    if current_user.id == user_id:
        return jsonify({"error": "Không thể tự follow chính mình"}), 400

    existing = Follow.query.filter_by(
        follower_id=current_user.id, followed_id=user_id
    ).first()
    if existing:
        return jsonify({"error": "Đã follow rồi"}), 400

    f = Follow(follower_id=current_user.id, followed_id=user_id)
    db.session.add(f)
    db.session.commit()
    return jsonify({"message": f"Đã follow user {user_id}"}), 201

@auth_bp.route("/unfollow/<int:user_id>", methods=["POST"])
@login_required
def unfollow(user_id):
    """Hủy theo dõi người dùng."""
    f = Follow.query.filter_by(
        follower_id=current_user.id, followed_id=user_id
    ).first()
    if not f:
        return jsonify({"error": "Chưa follow user này"}), 400

    db.session.delete(f)
    db.session.commit()
    return jsonify({"message": f"Đã unfollow user {user_id}"})
