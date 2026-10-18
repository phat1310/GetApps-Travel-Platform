"""Routes PLANS — Xử lý nghiệp vụ phân hệ Lịch trình chuyến đi (Itinerary / Plan).
Hỗ trợ cả giao diện HTML Jinja2 lẫn RESTful JSON API.
"""
import os
import re
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import render_template, redirect, url_for, flash, request, jsonify, abort, current_app, send_file
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Itinerary, Plan, ItineraryDay, ItineraryStop, ItineraryLodging, User, Location
from app.plans import plans_bp
from app.plans.forms import PlanCreateForm, PlanDayForm, PlanStopForm
from app.locations.places import resolve_location
from app.locations.discovery import link_destination, can_view_itinerary, viewer_follow_set, norm_text, clean_destination
from app.locations.maplinks import (parse_map_links, attach_map_links, PLAN_LIMIT, check_map_url, check_web_url,
                                    clean_text, looks_like_link)


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


# ---- Giới hạn + kiểm tra dữ liệu chặng / khách sạn gửi từ form "Đăng lịch trình" (kiểm tra Ở SERVER) ----
MAX_DAYS = 30
MAX_STOPS_PER_DAY = 15
MAX_LODGINGS = 10
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _at(lst, i):
    return lst[i] if i < len(lst) else ''


def _parse_trip_details(total_days):
    """Trả về (stops_by_day, lodgings, lỗi). Không ghi DB — chỉ làm sạch + kiểm tra.
    Mọi danh sách do client gửi đều bị chặn số lượng TRƯỚC khi lặp (tránh DoS bằng form khổng lồ)."""
    f = request.form
    stops_by_day = {}
    for d in range(1, total_days + 1):
        names = f.getlist(f'stop_name_{d}[]')[:MAX_STOPS_PER_DAY * 4]
        types = f.getlist(f'stop_type_{d}[]')
        times = f.getlist(f'stop_time_{d}[]')
        locs = f.getlist(f'stop_location_{d}[]')
        descs = f.getlist(f'stop_desc_{d}[]')
        foods = f.getlist(f'stop_food_{d}[]')
        opens = f.getlist(f'stop_open_hours_{d}[]')
        rows = []
        for i, raw_name in enumerate(names):
            name = clean_text(raw_name, 120)
            if not name:
                continue
            if len(rows) >= MAX_STOPS_PER_DAY:
                return None, None, f"Mỗi ngày tối đa {MAX_STOPS_PER_DAY} chặng (Ngày {d})."
            stype = 'food' if _at(types, i) == 'food' else 'travel'
            stime = clean_text(_at(times, i), 5)
            if stime and not _TIME_RE.match(stime):
                return None, None, f"Giờ ghé của \"{name}\" không hợp lệ (dạng HH:MM)."
            desc = clean_text(_at(descs, i), 500, keep_newlines=True)
            sfood = clean_text(_at(foods, i), 80)
            sopen = clean_text(_at(opens, i), 40)
            sloc = clean_text(_at(locs, i), 501)

            address = link = None
            if sloc and looks_like_link(sloc):
                link, err = check_map_url(sloc)
                if err:
                    return None, None, f"Chặng \"{name}\": {err}"
                address = link if len(link) <= 255 else None
            elif sloc:
                address = sloc[:255]

            if stype == 'food':
                activity = (f"Ăn uống: {sfood}" if sfood else f"Ghé quán {name}")[:200]
                parts = []
                if sfood:
                    parts.append(f"Món gợi ý: {sfood}")
                if sopen:
                    parts.append(f"Giờ mở cửa: {sopen}")
                if desc:
                    parts.append(desc)
                note = " • ".join(parts)
            else:
                activity, note = name, desc
            rows.append(dict(name=name, activity=activity, time=stime or None, address=address, link=link, note=note or None))
        stops_by_day[d] = rows

    lodgings = []
    h_names = f.getlist('hotel_name[]')[:MAX_LODGINGS * 4]
    if not h_names and f.get('hotel_name'):
        h_names = [f.get('hotel_name')]
    prices = f.getlist('lodging_price[]')
    books = f.getlist('booking_link[]')
    maps = f.getlist('lodging_map_link[]')
    notes = f.getlist('lodging_note[]')
    days = f.getlist('lodging_day[]')
    for i, raw_name in enumerate(h_names):
        hname = clean_text(raw_name, 200)
        if not hname:
            continue
        if len(lodgings) >= MAX_LODGINGS:
            return None, None, f"Tối đa {MAX_LODGINGS} nơi lưu trú cho mỗi lịch trình."
        price = 0.0
        raw_price = re.sub(r"[.,\sđ₫]|vnd|vnđ", "", clean_text(_at(prices, i), 40), flags=re.I)
        if raw_price.isdigit() and len(raw_price) <= 11:
            price = float(raw_price)

        braw = clean_text(_at(books, i), 501)
        booking_link = booking_ref = None
        if braw and looks_like_link(braw):
            booking_link, err = check_web_url(braw)
            if err:
                return None, None, f"Link đặt phòng của \"{hname}\": {err}"
            booking_ref = (re.sub(r"^https://", "", booking_link).split('/')[0])[:100]
        elif braw:
            booking_link = braw[:100]            # dạng chữ ("Đặt qua Agoda")
            booking_ref = braw[:100]

        mraw = clean_text(_at(maps, i), 501)
        map_link = None
        if mraw:
            map_link, err = check_map_url(mraw)
            if err:
                return None, None, f"Link Google Maps của \"{hname}\": {err}"

        dval = _at(days, i).strip()
        if dval.isdigit() and 1 <= int(dval) <= total_days:
            day_no = int(dval)
        elif dval == 'all':
            day_no = None                         # toàn bộ chuyến đi
        else:
            day_no = 1
        lodgings.append(dict(name=hname, price=price, booking_link=booking_link, booking_ref=booking_ref,
                             map_link=map_link, note=clean_text(_at(notes, i), 1000, keep_newlines=True) or None,
                             day_no=day_no))
    return stops_by_day, lodgings, None



