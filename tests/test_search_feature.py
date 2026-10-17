"""
Tests for Universal Search Feature (Facebook style).
Checks:
- /search route with tabs (all, users, posts, locations)
- Engagement score sorting (posts with higher likes/comments/shares appear first)
- Private post / itinerary protection
- /search/suggest endpoint
"""

import pytest
from app.extensions import db
from app.models import User, Post, Like, Comment, Share, Location, Itinerary


def test_search_page_empty_query(client):
    """Truy cập /search khi chưa nhập từ khóa."""
    res = client.get('/search')
    assert res.status_code == 200
    assert "Tìm kiếm trên GetApps".encode('utf-8') in res.data
    assert "Nhập từ khóa để bắt đầu tìm kiếm".encode('utf-8') in res.data


def test_search_page_with_users(client, app):
    """Tìm kiếm người dùng và kiểm tra hiển thị tab 'users'."""
    with app.app_context():
        u = User(username="danchoi_dalat", nickname="Dân Chơi Đà Lạt", full_name="Trần Văn Chơi", email="choi@dalat.vn", profile_completed=True)
        u.set_password("123456")
        db.session.add(u)
        db.session.commit()

    # Tab all
    res = client.get('/search?q=dalat')
    assert res.status_code == 200
    assert "danchoi_dalat".encode('utf-8') in res.data

    # Tab users
    res_users = client.get('/search?q=danchoi&tab=users')
    assert res_users.status_code == 200
    assert "danchoi_dalat".encode('utf-8') in res_users.data
    assert "Dân Chơi Đà Lạt".encode('utf-8') in res_users.data


def test_search_posts_engagement_sorting(client, app, users):
    """Kiểm tra bài viết có lượt tương tác (like, comment, share) cao hơn sẽ đứng trước."""
    with app.app_context():
        u1_id = users["user1"].id
        u2_id = users["user2"].id

        # Post A: caption 'Dã ngoại Phú Quốc tuyệt đẹp', 0 tương tác
        p_a = Post(user_id=u1_id, caption="Dã ngoại Phú Quốc tuyệt đẹp bài ít like", visibility="public")
        # Post B: caption 'Review Phú Quốc ăn hải sản', 2 like + 1 cmt
        p_b = Post(user_id=u2_id, caption="Review Phú Quốc ăn hải sản bài nhiều like", visibility="public")
        db.session.add_all([p_a, p_b])
        db.session.commit()

        # Thêm like và comment cho Post B
        l1 = Like(user_id=u1_id, post_id=p_b.id)
        l2 = Like(user_id=u2_id, post_id=p_b.id)
        c1 = Comment(user_id=u1_id, post_id=p_b.id, content="Tuyệt vời quá!")
        db.session.add_all([l1, l2, c1])
        db.session.commit()

        p_a_id = p_a.id
        p_b_id = p_b.id

    res = client.get('/search?q=Phú Quốc&tab=posts')
    assert res.status_code == 200
    content = res.data.decode('utf-8')
    # Post B (nhiều tương tác) phải xuất hiện trước Post A
    pos_b = content.find(f'id="post-article-{p_b_id}"')
    pos_a = content.find(f'id="post-article-{p_a_id}"')
    assert pos_b != -1 and pos_a != -1
    assert pos_b < pos_a


def test_search_private_post_protection(client, app, users):
    """Bài viết private của người khác tuyệt đối không xuất hiện trong kết quả tìm kiếm."""
    with app.app_context():
        u2_id = users["user2"].id
        # Post private của user2
        private_post = Post(user_id=u2_id, caption="Bí mật riêng tư của user2 secretwordxyz", visibility="private")
        db.session.add(private_post)
        db.session.commit()

    # Chưa đăng nhập hoặc đăng nhập user1 tìm từ khóa bí mật
    res = client.get('/search?q=secretwordxyz')
    assert res.status_code == 200
    # Tiêu đề và input chứa từ khóa tìm kiếm nhưng NỘI DUNG bài viết private không được xuất hiện
    assert "Bí mật riêng tư của user2" not in res.data.decode('utf-8')
    assert "Không tìm thấy kết quả nào".encode('utf-8') in res.data


def test_search_suggest_api(client, app):
    """API gợi ý nhanh /search/suggest trả về danh sách user và location."""
    with app.app_context():
        loc = Location(name="Hồ Xuân Hương Đà Lạt", address="Đà Lạt, Lâm Đồng", slug="ho-xuan-huong-da-lat")
        db.session.add(loc)
        db.session.commit()

    # Gõ ngắn < 2 ký tự -> rỗng
    res_short = client.get('/search/suggest?q=d')
    assert res_short.status_code == 200
    assert res_short.get_json() == {"users": [], "locations": []}

    # Gõ >= 2 ký tự khớp location
    res = client.get('/search/suggest?q=Xuân Hương')
    assert res.status_code == 200
    data = res.get_json()
    assert len(data["locations"]) >= 1
    assert data["locations"][0]["name"] == "Hồ Xuân Hương Đà Lạt"


def test_search_locations_dataset(client):
    """Tìm kiếm địa điểm thực tế từ dataset vietnamese-provinces-database (Đà Lạt, Lâm Đồng)."""
    # Test tab locations với từ khóa 'đà lạt'
    res = client.get('/search?q=đà lạt&tab=locations')
    assert res.status_code == 200
    content = res.data.decode('utf-8')
    assert "Lâm Đồng".encode('utf-8') in res.data or "Đà Lạt".encode('utf-8') in res.data
    assert "google.com/maps" in content

    # Test suggest API với từ khóa 'đà lạt'
    res_suggest = client.get('/search/suggest?q=đà lạt')
    assert res_suggest.status_code == 200
    suggest_data = res_suggest.get_json()
    assert len(suggest_data["locations"]) > 0
    # Địa điểm trả về có liên quan tới Đà Lạt / Lâm Đồng
    assert any("Lâm Đồng" in loc["address"] or "Đà Lạt" in loc["name"] for loc in suggest_data["locations"])

