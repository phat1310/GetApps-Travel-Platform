"""Test suite cho Phân hệ Lịch trình du lịch (Plans / Itinerary).
Bao gồm kiểm thử:
- Danh sách lịch trình cộng đồng & cá nhân (HTML & JSON)
- Tạo lịch trình (Form & JSON API)
- Quản lý Timeline: Thêm ngày, Thêm điểm đến (Stop), Xóa điểm đến
- Phân quyền riêng tư (Public / Private)
- Chỉnh sửa & Xóa lịch trình
"""
import pytest
from datetime import date
from app.models import User, Itinerary, ItineraryDay, ItineraryStop
from app.extensions import db


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
    assert "Lên kế hoạch cho chuyến đi" in html
    assert "Khám phá cộng đồng" in html
    assert "Lịch trình của tôi" in html


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
            "description": "Lịch trình phượt khám phá Đà Lạt mùa đông."
        },
        headers={"Accept": "text/html"}
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
    assert res_guest.status_code == 302
    assert "/plans" in res_guest.headers["Location"]

    # Đăng nhập user2 truy cập
    login_user(client, "testuser2")
    res_user2 = client.get(f"/plans/{plan_id}")
    assert res_user2.status_code == 302

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
    """Khách chưa đăng nhập truy cập /plans/my-plans bị chuyển hướng sang /login."""
    res = client.get("/plans/my-plans")
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]


def test_my_plans_redirect_authenticated(client, users):
    """Người dùng đã đăng nhập truy cập /plans/my-plans được chuyển hướng về /plans?tab=my_plans."""
    login_user(client, "testuser1")
    res = client.get("/plans/my-plans")
    assert res.status_code == 302
    assert "tab=my_plans" in res.headers["Location"]