# ---- Bộ lọc trang Lịch trình ----
PRICE_BUCKETS = [   # (mã, nhãn, từ (>=), đến (<))  — khoảng nửa mở nên 2 triệu chỉ thuộc nhóm "2–4 triệu"
    ("lt1", "Dưới 1 triệu", 0, 1_000_000),
    ("1-2", "1 – 2 triệu", 1_000_000, 2_000_000),
    ("2-4", "2 – 4 triệu", 2_000_000, 4_000_000),
    ("4-10", "4 – 10 triệu", 4_000_000, 10_000_000),
    ("gt10", "Trên 10 triệu", 10_000_000, None),
]
ATTACH_EXTS = {'pdf', 'docx', 'xlsx', 'pptx'}
DEFAULT_COVER = 'images/halong-cover.jpg'


def plan_budget(p):
    return float(p.estimated_budget or p.budget_estimate or 0)


def trip_code(p):
    """'2N1Đ - Đi phượt' -> '2N1Đ'."""
    return (p.trip_type or '').split(' - ')[0].strip()


def _price_bucket(code):
    return next((b for b in PRICE_BUCKETS if b[0] == code), None)


def _loc_match(q_norm, names):
    """Khớp tên địa điểm không phân biệt dấu/hoa thường/khoảng trắng; chịu gõ sai nhẹ (>= 4 ký tự)."""
    import difflib
    for n in names:
        if not n:
            continue
        if q_norm in n:
            return True
        if len(q_norm) >= 4 and difflib.SequenceMatcher(None, q_norm, n).ratio() >= 0.8:
            return True
    return False


def _counts(model_col, ids, model):
    from sqlalchemy import func
    if not ids:
        return {}
    return dict(db.session.query(model_col, func.count(model.id)).filter(model_col.in_(ids)).group_by(model_col).all())


def _social_state(ids, uid):
    """Số tim / bình luận / chia sẻ + tập lịch trình mình đã thả tim, đã lưu."""
    from app.models import Like, Comment, Share, SavedPost
    likes = _counts(Like.itinerary_id, ids, Like)
    cmts = _counts(Comment.itinerary_id, ids, Comment)
    shares = _counts(Share.itinerary_id, ids, Share)
    liked, saved = set(), set()
    if uid and ids:
        liked = {r.itinerary_id for r in Like.query.filter(Like.user_id == uid, Like.itinerary_id.in_(ids)).all()}
        saved = {r.itinerary_id for r in SavedPost.query.filter(SavedPost.user_id == uid, SavedPost.itinerary_id.in_(ids)).all()}
    return likes, cmts, shares, liked, saved


