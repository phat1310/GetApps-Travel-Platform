"""Test suite cho Phân hệ Lịch trình du lịch (Plans / Itinerary).
Bao gồm kiểm thử:
- Danh sách lịch trình cộng đồng & cá nhân (HTML & JSON)
- Tạo lịch trình (Form & JSON API)
- Quản lý Timeline: Thêm ngày, Thêm điểm đến (Stop), Xóa điểm đến
- Phân quyền riêng tư (Public / Private)
- Chỉnh sửa & Xóa lịch trình
"""
import io
import pytest
from datetime import date
from app.models import User, Itinerary, ItineraryDay, ItineraryStop
from app.extensions import db


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def cover():
    """Ảnh bìa giả (bắt buộc khi đăng lịch trình)."""
    return (io.BytesIO(PNG), "cover.png")


def login_user(client, username="testuser1", password="123456"):
    return client.post(
        "/login",
        json={
            "username": username,
            "password": password
        }
    )


def test_plans_index_get(client):
    """GET /plans hiển thị giao diện danh sách lịch trình 200 OK."""
    res = client.get("/plans")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Hiện chưa có lịch trình nào" in html     # chưa có lịch trình nào
    assert "Giá cả" in html and "Địa điểm" in html and "Loại chuyến đi" in html


def test_plans_index_json_api(client, users):
    """GET /plans với Accept: application/json trả về danh sách lịch trình rỗng hoặc có sẵn."""
    res = client.get("/plans", headers={"Accept": "application/json"})
    assert res.status_code == 200
    data = res.get_json()
    assert "plans" in data
    assert "count" in data


def test_plan_create_unauthenticated_redirect(client):
    """Người dùng chưa đăng nhập khi truy cập /plans/create bị chuyển hướng về /login."""
    res = client.get("/plans/create")
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]


def test_plan_create_form_post_success(client, users):
    """POST /plans/create qua HTML form tạo lịch trình thành công và tự động tạo Ngày 1."""
    login_user(client, "testuser1")

    res = client.post(
        "/plans/create",
        data={
            "title": "Chuyến đi săn mây Đà Lạt 3N2Đ",
            "destination": "Đà Lạt, Lâm Đồng",
            "start_date": "2026-11-10",
            "end_date": "2026-11-12",
            "estimated_budget": 3500000.0,
            "visibility": "public",
            "trip_type": "3N2Đ - Đi phượt",
            "participants_count": "2",
            "cover_image": cover(),
            "stop_name_1[]": ["Đồi chè Cầu Đất"],
            "stop_name_2[]": ["Thác Datanla"],
            "stop_name_3[]": ["Chợ Đà Lạt"],
            "description": "Lịch trình phượt khám phá Đà Lạt mùa đông."
        },
        headers={"Accept": "text/html"},
        content_type="multipart/form-data"
    )
    assert res.status_code == 302

    with client.application.app_context():
        plan = Itinerary.query.filter_by(title="Chuyến đi săn mây Đà Lạt 3N2Đ").first()
        assert plan is not None
        assert plan.destination == "Đà Lạt, Lâm Đồng"
        assert plan.total_days == 3
        assert len(plan.days) == 3


def test_plan_create_json_api(client, users):
    """POST /plans/create với JSON tạo lịch trình thành công 201 Created."""
    login_user(client, "testuser1")

    res = client.post(
        "/plans/create",
        json={
            "title": "Hành trình khám phá Đảo ngọc Phú Quốc",
            "destination": "Phú Quốc, Kiên Giang",
            "start_date": "2026-12-01",
            "end_date": "2026-12-04",
            "estimated_budget": 6000000.0,
            "visibility": "public",
            "trip_type": "3N2Đ",
            "participants_count": 4,
            "description": "Nghỉ dưỡng và lặn biển ngắm san hô."
        }
    )
    assert res.status_code == 201
    data = res.get_json()
    assert "plan_id" in data
    assert data["message"] == "Tạo lịch trình thành công"


