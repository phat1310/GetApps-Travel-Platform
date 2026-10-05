"""Model HASHTAG — nhãn tự do gắn vào bài viết (tối đa 3 hashtag mỗi bài).
Bảng nối post_hashtags (nhiều-nhiều). Post.hashtags được tạo tự động qua backref,
nên không cần sửa app/models/post.py.
"""
from datetime import datetime
from app.extensions import db

post_hashtags = db.Table(
    "post_hashtags",
    db.Column("post_id", db.Integer, db.ForeignKey("posts.id"), primary_key=True),
    db.Column("hashtag_id", db.Integer, db.ForeignKey("hashtags.id"), primary_key=True),
)


class Hashtag(db.Model):
    __tablename__ = "hashtags"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)  # đã chuẩn hóa: "dalat"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    posts = db.relationship("Post", secondary=post_hashtags, backref="hashtags")

    def __repr__(self):
        return f"<Hashtag {self.name}>"