def _edited_at(p):
    """updated_at chỉ tính là 'đã cập nhật' khi lệch created_at > 60 giây (tránh lệch micro-giây lúc tạo)."""
    if p.updated_at and p.created_at and (p.updated_at - p.created_at).total_seconds() > 60:
        return p.updated_at
    return None


def make_plan_cards(plans, viewer_id, loc_name):
    """Dữ liệu thẻ lịch trình (trang Lịch trình + tab "Lịch trình" ở trang cá nhân dùng chung 1 mẫu thẻ).
    `plans` đã được lọc quyền xem ở nơi gọi; `loc_name(plan)` trả tên địa điểm hiển thị."""
    ids = [p.id for p in plans]
    likes, cmts, shares, liked, saved = _social_state(ids, viewer_id)
    cards = []
    for p in plans:
        cover = (p.cover_image or '').replace('static/', '', 1) or DEFAULT_COVER
        stops = sum(len(d.stops) for d in p.days)
        cards.append(dict(
            plan=p, cover=cover, location=loc_name(p), type=trip_code(p), budget=plan_budget(p),
            days=p.total_days, stops=stops, edited=_edited_at(p), is_mine=(p.id and p.user_id == viewer_id),
            private=((p.visibility or 'public') == 'private'),
            likes=likes.get(p.id, 0), comments=cmts.get(p.id, 0), shares=shares.get(p.id, 0),
            liked=(p.id in liked), has_attach=bool(p.attachment_file or p.attachments),
        ))
    return cards


def cards_for_profile(plans, viewer_id):
    """Thẻ lịch trình cho trang cá nhân (tự nạp tên địa điểm)."""
    ids = list({p.location_id for p in plans if p.location_id})
    locs = {l.id: l for l in Location.query.filter(Location.id.in_(ids or [0])).all()}

    def loc_name(p):
        l = locs.get(p.location_id)
        return l.name if l else clean_destination(p.destination)
    return make_plan_cards(plans, viewer_id, loc_name)


