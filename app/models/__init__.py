"""Nơi tập hợp import tất cả model — Flask-Migrate dựa vào đây để phát hiện bảng.
Thêm model mới thì thêm 1 dòng import ở đây, không thêm ở đâu khác.
"""
from app.models.user import User
from app.models.follow import Follow
from app.models.post import Post
from app.models.photo import Photo
from app.models.like import Like
from app.models.comment import Comment
from app.models.share import Share
from app.models.saved_post import SavedPost
from app.models.location import Location
from app.models.itinerary import (
    Itinerary, Plan,
    ItineraryDay, PlanDay,
    ItineraryStop, PlanStop, PlanItem,
    ItineraryLodging, PlanLodging,
    ItineraryAttachment
)
from app.models.hashtag import Hashtag
from app.models.map_link import MapLink
from app.models.notification import Notification
from app.models.chat import Conversation, Message, MessageReaction
from app.models.ges_place import GesPlace
from app.models.security_log import SecurityLog
