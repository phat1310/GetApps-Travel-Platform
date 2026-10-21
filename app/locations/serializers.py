"""Serializer BÀI VIẾT — dựng JSON cho feed, chi tiết bài viết (và danh sách đã lưu).
Dùng số query CỐ ĐỊNH bất kể có bao nhiêu bài (không N+1).
"""
from collections import defaultdict
from sqlalchemy import func

from app.extensions import db
from app.models import Post, Photo, Like, Comment, SavedPost, Location, User
from app.models.map_link import MapLink
from app.models.post import post_extra_locations
from app.models.hashtag import Hashtag, post_hashtags


def serialize_posts(posts, viewer_id):
    """posts: list Post. viewer_id: id người đang xem (để tính liked_by_me, saved_by_me)."""
    if not posts:
        return []

    post_ids = [p.id for p in posts]
    user_ids = {p.user_id for p in posts}
    location_ids = {p.location_id for p in posts if p.location_id}

    authors = {u.id: u for u in User.query.filter(User.id.in_(user_ids)).all()}
    locations = (
        {l.id: l for l in Location.query.filter(Location.id.in_(location_ids)).all()}
        if location_ids else {}
    )

    # Bản đăng lại luôn lấy NỘI DUNG (chữ + ảnh/video) từ bài gốc
    root_of = {p.id: p.original_post_id for p in posts if p.original_post_id}
    roots = {r.id: r for r in Post.query.filter(Post.id.in_(set(root_of.values()) or {0})).all()}

    media = defaultdict(list)
    for ph in Photo.query.filter(Photo.post_id.in_(post_ids + list(roots))).order_by(Photo.id).all():
        media[ph.post_id].append({"file_path": ph.file_path, "media_type": ph.media_type})

    extra = defaultdict(list)
    rows = (
        db.session.query(post_extra_locations.c.post_id, Location)
        .select_from(post_extra_locations)
        .join(Location, Location.id == post_extra_locations.c.location_id)
        .filter(post_extra_locations.c.post_id.in_(post_ids))
        .all()
    )
    for post_id, loc in rows:
        extra[post_id].append({"id": loc.id, "name": loc.name})

    maps = defaultdict(list)
    for m in MapLink.query.filter(MapLink.post_id.in_(post_ids)).order_by(MapLink.position).all():
        if m.safe_url:
            maps[m.post_id].append(m.to_dict())

    tags = defaultdict(list)
    rows = (
        db.session.query(post_hashtags.c.post_id, Hashtag.name)
        .select_from(post_hashtags)
        .join(Hashtag, Hashtag.id == post_hashtags.c.hashtag_id)
        .filter(post_hashtags.c.post_id.in_(post_ids))
        .all()
    )
    for post_id, name in rows:
        tags[post_id].append(name)

    like_counts = dict(
        db.session.query(Like.post_id, func.count())
        .filter(Like.post_id.in_(post_ids)).group_by(Like.post_id).all()
    )
    comment_counts = dict(
        db.session.query(Comment.post_id, func.count())
        .filter(Comment.post_id.in_(post_ids)).group_by(Comment.post_id).all()
    )
    liked = {
        r[0] for r in db.session.query(Like.post_id)
        .filter(Like.user_id == viewer_id, Like.post_id.in_(post_ids)).all()
    }
    saved = {
        r[0] for r in db.session.query(SavedPost.post_id)
        .filter(SavedPost.user_id == viewer_id, SavedPost.post_id.in_(post_ids)).all()
    }

    result = []
    for p in posts:
        author = authors.get(p.user_id)
        loc = locations.get(p.location_id)
        result.append({
            "post_id": p.id,
            "user_id": p.user_id,
            "author": {
                "id": author.id,
                "username": author.username,
                "nickname": author.nickname,
                "avatar_url": author.avatar_url,
            } if author else None,
            "caption": (roots.get(root_of.get(p.id)) or p).caption,
            "visibility": p.visibility,
            "created_at": p.created_at.isoformat(),
            "edited_at": ((roots.get(root_of.get(p.id)) or p).edited_at.isoformat() + "Z")
                          if (roots.get(root_of.get(p.id)) or p).edited_at else None,
            "location": {"id": loc.id, "name": loc.name} if loc else None,
            "extra_locations": extra.get(p.id, []),
            "map_links": maps.get(p.id, []),
            "hashtags": sorted(tags.get(p.id, [])),
            "media": media.get(root_of.get(p.id) or p.id, []),
            "like_count": like_counts.get(p.id, 0),
            "comment_count": comment_counts.get(p.id, 0),
            "liked_by_me": p.id in liked,
            "saved_by_me": p.id in saved,
        })
    return result