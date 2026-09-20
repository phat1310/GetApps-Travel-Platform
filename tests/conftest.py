import os

import pytest

from app import create_app
from app.extensions import db
from app.models import User, Post


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Tạo Flask app và database riêng cho pytest."""

    db_path = tmp_path / "test.db"

    # Cho app dùng database SQLite riêng của pytest
    monkeypatch.setenv(
        "DATABASE_URL",
        f"sqlite:///{db_path}"
    )

    app = create_app()

    app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
    )

    with app.app_context():
        db.create_all()

        # User 1
        user1 = User(
            username="testuser1",
            email="test1@example.com"
        )
        user1.set_password("123456")

        # User 2
        user2 = User(
            username="testuser2",
            email="test2@example.com"
        )
        user2.set_password("123456")

        db.session.add_all([user1, user2])
        db.session.commit()

        # Post của User 1
        post = Post(
            user_id=user1.id,
            caption="Test post"
        )
        db.session.add(post)
        db.session.commit()

    yield app

    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def users(app):
    """Trả về 2 user test."""
    with app.app_context():
        return {
            "user1": User.query.filter_by(username="testuser1").first(),
            "user2": User.query.filter_by(username="testuser2").first(),
        }


@pytest.fixture
def post(app):
    """Trả về Post test."""
    with app.app_context():
        return Post.query.first()