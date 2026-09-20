from app.extensions import db
from app.models import Comment


def login_user(client, username, password="123456"):
    return client.post(
        "/login",
        json={
            "username": username,
            "password": password
        }
    )


def test_create_comment(client, users, post):
    """User có thể tạo Comment cho Post."""

    response = login_user(client, "testuser1")

    assert response.status_code in [200, 302]

    response = client.post(
        f"/locations/posts/{post.id}/comments",
        json={
            "content": "Test comment"
        }
    )

    assert response.status_code == 201

    data = response.get_json()

    assert "comment" in data

    with client.application.app_context():
        comment = Comment.query.filter_by(
            user_id=users["user1"].id,
            post_id=post.id
        ).first()

        assert comment is not None
        assert comment.content == "Test comment"


def test_get_comments(client, post):
    """User có thể lấy danh sách Comment của Post."""

    login_user(client, "testuser1")

    response = client.post(
        f"/locations/posts/{post.id}/comments",
        json={
            "content": "Comment 1"
        }
    )

    assert response.status_code == 201

    response = client.get(
        f"/locations/posts/{post.id}/comments"
    )

    assert response.status_code == 200

    data = response.get_json()

    assert "comments" in data
    assert len(data["comments"]) == 1
    assert data["comments"][0]["content"] == "Comment 1"


def test_empty_comment(client, post):
    """Không cho phép tạo Comment rỗng."""

    login_user(client, "testuser1")

    response = client.post(
        f"/locations/posts/{post.id}/comments",
        json={
            "content": "   "
        }
    )

    assert response.status_code == 400


def test_comment_ownership(client, users, post):
    """User khác không được xóa Comment của User 1."""

    # User 1 đăng nhập và tạo comment
    login_user(client, "testuser1")

    response = client.post(
        f"/locations/posts/{post.id}/comments",
        json={
            "content": "Comment của user 1"
        }
    )

    assert response.status_code == 201

    comment_id = response.get_json()["comment"]["id"]

    # User 2 đăng nhập
    login_user(client, "testuser2")

    # User 2 cố xóa comment của User 1
    response = client.delete(
        f"/locations/comments/{comment_id}"
    )

    assert response.status_code == 403

    # Kiểm tra comment vẫn còn
    with client.application.app_context():
        comment = db.session.get(Comment, comment_id)

        assert comment is not None