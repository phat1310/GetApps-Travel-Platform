"""Routes PLANS — Xử lý nghiệp vụ phân hệ Lịch trình chuyến đi (Itinerary / Plan).
Hỗ trợ cả giao diện HTML Jinja2 lẫn RESTful JSON API.
"""
import os
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import render_template, redirect, url_for, flash, request, jsonify, abort, current_app
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Itinerary, Plan, ItineraryDay, ItineraryStop, ItineraryLodging, User
from app.plans import plans_bp
from app.plans.forms import PlanCreateForm, PlanDayForm, PlanStopForm


def save_uploaded_file(file_storage, subfolder):
    """Lưu file tải lên an toàn với UUID và trả về đường dẫn tĩnh."""
    if not file_storage or not file_storage.filename:
        return None
    filename = secure_filename(file_storage.filename)
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    unique_filename = f"{uuid.uuid4().hex[:12]}_{filename}" if filename else f"{uuid.uuid4().hex}.{ext}"

    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', subfolder)
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, unique_filename)
    file_storage.save(file_path)

    return f"static/uploads/{subfolder}/{unique_filename}"


@plans_bp.route('', methods=['GET'])
@plans_bp.route('/', methods=['GET'])
def index():
    """Trang chủ Lịch trình — Khám phá hành trình cộng đồng & xem lịch trình cá nhân."""
    tab = request.args.get('tab', 'community')
    destination = request.args.get('destination', '').strip()
    sort = request.args.get('sort', 'newest')

    query = Itinerary.query

    # Lọc theo Tab
    if tab == 'my_plans':
        if not current_user.is_authenticated:
            flash("Vui lòng đăng nhập để xem lịch trình của bạn.", "info")
            return redirect(url_for('auth.login'))
        query = query.filter_by(user_id=current_user.id)
    else:
        # Tab Khám phá cộng đồng: chỉ hiển thị lịch trình công khai (public)
        query = query.filter_by(visibility='public')

    # Lọc theo điểm đến
    if destination:
        query = query.filter(Itinerary.destination.ilike(f"%{destination}%"))

    # Sắp xếp
    if sort == 'budget_low':
        query = query.order_by(Itinerary.estimated_budget.asc())
    elif sort == 'budget_high':
        query = query.order_by(Itinerary.estimated_budget.desc())
    else:
        query = query.order_by(Itinerary.created_at.desc())

    plans = query.all()

    # Thống kê điểm đến nổi bật
    destinations_suggest = ["Đà Lạt", "Phú Quốc", "Hà Giang", "Đà Nẵng", "Nha Trang", "Sapa"]

    # Phản hồi JSON nếu client yêu cầu
    if request.is_json or request.headers.get('Accept') == 'application/json':
        return jsonify({
            "plans": [p.to_dict() for p in plans],
            "count": len(plans)
        }), 200

    return render_template(
        'plans/index.html',
        plans=plans,
        active_tab=tab,
        destination=destination,
        sort=sort,
        destinations_suggest=destinations_suggest
    )


@plans_bp.route('/my-plans', methods=['GET'])
def my_plans():
    """Chuyển hướng hoặc xem thẳng tab Lịch trình của tôi."""
    if not current_user.is_authenticated:
        flash("Vui lòng đăng nhập để xem lịch trình của bạn.", "info")
        return redirect(url_for('auth.login'))
    return redirect(url_for('plans.index', tab='my_plans'))