@plans_bp.route('', methods=['GET'])
@plans_bp.route('/', methods=['GET'])
def index():
    """Trang Lịch trình: 1 danh sách duy nhất (công khai + lịch trình riêng tư của mình), lọc giá / địa điểm / loại chuyến đi."""
    from app.models import Location
    price = request.args.get('price', '').strip()
    loc_id = request.args.get('loc', '').strip()
    ttype = request.args.get('type', '').strip()
    q = request.args.get('q', '').strip()[:160]
    kw = ' '.join(request.args.get('kw', '').split())[:100]   # từ khóa từ thanh "Tìm kiếm hành trình" ở top bar

    viewer_id = current_user.id if current_user.is_authenticated else None
    viewer_follow = viewer_follow_set(viewer_id)
    all_plans = Itinerary.query.order_by(Itinerary.created_at.desc(), Itinerary.id.desc()).all()
    visible = [p for p in all_plans if can_view_itinerary(p, viewer_id, viewer_follow)]

    locs = {l.id: l for l in Location.query.filter(Location.id.in_(list({p.location_id for p in visible if p.location_id}) or [0])).all()}
    parent_ids = {l.parent_id for l in locs.values() if l.parent_id and l.parent_id not in locs}
    if parent_ids:                                    # nạp thêm hàng tỉnh/thành cha để gộp số đếm theo tỉnh
        locs.update({l.id: l for l in Location.query.filter(Location.id.in_(list(parent_ids))).all()})

    def top_id(location_id):
        """Lọc theo tỉnh/thành thì gồm cả phường/xã con: quy mọi địa điểm về tỉnh/thành cha (nếu có)."""
        l = locs.get(location_id)
        return (l.parent_id or l.id) if l else None

    def loc_name(p):
        l = locs.get(p.location_id)
        return l.name if l else clean_destination(p.destination)

    # Danh sách để chọn trong 3 ô lọc (đếm trên toàn bộ lịch trình xem được)
    loc_count, type_count = {}, {}
    for p in visible:
        t_id = top_id(p.location_id)
        if t_id in locs:
            loc_count[t_id] = loc_count.get(t_id, 0) + 1
        t = trip_code(p)
        if t:
            type_count[t] = type_count.get(t, 0) + 1
    loc_options = sorted(({"id": i, "name": locs[i].name, "n": n} for i, n in loc_count.items()),
                         key=lambda r: (-r["n"], r["name"].lower()))
    type_options = sorted(({"name": t, "n": n} for t, n in type_count.items()), key=lambda r: (-r["n"], r["name"].lower()))

    # Áp dụng bộ lọc (AND)
    plans = visible
    bucket = _price_bucket(price)
    if bucket:
        lo, hi = bucket[2], bucket[3]
        plans = [p for p in plans if plan_budget(p) >= lo and (hi is None or plan_budget(p) < hi)]
    if any(str(o["id"]) == loc_id for o in loc_options):      # chỉ nhận địa điểm có thật trong danh sách
        plans = [p for p in plans if top_id(p.location_id) == int(loc_id)]
    if ttype:
        plans = [p for p in plans if trip_code(p) == ttype]
    if q:
        qn = norm_text(q)
        if qn:
            from app.locations.places import find_province
            q_prov = find_province(q)[0]               # "Đà Lạt"/"Bà Rịa"/"Sài Gòn" -> tỉnh/thành hiện nay
            q_code = q_prov["code"] if q_prov else None

            def _in_prov(p):
                t = locs.get(top_id(p.location_id))
                return bool(q_code and t is not None and t.code == q_code)
            plans = [p for p in plans if _in_prov(p) or _loc_match(qn, [norm_text(loc_name(p)), norm_text(p.destination)])]

    if kw:
        # Mọi từ khóa phải xuất hiện (không phân biệt hoa/thường, dấu) trong tên / điểm đến / mô tả / loại chuyến đi.
        # Lọc trong bộ nhớ trên danh sách ĐÃ qua can_view_itinerary -> không SQL tự ghép, không lộ lịch trình riêng tư.
        tokens = [t for t in (norm_text(w) for w in kw.split()) if t]   # tách TRƯỚC rồi mới chuẩn hóa (norm_text bỏ hết khoảng trắng)

        def _hay(p):
            return norm_text(' '.join([p.title or '', p.destination or '', loc_name(p) or '', p.description or '', p.trip_type or '']))
        plans = [p for p in plans if tokens and all(t in _hay(p) for t in tokens)]

    if request.is_json or request.headers.get('Accept') == 'application/json':
        return jsonify({"plans": [p.to_dict() for p in plans], "count": len(plans)}), 200

    cards = make_plan_cards(plans, viewer_id, loc_name)

    price_label = bucket[1] if bucket else ''
    loc_label = next((o["name"] for o in loc_options if str(o["id"]) == loc_id), '')
    ttype_ok = ttype if any(o["name"] == ttype for o in type_options) else ''
    cur = {'price': price if bucket else '', 'loc': loc_id if loc_label else '', 'type': ttype_ok, 'q': q, 'kw': kw}

    def href(**over):
        """URL trang Lịch trình với bộ lọc hiện tại, ghi đè bằng `over` (giá trị rỗng/None = bỏ lọc đó)."""
        args = dict(cur)
        args.update(over)
        return url_for('plans.index', **{k: v for k, v in args.items() if v})

    return render_template(
        'plans/index.html', cards=cards, total=len(visible),
        price=price if bucket else '', price_label=price_label, price_buckets=PRICE_BUCKETS,
        loc=loc_id if loc_label else '', loc_label=loc_label, loc_options=loc_options,
        ttype=ttype_ok, type_options=type_options, href=href,
        q=q, kw=kw, any_filter=bool(bucket or loc_label or ttype_ok or q or kw),
    )


@plans_bp.route('/my-plans', methods=['GET'])
def my_plans():
    """Đã gộp 'Của tôi' vào danh sách chung — giữ đường dẫn cũ để không hỏng liên kết."""
    return redirect(url_for('plans.index'))


def _viewable_or_404(plan_id):
    plan = db.session.get(Itinerary, plan_id)
    viewer_id = current_user.id if current_user.is_authenticated else None
    if plan is None or not can_view_itinerary(plan, viewer_id, viewer_follow_set(viewer_id)):
        abort(404)                       # không lộ là có tồn tại
    return plan


def _attachment_path(plan):
    """Đường dẫn tuyệt đối tệp đính kèm nếu hợp lệ (nằm trong static/uploads, đúng đuôi cho phép), ngược lại None."""
    rel = plan.attachment_file or (plan.attachments[0].file_path if plan.attachments else None)
    if not rel:
        return None
    rel = rel.replace('\\', '/').lstrip('/')
    if rel.startswith('static/'):
        rel = rel[len('static/'):]
    root = os.path.realpath(os.path.join(current_app.root_path, 'static', 'uploads'))
    full = os.path.realpath(os.path.join(current_app.root_path, 'static', rel))
    if not full.startswith(root + os.sep) or not os.path.isfile(full):
        return None
    if full.rsplit('.', 1)[-1].lower() not in ATTACH_EXTS:
        return None
    return full