def test_plan_detail_get(client, users):
    """GET /plans/<id> hiển thị chi tiết lịch trình và timeline."""
    login_user(client, "testuser1")

    # Tạo trước 1 plan
    with client.application.app_context():
        user = User.query.filter_by(username="testuser1").first()
        plan = Itinerary(
            user_id=user.id,
            title="Khám phá Phố cổ Hội An",
            destination="Hội An, Quảng Nam",
            estimated_budget=2000000.0,
            visibility="public"
        )
        db.session.add(plan)
        db.session.flush()

        day1 = ItineraryDay(itinerary_id=plan.id, day_number=1, title="Dạo quanh Phố cổ")
        db.session.add(day1)
        db.session.commit()
        plan_id = plan.id

    res = client.get(f"/plans/{plan_id}")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Khám phá Phố cổ Hội An" in html
    assert "Hội An, Quảng Nam" in html
    assert "Ngày 1" in html


def test_plan_add_day_and_stops(client, users):
    """Chủ sở hữu có thể thêm ngày mới và thêm điểm dừng chân vào hành trình."""
    login_user(client, "testuser1")

    with client.application.app_context():
        user = User.query.filter_by(username="testuser1").first()
        plan = Itinerary(
            user_id=user.id,
            title="Du hí Đà Nẵng",
            destination="Đà Nẵng",
            visibility="public"
        )
        db.session.add(plan)
        db.session.commit()
        plan_id = plan.id

    # 1. Thêm Ngày 1
    res_day = client.post(
        f"/plans/{plan_id}/days/add",
        data={"title": "Ngày 1: Cầu Rồng & Bán đảo Sơn Trà", "note": "Mang máy ảnh"},
        headers={"Accept": "text/html"}
    )
    assert res_day.status_code == 302

    with client.application.app_context():
        plan = Itinerary.query.get(plan_id)
        assert len(plan.days) == 1
        day1 = plan.days[0]
        day1_id = day1.id

    # 2. Thêm Điểm dừng vào Ngày 1
    res_stop = client.post(
        f"/plans/days/{day1_id}/stops/add",
        data={
            "location_name": "Cầu Rồng Đà Nẵng",
            "arrival_time": "18:30",
            "transportation": "Xe máy",
            "estimated_cost": 50000.0,
            "notes": "Xem rồng phun lửa lúc 21h cuối tuần"
        },
        headers={"Accept": "text/html"}
    )
    assert res_stop.status_code == 302

    with client.application.app_context():
        day1 = ItineraryDay.query.get(day1_id)
        assert len(day1.stops) == 1
        assert day1.stops[0].location_name == "Cầu Rồng Đà Nẵng"
        stop_id = day1.stops[0].id

    # 3. Xóa Điểm dừng
    res_del_stop = client.post(f"/plans/stops/{stop_id}/delete")
    assert res_del_stop.status_code == 302

    with client.application.app_context():
        day1 = ItineraryDay.query.get(day1_id)
        assert len(day1.stops) == 0


def test_plan_private_visibility_protection(client, users):
    """Lịch trình private không cho người dùng khác truy cập."""
    # Tạo plan riêng tư của testuser1
    with client.application.app_context():
        user1 = User.query.filter_by(username="testuser1").first()
        plan = Itinerary(
            user_id=user1.id,
            title="Kế hoạch bí mật",
            destination="Côn Đảo",
            visibility="private"
        )
        db.session.add(plan)
        db.session.commit()
        plan_id = plan.id

    # Khách vãng lai chưa login truy cập
    res_guest = client.get(f"/plans/{plan_id}")
    assert res_guest.status_code == 404   # riêng tư: không lộ là có tồn tại

    # Đăng nhập user2 truy cập
    login_user(client, "testuser2")
    res_user2 = client.get(f"/plans/{plan_id}")
    assert res_user2.status_code == 404

    # Đăng nhập chính chủ user1 truy cập -> thành công 200
    login_user(client, "testuser1")
    res_owner = client.get(f"/plans/{plan_id}")
    assert res_owner.status_code == 200
    assert "Kế hoạch bí mật" in res_owner.data.decode("utf-8")


def test_plan_delete_success(client, users):
    """Chủ sở hữu có thể xóa lịch trình của mình."""
    login_user(client, "testuser1")

    with client.application.app_context():
        user = User.query.filter_by(username="testuser1").first()
        plan = Itinerary(
            user_id=user.id,
            title="Lịch trình sắp bị xóa",
            destination="Vũng Tàu",
            visibility="public"
        )
        db.session.add(plan)
        db.session.commit()
        plan_id = plan.id

    res = client.post(f"/plans/{plan_id}/delete")
    assert res.status_code == 302
    assert "/plans" in res.headers["Location"]

    with client.application.app_context():
        assert Itinerary.query.get(plan_id) is None


