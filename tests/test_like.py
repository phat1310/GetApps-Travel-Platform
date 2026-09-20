from app.extensions import db
from app.models import Like


def login_user(client, username, password="123456"):
    return client.post(
        "/login",
        json={
            "username": username,
            "password": password
        }
    )


def test_like_post(client, users, post):
    """User có thể Like một Post."""

    response = login_user(client, "testuser1")

    assert response.status_code in [200, 302]

    response = client.post(
        f"/locations/posts/{post.id}/like"
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["liked"] is True

    with client.application.app_context():
        like = Like.query.filter_by(
            user_id=users["user1"].id,
            post_id=post.id
        ).first()

        assert like is not None


def test_unlike_post(client, users, post):
    """User có thể Unlike một Post đã Like."""

    login_user(client, "testuser1")

    # Like trước
    response = client.post(
        f"/locations/posts/{post.id}/like"
    )

    assert response.status_code == 200
    assert response.get_json()["liked"] is True

    # Unlike
    response = client.post(
        f"/locations/posts/{post.id}/like"
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["liked"] is False

    with client.application.app_context():
        like = Like.query.filter_by(
            user_id=users["user1"].id,
            post_id=post.id
        ).first()

        assert like is None