@plans_bp.route('/<int:plan_id>/panel', methods=['GET'])
def panel(plan_id):
    """Nội dung HTML của cửa sổ chi tiết (modal) — cùng quyền xem với trang chi tiết."""
    plan = _viewable_or_404(plan_id)
    uid = current_user.id if current_user.is_authenticated else None
    likes, cmts, shares, liked, saved = _social_state([plan.id], uid)
    stops_total = sum(len(d.stops) for d in plan.days)
    from app.models import Comment
    from app.mentions import render_mentions
    rows = Comment.query.filter_by(itinerary_id=plan.id).order_by(Comment.created_at.asc()).limit(200).all()
    users = {u.id: u for u in User.query.filter(User.id.in_(list({c.user_id for c in rows}) or [0])).all()}
    comment_list = [dict(user=users.get(c.user_id), html=render_mentions(c.content), at=c.created_at) for c in rows if users.get(c.user_id)]
    return render_template(
        'plans/_panel.html', plan=plan, comment_list=comment_list, is_owner=(uid == plan.user_id),
        cover=(plan.cover_image or '').replace('static/', '', 1) or DEFAULT_COVER,
        type_code=trip_code(plan), budget=plan_budget(plan), stops_total=stops_total, edited=_edited_at(plan),
        likes=likes.get(plan.id, 0), comments=cmts.get(plan.id, 0), shares=shares.get(plan.id, 0),
        liked=(plan.id in liked), saved=(plan.id in saved), has_attach=bool(_attachment_path(plan)),
        private=((plan.visibility or 'public') == 'private'),
    )


@plans_bp.route('/<int:plan_id>/attachment', methods=['GET'])
def attachment(plan_id):
    """Tải TỆP ĐÍNH KÈM mà người đăng đã up (chỉ người có quyền xem lịch trình)."""
    plan = _viewable_or_404(plan_id)
    full = _attachment_path(plan)
    if not full:
        abort(404)
    name = re.sub(r'^[0-9a-f]{12}_', '', os.path.basename(full)) or os.path.basename(full)
    resp = send_file(full, as_attachment=True, download_name=name, max_age=0)
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    return resp


@plans_bp.route('/<int:plan_id>/repost', methods=['POST'])
@login_required
def repost(plan_id):
    """Đăng lại (Repost) lịch trình của người khác: ghi nhận 1 lượt chia sẻ + báo cho chủ lịch trình."""
    from app.models import Share
    from app.notifications import notify
    plan = _viewable_or_404(plan_id)
    if plan.user_id == current_user.id:
        return jsonify({"error": "Bạn không thể đăng lại lịch trình của chính mình"}), 400
    if Share.query.filter_by(user_id=current_user.id, itinerary_id=plan.id).first():
        return jsonify({"message": "Bạn đã đăng lại lịch trình này rồi", "reposted": True, "already": True})
    db.session.add(Share(user_id=current_user.id, itinerary_id=plan.id, share_type="repost"))
    notify(plan.user_id, current_user.id, "share", itinerary_id=plan.id)
    db.session.commit()
    return jsonify({"message": "Đã đăng lại lịch trình", "reposted": True, "already": False})


def _required_error(title, destination, trip_type, start, end, participants, budget):
    """Các trường BẮT BUỘC khi đăng lịch trình (kiểm tra ở server, không tin client). Trả về câu lỗi hoặc None."""
    if not (title or '').strip():
        return "Vui lòng nhập tên chuyến đi."
    if not clean_destination(destination):
        return "Vui lòng nhập địa điểm."
    if not (trip_type or '').strip():
        return "Vui lòng chọn loại chuyến đi (2N1Đ, 3N2Đ, 1 tuần...)."
    if not start or not end:
        return "Vui lòng chọn ngày bắt đầu và ngày kết thúc."
    if end < start:
        return "Ngày kết thúc phải sau ngày bắt đầu."
    if not participants or participants < 1 or participants > 1000:
        return "Vui lòng nhập số người tham gia (từ 1 trở lên)."
    if not budget or budget <= 0:
        return "Vui lòng nhập dự toán ngân sách."
    return None


