from app.models import Share


def login_user(client, username, password="123456"):
    return client.post(
        "/login",
        json={
            "username": username,
            "password": password
        }
    )


def test_share_post(client, users, post):
    """User có thể Share một Post."""

    response = login_user(client, "testuser1")

    assert response.status_code in [200, 302]

    response = client.post(
        f"/locations/posts/{post.id}/share"
    )

    assert response.status_code == 201

    data = response.get_json()

    assert data["share"]["user_id"] == users["user1"].id
    assert data["share"]["post_id"] == post.id

    with client.application.app_context():
        shares = Share.query.filter_by(
            user_id=users["user1"].id,
            post_id=post.id
        ).all()

        assert len(shares) == 1


def test_share_post_multiple_times(client, users, post):
    """Một User có thể Share cùng một Post nhiều lần."""

    login_user(client, "testuser1")

    # Share lần 1
    response = client.post(
        f"/locations/posts/{post.id}/share"
    )

    assert response.status_code == 201

    first_share_id = response.get_json()["share"]["id"]

    # Share lần 2
    response = client.post(
        f"/locations/posts/{post.id}/share"
    )

    assert response.status_code == 201

    second_share_id = response.get_json()["share"]["id"]

    # Mỗi lần Share tạo một record mới
    assert second_share_id != first_share_id

    with client.application.app_context():
        shares = Share.query.filter_by(
            user_id=users["user1"].id,
            post_id=post.id
        ).all()

        assert len(shares) == 2