from app.models import Share, Post, Photo


def login_user(client, username, password="123456"):
    return client.post(
        "/login",
        json={
            "username": username,
            "password": password
        }
    )


def test_share_post(client, users, post):
    """User có thể Share một Post bằng Copy Link."""

    response = login_user(client, "testuser1")

    assert response.status_code in [200, 302]

    response = client.post(
        f"/locations/posts/{post.id}/share"
    )

    assert response.status_code == 201

    data = response.get_json()

    assert data["share"]["user_id"] == users["user1"].id
    assert data["share"]["post_id"] == post.id
    assert data["share"]["share_type"] == "copy_link"

    with client.application.app_context():
        shares = Share.query.filter_by(
            user_id=users["user1"].id,
            post_id=post.id,
            share_type="copy_link"
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
            post_id=post.id,
            share_type="copy_link"
        ).all()

        assert len(shares) == 2


def test_download_post(client, users, post):
    """User có thể Download file của Post."""

    login_user(client, "testuser1")

    response = client.get(
        f"/locations/posts/{post.id}/share/download"
    )

    assert response.status_code == 200

    # Kiểm tra server trả file dạng download
    content_disposition = response.headers.get(
        "Content-Disposition",
        ""
    )

    assert "attachment" in content_disposition
    assert "test.png" in content_disposition

    # Kiểm tra Share được ghi nhận
    with client.application.app_context():
        share = Share.query.filter_by(
            user_id=users["user1"].id,
            post_id=post.id,
            share_type="download"
        ).first()

        assert share is not None


def test_repost_post(client, users, post):
    """User có thể Repost một Post."""

    login_user(client, "testuser1")

    response = client.post(
        f"/locations/posts/{post.id}/repost"
    )

    assert response.status_code == 201

    data = response.get_json()

    repost_data = data["repost"]

    # Kiểm tra bài repost
    assert repost_data["user_id"] == users["user1"].id
    assert repost_data["original_post_id"] == post.id
    assert repost_data["caption"] == post.caption

    # Kiểm tra Share được ghi nhận
    assert data["share"]["share_type"] == "repost"

    with client.application.app_context():
        # Kiểm tra Post repost thực sự tồn tại
        repost = Post.query.filter_by(
            id=repost_data["id"]
        ).first()

        assert repost is not None
        assert repost.user_id == users["user1"].id
        assert repost.original_post_id == post.id

        # Kiểm tra Photo được copy sang bài repost
        repost_photos = Photo.query.filter_by(
            post_id=repost.id
        ).all()

        assert len(repost_photos) == 1
        assert repost_photos[0].file_path == "static/uploads/test.png"

        # Kiểm tra Share record
        share = Share.query.filter_by(
            user_id=users["user1"].id,
            post_id=post.id,
            share_type="repost"
        ).first()

        assert share is not None