def test_my_plans_redirect_anonymous(client):
    """/plans/my-plans đã gộp vào danh sách chung: luôn chuyển về /plans."""
    res = client.get("/plans/my-plans")
    assert res.status_code == 302
    assert "/plans" in res.headers["Location"] and "my-plans" not in res.headers["Location"]


def test_my_plans_redirect_authenticated(client, users):
    login_user(client, "testuser1")
    res = client.get("/plans/my-plans")
    assert res.status_code == 302
    assert "/plans" in res.headers["Location"] and "my-plans" not in res.headers["Location"]


def test_plan_create_multi_day_stops_and_lodgings(client, users):
    """POST /plans/create hỗ trợ tạo nhiều ngày, chặng Du lịch / Ăn uống và nhiều nơi lưu trú theo ngày."""
    login_user(client, "testuser1")

    res = client.post(
        "/plans/create",
        data={
            "title": "Đà Lạt 2N1Đ Săn Mây & Ẩm Thực",
            "destination": "Đà Lạt",
            "start_date": "2026-11-20",
            "end_date": "2026-11-21",
            "estimated_budget": 2500000.0,
            "visibility": "public",
            "submitted_days_count": "2",
            "trip_type": "2N1Đ - Nghỉ dưỡng",
            "participants_count": "2",
            "cover_image": cover(),
            # Chặng ngày 1: 1 du lịch, 1 ăn uống
            "stop_type_1[]": ["travel", "food"],
            "stop_name_1[]": ["Đồi chè Cầu Đất", "Lẩu gà lá é Tao Ngộ"],
            "stop_time_1[]": ["07:30", "12:00"],
            "stop_location_1[]": ["https://maps.app.goo.gl/sample1", "Đường 3/4 Đà Lạt"],
            "stop_desc_1[]": ["Săn mây sáng sớm", "Quán đông, nên tới sớm"],
            "stop_food_1[]": ["", "Lẩu gà lá é"],
            "stop_open_hours_1[]": ["", "09:00 - 21:00"],
            # Chặng ngày 2: 1 du lịch
            "stop_type_2[]": ["travel"],
            "stop_name_2[]": ["Thác Datanla"],
            "stop_time_2[]": ["09:00"],
            "stop_location_2[]": ["https://maps.app.goo.gl/sample2"],
            "stop_desc_2[]": ["Trải nghiệm máng trượt"],
            # Nơi lưu trú: 2 nơi lưu trú gán theo ngày
            "hotel_name[]": ["Làng Boho Homestay", "Khách sạn Colline"],
            "lodging_price[]": ["600000", "1500000"],
            "booking_link[]": ["Agoda", "Booking.com"],
            "lodging_map_link[]": ["https://maps.app.goo.gl/homestay", "https://maps.app.goo.gl/hotel"],
            "lodging_note[]": ["View thung lũng", "Gần chợ đêm"],
            "lodging_day[]": ["1", "2"]
        },
        headers={"Accept": "text/html"},
        content_type="multipart/form-data"
    )
    assert res.status_code == 302

    with client.application.app_context():
        plan = Itinerary.query.filter_by(title="Đà Lạt 2N1Đ Săn Mây & Ẩm Thực").first()
        assert plan is not None
        assert len(plan.days) >= 2

        day1 = plan.days[0]
        day2 = plan.days[1]
        assert len(day1.stops) == 2
        assert day1.stops[0].location_name == "Đồi chè Cầu Đất"
        assert day1.stops[0].arrival_time == "07:30"
        assert day1.stops[1].location_name == "Lẩu gà lá é Tao Ngộ"
        assert "Lẩu gà lá é" in (day1.stops[1].notes or "")

        assert len(day2.stops) == 1
        assert day2.stops[0].location_name == "Thác Datanla"

        assert len(plan.lodgings) == 2
        assert plan.lodgings[0].hotel_name == "Làng Boho Homestay"
        assert plan.lodgings[0].day_id == day1.id
        assert plan.lodgings[1].hotel_name == "Khách sạn Colline"
        assert plan.lodgings[1].day_id == day2.id


