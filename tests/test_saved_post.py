from app.extensions import db
from app.models import SavedPost


def login_user(client, username, password="123456"):
    return client.post(
        "/login",
        json={
            "username": username,
            "password": password
        }
    )


def test_save_post(client, users, post):
    """User có thể lưu một Post."""

    response = login_user(client, "testuser1")

    assert response.status_code in [200, 302]

    response = client.post(
        f"/locations/posts/{post.id}/save"
    )

    assert response.status_code == 201

    data = response.get_json()

    assert data["saved"] is True

    with client.application.app_context():
        saved = SavedPost.query.filter_by(
            user_id=users["user1"].id,
            post_id=post.id
        ).first()

        assert saved is not None


def test_unsave_post(client, users, post):
    """User có thể bỏ lưu một Post."""

    login_user(client, "testuser1")

    # Lưu lần 1
    response = client.post(
        f"/locations/posts/{post.id}/save"
    )

    assert response.status_code == 201
    assert response.get_json()["saved"] is True

    # Bỏ lưu lần 2
    response = client.post(
        f"/locations/posts/{post.id}/save"
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["saved"] is False

    with client.application.app_context():
        saved = SavedPost.query.filter_by(
            user_id=users["user1"].id,
            post_id=post.id
        ).first()

        assert saved is None