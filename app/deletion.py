"""Xóa bài đăng / lịch trình KÈM mọi dữ liệu liên quan (tim, bình luận, chia sẻ, đã lưu, thông báo, ảnh...).

Các bảng liên quan trỏ tới posts/itineraries bằng khóa ngoại nhưng không có cascade ở mô hình,
nên xóa ở đây một cách tường minh để không để lại dữ liệu mồ côi.
"""
import os

from flask import current_app

from app.extensions import db


def _upload_root():
    return os.path.realpath(os.path.join(current_app.root_path, "static"))


def remove_files_if_unused(paths):
    """Xóa file tĩnh (ảnh/video/tệp) nếu không còn dòng Photo / cover / attachment nào dùng; chỉ xóa trong static/."""
    from app.models import Photo, Itinerary
    from app.models.itinerary import ItineraryAttachment, ItineraryStop
    root = _upload_root()
    for rel in {p for p in paths if p}:
        still_used = (
            Photo.query.filter_by(file_path=rel).first()
            or Itinerary.query.filter((Itinerary.cover_image == rel) | (Itinerary.attachment_file == rel)).first()
            or ItineraryAttachment.query.filter_by(file_path=rel).first()
            or ItineraryStop.query.filter_by(image_path=rel).first()
        )
        if still_used:
            continue
        full = os.path.realpath(os.path.join(current_app.root_path, rel))
        if not full.startswith(root + os.sep):       # chặn path traversal (đường dẫn lạ trong DB)
            continue
        try:
            if os.path.isfile(full):
                os.remove(full)
        except OSError:
            pass


def delete_post_cascade(post):
    """Xóa 1 bài. Nếu là BÀI GỐC thì xóa luôn các bản đăng lại của nó. Trả về danh sách id đã xóa."""
    from app.models import Post, Photo, Like, Comment, Share, SavedPost, Notification

    ids, queue = [], [post.id]
    while queue:                                       # gốc + mọi repost (kể cả chuỗi repost cũ)
        cur = queue.pop()
        if cur in ids:
            continue
        ids.append(cur)
        queue.extend(r.id for r in Post.query.filter_by(original_post_id=cur).all())

    # Repost đơn lẻ: trả lại quyền đăng lại cho chính người đó
    if post.original_post_id:
        Share.query.filter_by(user_id=post.user_id, post_id=post.original_post_id, share_type="repost").delete()

    files = [p.file_path for p in Photo.query.filter(Photo.post_id.in_(ids)).all()]

    Like.query.filter(Like.post_id.in_(ids)).delete(synchronize_session=False)
    Comment.query.filter(Comment.post_id.in_(ids)).delete(synchronize_session=False)
    Share.query.filter(Share.post_id.in_(ids)).delete(synchronize_session=False)
    SavedPost.query.filter(SavedPost.post_id.in_(ids)).delete(synchronize_session=False)
    Notification.query.filter(Notification.post_id.in_(ids)).delete(synchronize_session=False)
    Photo.query.filter(Photo.post_id.in_(ids)).delete(synchronize_session=False)

    # Xóa con trước, gốc sau (repost trỏ về gốc bằng khóa ngoại)
    for pid in reversed(ids):
        obj = db.session.get(Post, pid)
        if obj is not None:
            obj.hashtags.clear()
            obj.extra_locations.clear()
            db.session.delete(obj)
            db.session.flush()
    db.session.commit()
    remove_files_if_unused(files)
    return ids


def delete_itinerary_cascade(it):
    """Xóa lịch trình + tim/bình luận/chia sẻ/đã lưu/thông báo + tệp đính kèm/ảnh bìa."""
    from app.models import Like, Comment, Share, SavedPost, Notification
    from app.models.itinerary import ItineraryAttachment, ItineraryStop, ItineraryDay

    iid = it.id
    files = [it.cover_image, it.attachment_file]
    files += [a.file_path for a in ItineraryAttachment.query.filter_by(itinerary_id=iid).all()]
    day_ids = [d.id for d in ItineraryDay.query.filter_by(itinerary_id=iid).all()]
    if day_ids:
        files += [s.image_path for s in ItineraryStop.query.filter(ItineraryStop.day_id.in_(day_ids)).all()]

    Like.query.filter_by(itinerary_id=iid).delete(synchronize_session=False)
    Comment.query.filter_by(itinerary_id=iid).delete(synchronize_session=False)
    Share.query.filter_by(itinerary_id=iid).delete(synchronize_session=False)
    SavedPost.query.filter_by(itinerary_id=iid).delete(synchronize_session=False)
    Notification.query.filter_by(itinerary_id=iid).delete(synchronize_session=False)
    db.session.delete(it)            # days/stops/lodgings/attachments/map_links: cascade ở mô hình
    db.session.commit()
    remove_files_if_unused(files)
