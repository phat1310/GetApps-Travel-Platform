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
from app.locations.discovery import link_destination
from app.locations.maplinks import parse_map_links, attach_map_links, PLAN_LIMIT


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

        map_links, map_error = parse_map_links(data.get('map_links'), PLAN_LIMIT)
        if map_error:
            return jsonify({"error": map_error}), 400

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

        dest_loc = link_destination(destination)   # chuẩn hóa điểm đến -> Location để thống kê "Địa điểm nổi bật"
        plan = Itinerary(
            user_id=current_user.id,
            title=title,
            destination=destination,
            location_id=dest_loc.id if dest_loc else None,
            start_date=start_date,
            end_date=end_date,
            estimated_budget=float(data.get('estimated_budget') or 0.0),
            visibility=data.get('visibility', 'public'),
            description=data.get('description', '')
        )
        db.session.add(plan)
        db.session.flush()
        attach_map_links(map_links, itinerary=plan)

        # Tạo ngày 1 mặc định
        day1 = ItineraryDay(itinerary_id=plan.id, day_number=1, title="Ngày 1: Khởi hành")
        db.session.add(day1)
        db.session.commit()

        return jsonify({"message": "Tạo lịch trình thành công", "plan_id": plan.id}), 201

    # 2. Xử lý Form HTML (Flask-WTF)
    if form.validate_on_submit():
        # Địa chỉ Google Maps: kiểm tra ở server (tối đa 5, đúng tên miền Google Maps) TRƯỚC khi lưu file/DB
        map_links, map_error = parse_map_links(request.form.get('map_links'), PLAN_LIMIT)
        if map_error:
            flash(map_error, "danger")
            return render_template('plans/create.html', form=form), 400

        cover_url = save_uploaded_file(form.cover_image.data, 'plans')
        attach_url = save_uploaded_file(form.attachment_file.data, 'attachments')

        participants_cnt = form.participants_count.data or (int(request.form.get('participants_count')) if request.form.get('participants_count', '').isdigit() else None)
        trip_type = form.trip_type.data or request.form.get('trip_type')

        dest_loc = link_destination(form.destination.data)   # chuẩn hóa điểm đến -> Location
        plan = Itinerary(
            user_id=current_user.id,
            title=form.title.data.strip(),
            destination=form.destination.data.strip(),
            location_id=dest_loc.id if dest_loc else None,
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
        attach_map_links(map_links, itinerary=plan)

        # Tạo tự động các ngày dựa trên khoảng thời gian bắt đầu - kết thúc hoặc số ngày submit từ form
        submitted_days_count = 1
        raw_sub_days = request.form.get('submitted_days_count', '').strip()
        if raw_sub_days.isdigit():
            submitted_days_count = int(raw_sub_days)

        total_days = 1
        if plan.start_date and plan.end_date:
            delta = (plan.end_date - plan.start_date).days + 1
            total_days = max(delta, 1)

        total_days = max(total_days, submitted_days_count)

        day_map = {}
        for i in range(1, min(total_days + 1, 31)):  # Tối đa 30 ngày
            day = ItineraryDay(
                itinerary_id=plan.id,
                day_number=i,
                title=f"Ngày {i}: Khám phá {plan.destination}" if i > 1 else f"Ngày 1: Khởi hành & Đến {plan.destination}"
            )
            db.session.add(day)
            day_map[i] = day

        db.session.flush()

        first_day = day_map.get(1)

        # Lưu các chặng hoạt động theo từng ngày (Cấu trúc mới: Du lịch & Ăn uống)
        any_stops_added = False
        for i in range(1, total_days + 1):
            day_obj = day_map.get(i)
            if not day_obj:
                continue

            stop_names = request.form.getlist(f'stop_name_{i}[]')
            stop_types = request.form.getlist(f'stop_type_{i}[]')
            stop_times = request.form.getlist(f'stop_time_{i}[]')
            stop_locations = request.form.getlist(f'stop_location_{i}[]')
            stop_descs = request.form.getlist(f'stop_desc_{i}[]')
            stop_foods = request.form.getlist(f'stop_food_{i}[]')
            stop_open_hours = request.form.getlist(f'stop_open_hours_{i}[]')

            for sidx, sname in enumerate(stop_names):
                sname = (sname or '').strip()
                if not sname:
                    continue

                stype = stop_types[sidx] if sidx < len(stop_types) else 'travel'
                stime = stop_times[sidx] if sidx < len(stop_times) else ''
                sloc = stop_locations[sidx] if sidx < len(stop_locations) else ''
                sdesc = stop_descs[sidx] if sidx < len(stop_descs) else ''
                sfood = stop_foods[sidx] if sidx < len(stop_foods) else ''
                sopen = stop_open_hours[sidx] if sidx < len(stop_open_hours) else ''

                if stype == 'food':
                    act_name = f"Ăn uống: {sfood}" if sfood else f"Ghé quán {sname}"
                    note_parts = []
                    if sfood:
                        note_parts.append(f"Món gợi ý: {sfood}")
                    if sopen:
                        note_parts.append(f"Giờ mở cửa: {sopen}")
                    if sdesc:
                        note_parts.append(sdesc)
                    note_text = " • ".join(note_parts)
                else:
                    act_name = sname
                    note_text = sdesc

                is_link = sloc.startswith('http://') or sloc.startswith('https://')
                stop = ItineraryStop(
                    day_id=day_obj.id,
                    order_index=sidx + 1,
                    activity_name=act_name,
                    location_name=sname,
                    arrival_time=stime or None,
                    address=sloc or None,
                    location_link=sloc if is_link else None,
                    notes=note_text or None
                )
                db.session.add(stop)
                any_stops_added = True

        # Fallback tương thích ngược: nếu form gửi theo chuẩn cũ stop_activity_names[]
        if not any_stops_added:
            legacy_stop_names = request.form.getlist('stop_activity_names[]') or request.form.getlist('stop_activity_name')
            if not legacy_stop_names and request.form.get('stop_activity_name'):
                legacy_stop_names = [request.form.get('stop_activity_name')]

            if first_day and legacy_stop_names:
                for idx, sname in enumerate(legacy_stop_names):
                    sname = (sname or '').strip()
                    if sname:
                        stop = ItineraryStop(
                            day_id=first_day.id,
                            order_index=idx + 1,
                            activity_name=sname,
                            location_name=sname
                        )
                        db.session.add(stop)

        # Lưu danh sách nơi lưu trú (Hỗ trợ nhiều nơi lưu trú, chọn ngày & link GG Maps)
        hotel_names = request.form.getlist('hotel_name[]') or ([request.form.get('hotel_name')] if request.form.get('hotel_name') else [])
        lodging_prices = request.form.getlist('lodging_price[]')
        booking_links = request.form.getlist('booking_link[]')
        lodging_map_links = request.form.getlist('lodging_map_link[]')
        lodging_notes = request.form.getlist('lodging_note[]')
        lodging_days = request.form.getlist('lodging_day[]')

        for lidx, hname in enumerate(hotel_names):
            hname = (hname or '').strip()
            if not hname:
                continue

            lprice = lodging_prices[lidx] if lidx < len(lodging_prices) else ''
            lblink = booking_links[lidx] if lidx < len(booking_links) else ''
            lmap = lodging_map_links[lidx] if lidx < len(lodging_map_links) else ''
            lnote = lodging_notes[lidx] if lidx < len(lodging_notes) else ''
            lday_val = lodging_days[lidx] if lidx < len(lodging_days) else '1'

            price_night = 0.0
            if lprice:
                raw_price = str(lprice).replace('.', '').replace(',', '').replace('đ', '').replace(' ', '').strip()
                if raw_price.isdigit():
                    price_night = float(raw_price)

            target_day_id = None
            if lday_val and lday_val.isdigit() and int(lday_val) in day_map:
                target_day_id = day_map[int(lday_val)].id
            elif first_day:
                target_day_id = first_day.id

            lodging = ItineraryLodging(
                itinerary_id=plan.id,
                day_id=target_day_id,
                hotel_name=hname,
                price_per_night=price_night,
                booking_link=lblink.strip() if lblink else None,
                address=lmap.strip() if lmap else None,
                note=lnote.strip() if lnote else None
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
        dest_loc = link_destination(plan.destination)
        plan.location_id = dest_loc.id if dest_loc else None
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