@plans_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Tạo lịch trình du lịch mới."""
    form = PlanCreateForm()

    # 1. API JSON tạo lịch trình
    if request.is_json:
        data = request.get_json() or {}
        title = (data.get('title') or '').strip()
        destination = (data.get('destination') or '').strip()

        if not title or not destination:
            return jsonify({"error": "Thiếu tiêu đề hoặc điểm đến của lịch trình"}), 400

        start_date = None
        if data.get('start_date'):
            try:
                start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
            except ValueError:
                pass

        end_date = None
        if data.get('end_date'):
            try:
                end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
            except ValueError:
                pass

        plan = Itinerary(
            user_id=current_user.id,
            title=title,
            destination=destination,
            start_date=start_date,
            end_date=end_date,
            estimated_budget=float(data.get('estimated_budget') or 0.0),
            visibility=data.get('visibility', 'public'),
            description=data.get('description', '')
        )
        db.session.add(plan)
        db.session.flush()

        # Tạo ngày 1 mặc định
        day1 = ItineraryDay(itinerary_id=plan.id, day_number=1, title="Ngày 1: Khởi hành")
        db.session.add(day1)
        db.session.commit()

        return jsonify({"message": "Tạo lịch trình thành công", "plan_id": plan.id}), 201

    # 2. Xử lý Form HTML (Flask-WTF)
    if form.validate_on_submit():
        cover_url = save_uploaded_file(form.cover_image.data, 'plans')
        attach_url = save_uploaded_file(form.attachment_file.data, 'attachments')

        participants_cnt = form.participants_count.data or (int(request.form.get('participants_count')) if request.form.get('participants_count', '').isdigit() else None)
        trip_type = form.trip_type.data or request.form.get('trip_type')

        plan = Itinerary(
            user_id=current_user.id,
            title=form.title.data.strip(),
            destination=form.destination.data.strip(),
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            estimated_budget=form.estimated_budget.data or 0.0,
            visibility=form.visibility.data,
            cover_image=cover_url,
            attachment_file=attach_url,
            description=form.description.data,
            trip_type=trip_type,
            participants_count=participants_cnt
        )
        db.session.add(plan)
        db.session.flush()

        # Tạo tự động các ngày dựa trên khoảng thời gian bắt đầu - kết thúc
        total_days = 1
        if plan.start_date and plan.end_date:
            delta = (plan.end_date - plan.start_date).days + 1
            total_days = max(delta, 1)

        first_day = None
        for i in range(1, min(total_days + 1, 15)):  # Tối đa 14 ngày tạo sẵn
            day = ItineraryDay(
                itinerary_id=plan.id,
                day_number=i,
                title=f"Ngày {i}: Khám phá {plan.destination}" if i > 1 else f"Ngày 1: Khởi hành & Đến {plan.destination}"
            )
            db.session.add(day)
            if i == 1:
                first_day = day

        db.session.flush()

        # Lưu các chặng hoạt động nếu có nhập
        stop_names = request.form.getlist('stop_activity_names[]') or request.form.getlist('stop_activity_name')
        if not stop_names and request.form.get('stop_activity_name'):
            stop_names = [request.form.get('stop_activity_name')]

        if first_day and stop_names:
            for idx, sname in enumerate(stop_names):
                sname = sname.strip()
                if sname:
                    stop = ItineraryStop(
                        day_id=first_day.id,
                        order_index=idx + 1,
                        activity_name=sname,
                        location_name=sname
                    )
                    db.session.add(stop)

        # Lưu nơi lưu trú nếu có nhập
        hotel_name = request.form.get('hotel_name', '').strip()
        if hotel_name:
            price_night = 0.0
            raw_price = request.form.get('lodging_price', '').replace('.', '').replace(',', '').strip()
            if raw_price.isdigit():
                price_night = float(raw_price)

            lodging = ItineraryLodging(
                itinerary_id=plan.id,
                day_id=first_day.id if first_day else None,
                hotel_name=hotel_name,
                price_per_night=price_night,
                booking_link=request.form.get('booking_link', '').strip(),
                note=request.form.get('lodging_note', '').strip()
            )
            db.session.add(lodging)

        db.session.commit()
        flash(f"Đã tạo thành công lịch trình '{plan.title}'! Hãy thêm các điểm đến chi tiết.", "success")
        return redirect(url_for('plans.detail', plan_id=plan.id))

    return render_template('plans/create.html', form=form)


@plans_bp.route('/<int:plan_id>', methods=['GET'])
def detail(plan_id):
    """Xem chi tiết lịch trình và timeline từng ngày."""
    plan = Itinerary.query.get_or_404(plan_id)

    # Kiểm tra quyền xem riêng tư
    if plan.visibility == 'private':
        if not current_user.is_authenticated or current_user.id != plan.user_id:
            flash("Lịch trình này ở chế độ riêng tư của tác giả.", "warning")
            return redirect(url_for('plans.index'))

    # JSON API response
    if request.is_json or request.headers.get('Accept') == 'application/json':
        return jsonify(plan.to_dict()), 200

    day_form = PlanDayForm()
    stop_form = PlanStopForm()

    return render_template(
        'plans/detail.html',
        plan=plan,
        day_form=day_form,
        stop_form=stop_form,
        is_owner=(current_user.is_authenticated and current_user.id == plan.user_id)
    )


@plans_bp.route('/<int:plan_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(plan_id):
    """Chỉnh sửa thông tin lịch trình."""
    plan = Itinerary.query.get_or_404(plan_id)
    if plan.user_id != current_user.id:
        abort(403)

    form = PlanCreateForm(obj=plan)

    if form.validate_on_submit():
        plan.title = form.title.data.strip()
        plan.destination = form.destination.data.strip()
        plan.start_date = form.start_date.data
        plan.end_date = form.end_date.data
        plan.estimated_budget = form.estimated_budget.data or 0.0
        plan.visibility = form.visibility.data
        plan.description = form.description.data

        if form.cover_image.data:
            new_cover = save_uploaded_file(form.cover_image.data, 'plans')
            if new_cover:
                plan.cover_image = new_cover

        if form.attachment_file.data:
            new_attach = save_uploaded_file(form.attachment_file.data, 'attachments')
            if new_attach:
                plan.attachment_file = new_attach

        db.session.commit()
        flash("Đã cập nhật lịch trình thành công!", "success")
        return redirect(url_for('plans.detail', plan_id=plan.id))

    return render_template('plans/edit.html', form=form, plan=plan)


@plans_bp.route('/<int:plan_id>/delete', methods=['POST'])
@login_required
def delete(plan_id):
    """Xóa lịch trình du lịch."""
    plan = Itinerary.query.get_or_404(plan_id)
    if plan.user_id != current_user.id:
        abort(403)

    title = plan.title
    db.session.delete(plan)
    db.session.commit()

    if request.is_json:
        return jsonify({"message": f"Đã xóa lịch trình '{title}'"}), 200

    flash(f"Đã xóa lịch trình '{title}'.", "info")
    return redirect(url_for('plans.index'))


@plans_bp.route('/<int:plan_id>/days/add', methods=['POST'])
@login_required
def add_day(plan_id):
    """Thêm một ngày mới vào hành trình."""
    plan = Itinerary.query.get_or_404(plan_id)
    if plan.user_id != current_user.id:
        abort(403)

    form = PlanDayForm()
    next_day_num = len(plan.days) + 1
    title = form.title.data.strip() if form.title.data else f"Ngày {next_day_num}"
    note = form.note.data

    day = ItineraryDay(
        itinerary_id=plan.id,
        day_number=next_day_num,
        title=title,
        note=note
    )
    db.session.add(day)
    db.session.commit()

    if request.is_json:
        return jsonify(day.to_dict()), 201

    flash(f"Đã thêm {day.title} vào hành trình!", "success")
    return redirect(url_for('plans.detail', plan_id=plan.id))


@plans_bp.route('/days/<int:day_id>/stops/add', methods=['POST'])
@login_required
def add_stop(day_id):
    """Thêm điểm dừng chân vào một ngày."""
    day = ItineraryDay.query.get_or_404(day_id)
    plan = day.itinerary
    if plan.user_id != current_user.id:
        abort(403)

    form = PlanStopForm()
    if form.validate_on_submit() or request.is_json:
        data = request.get_json() if request.is_json else {}
        loc_name = data.get('location_name') or form.location_name.data
        arr_time = data.get('arrival_time') or form.arrival_time.data
        trans = data.get('transportation') or form.transportation.data
        cost = float(data.get('estimated_cost') or form.estimated_cost.data or 0.0)
        address = data.get('address') or form.address.data
        notes = data.get('notes') or form.notes.data

        stop = ItineraryStop(
            day_id=day.id,
            order_index=len(day.stops) + 1,
            location_name=loc_name.strip(),
            address=address,
            arrival_time=arr_time,
            transportation=trans,
            estimated_cost=cost,
            notes=notes
        )
        db.session.add(stop)
        db.session.commit()

        if request.is_json:
            return jsonify(stop.to_dict()), 201

        flash(f"Đã thêm điểm đến '{stop.location_name}' vào Ngày {day.day_number}!", "success")
    else:
        flash("Vui lòng kiểm tra lại thông tin điểm đến.", "error")

    return redirect(url_for('plans.detail', plan_id=plan.id))


@plans_bp.route('/stops/<int:stop_id>/delete', methods=['POST'])
@login_required
def delete_stop(stop_id):
    """Xóa một điểm dừng chân."""
    stop = ItineraryStop.query.get_or_404(stop_id)
    plan = stop.day.itinerary
    if plan.user_id != current_user.id:
        abort(403)

    db.session.delete(stop)
    db.session.commit()

    if request.is_json:
        return jsonify({"message": "Đã xóa điểm dừng"}), 200

    flash("Đã xóa điểm dừng.", "info")
    return redirect(url_for('plans.detail', plan_id=plan.id))