@plans_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Tạo lịch trình du lịch mới."""
    if request.method == 'GET':
        # Trang riêng đã bỏ: dùng hộp "Tạo mới" (nút máy bay) ở mọi trang, mở sẵn tab Đăng lịch trình
        return redirect(url_for('locations.feed', compose='plan'))
    form = PlanCreateForm()

    # 1. API JSON tạo lịch trình
    if request.is_json:
        data = request.get_json() or {}
        title = (data.get('title') or '').strip()
        destination = (data.get('destination') or '').strip()

        if not title or not destination:
            return jsonify({"error": "Thiếu tiêu đề hoặc điểm đến của lịch trình"}), 400
        try:
            _sd = datetime.strptime(data['start_date'], '%Y-%m-%d').date() if data.get('start_date') else None
            _ed = datetime.strptime(data['end_date'], '%Y-%m-%d').date() if data.get('end_date') else None
            _pc = int(data.get('participants_count') or 0)
            _bg = float(data.get('estimated_budget') or 0)
        except (ValueError, TypeError):
            return jsonify({"error": "Dữ liệu ngày / số người / ngân sách không hợp lệ"}), 400
        req_err = _required_error(title, destination, data.get('trip_type'), _sd, _ed, _pc, _bg)
        if req_err:
            return jsonify({"error": req_err}), 400

        map_links, map_error = parse_map_links(data.get('map_links'), PLAN_LIMIT)
        if map_error:
            return jsonify({"error": map_error}), 400

        dest_loc, dest_err = resolve_location(destination, data.get('destination_code'))
        if dest_err or not dest_loc:
            return jsonify({"error": dest_err or "Vui lòng chọn địa điểm."}), 400
        destination = dest_loc.name

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
            location_id=dest_loc.id if dest_loc else None,
            start_date=start_date,
            end_date=end_date,
            estimated_budget=float(data.get('estimated_budget') or 0.0),
            visibility=data.get('visibility', 'public') if data.get('visibility') in ('public', 'private') else 'public',
            description=data.get('description', ''),
            trip_type=clean_text(data.get('trip_type'), 50),
            participants_count=_pc
        )
        db.session.add(plan)
        db.session.flush()
        attach_map_links(map_links, itinerary=plan, locations=[dest_loc])

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

        # Số ngày: theo khoảng ngày hoặc số ngày form gửi lên — luôn bị chặn ở MAX_DAYS (chống form độc hại)
        raw_sub_days = request.form.get('submitted_days_count', '').strip()
        submitted_days_count = int(raw_sub_days[:6]) if raw_sub_days.isdigit() else 1
        total_days = 1
        if form.start_date.data and form.end_date.data:
            total_days = max((form.end_date.data - form.start_date.data).days + 1, 1)
        total_days = min(max(total_days, submitted_days_count, 1), MAX_DAYS)

        stops_by_day, lodging_rows, detail_error = _parse_trip_details(total_days)
        if detail_error:
            flash(detail_error, "danger")
            return render_template('plans/create.html', form=form), 400

        # Bắt buộc: mọi trường trừ tệp đính kèm; ảnh bìa; mỗi ngày >= 1 chặng (TRỪ khi đã đính kèm tệp lịch trình:
        # lúc đó được bỏ trống chặng và nơi lưu trú, người xem đọc chi tiết trong tệp)
        has_attach = bool(form.attachment_file.data and getattr(form.attachment_file.data, 'filename', ''))
        pc_raw = form.participants_count.data or (int(request.form.get('participants_count')) if request.form.get('participants_count', '').isdigit() else None)
        req_err = _required_error(form.title.data, form.destination.data, form.trip_type.data or request.form.get('trip_type'),
                                  form.start_date.data, form.end_date.data, pc_raw, form.estimated_budget.data)
        if not req_err and not (form.cover_image.data and getattr(form.cover_image.data, 'filename', '')):
            req_err = "Vui lòng chọn ảnh bìa cho chuyến đi."
        if not req_err and not has_attach:
            for d in range(1, total_days + 1):
                if not stops_by_day.get(d):
                    req_err = f"Ngày {d} cần có ít nhất 1 điểm ghé."
                    break
        dest_loc = None
        if not req_err:
            dest_loc, req_err = resolve_location(form.destination.data, request.form.get('destination_code'))
            if not req_err and not dest_loc:
                req_err = "Vui lòng chọn địa điểm."
        if req_err:
            flash(req_err, "danger")
            return render_template('plans/create.html', form=form), 400

        cover_url = save_uploaded_file(form.cover_image.data, 'plans')
        attach_url = save_uploaded_file(form.attachment_file.data, 'attachments')

        participants_cnt = form.participants_count.data or (int(request.form.get('participants_count')) if request.form.get('participants_count', '').isdigit() else None)
        trip_type = form.trip_type.data or request.form.get('trip_type')

        plan = Itinerary(
            user_id=current_user.id,
            title=form.title.data.strip(),
            destination=dest_loc.name,
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
        attach_map_links(map_links, itinerary=plan, locations=[dest_loc])

        # Tạo các ngày (đã bị chặn tối đa MAX_DAYS ở trên)
        day_map = {}
        for i in range(1, total_days + 1):
            day = ItineraryDay(
                itinerary_id=plan.id,
                day_number=i,
                title=f"Ngày {i}: Khám phá {plan.destination}" if i > 1 else f"Ngày 1: Khởi hành & Đến {plan.destination}"
            )
            db.session.add(day)
            day_map[i] = day
        db.session.flush()
        first_day = day_map.get(1)

        # Lưu chặng Du lịch / Ăn uống theo từng ngày (dữ liệu đã được làm sạch + kiểm tra ở _parse_trip_details)
        any_stops_added = False
        for i in range(1, total_days + 1):
            for sidx, st in enumerate(stops_by_day.get(i, [])):
                db.session.add(ItineraryStop(
                    day_id=day_map[i].id,
                    order_index=sidx + 1,
                    activity_name=st['activity'],
                    location_name=st['name'],
                    arrival_time=st['time'],
                    address=st['address'],
                    location_link=st['link'],
                    notes=st['note'],
                ))
                any_stops_added = True

        # Tương thích ngược: form cũ gửi stop_activity_names[]
        if not any_stops_added and first_day:
            legacy = request.form.getlist('stop_activity_names[]')[:MAX_STOPS_PER_DAY] or (
                [request.form.get('stop_activity_name')] if request.form.get('stop_activity_name') else [])
            idx = 0
            for raw in legacy:
                nm = clean_text(raw, 120)
                if nm:
                    idx += 1
                    db.session.add(ItineraryStop(day_id=first_day.id, order_index=idx, activity_name=nm, location_name=nm))

        # Nơi lưu trú (nhiều nơi, chọn đêm ngày N hoặc "toàn bộ chuyến đi", link Google Maps)
        for lg in lodging_rows:
            db.session.add(ItineraryLodging(
                itinerary_id=plan.id,
                day_id=day_map[lg['day_no']].id if lg['day_no'] else None,
                hotel_name=lg['name'],
                price_per_night=lg['price'],
                booking_link=lg['booking_link'],
                booking_reference=lg['booking_ref'],
                map_link=lg['map_link'],
                note=lg['note'],
            ))

        db.session.commit()
        flash(f"Đã tạo thành công lịch trình '{plan.title}'! Hãy thêm các điểm đến chi tiết.", "success")
        return redirect(url_for('plans.detail', plan_id=plan.id))

    return render_template('plans/create.html', form=form)


@plans_bp.route('/<int:plan_id>', methods=['GET'])
def detail(plan_id):
    """Xem chi tiết lịch trình và timeline từng ngày."""
    plan = Itinerary.query.get_or_404(plan_id)

    # Quyền xem: riêng tư chỉ chủ; tài khoản kín cần follow. Không có quyền -> 404 (không lộ là có tồn tại)
    viewer_id = current_user.id if current_user.is_authenticated else None
    if not can_view_itinerary(plan, viewer_id, viewer_follow_set(viewer_id)):
        abort(404)

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
        keep = [db.session.get(Location, plan.location_id)] if plan.location_id else []
        dest_loc, dest_err = resolve_location(form.destination.data, request.form.get('destination_code'), keep)
        if dest_err or not dest_loc:
            flash(dest_err or "Vui lòng chọn địa điểm.", "danger")
            return render_template('plans/edit.html', form=form, plan=plan), 400
        plan.destination = dest_loc.name
        plan.location_id = dest_loc.id
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
    from app.deletion import delete_itinerary_cascade
    delete_itinerary_cascade(plan)

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
