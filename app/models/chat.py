"""Model CHAT — hội thoại 1-1, tin nhắn và lượt thả tim.

Conversation luôn lưu cặp (user_a_id < user_b_id) để một cặp người chỉ có đúng 1 hội thoại.
status của hội thoại:
  - "mutual"  : tạo khi hai người đã follow nhau (chỉ gửi được khi vẫn còn follow nhau)
  - "pending" : người lạ nhắn trước (initiated_by) -> vào mục "Tin nhắn chờ" của người nhận
  - "accepted": người nhận đã chấp nhận (hoặc đã trả lời) -> nhắn tự do
  - "declined": người nhận đã từ chối
File đính kèm KHÔNG nằm trong static/ mà nằm trong instance/chat_uploads/, chỉ tải qua route có kiểm tra quyền.
"""
from datetime import datetime
from app.extensions import db


class Conversation(db.Model):
    __tablename__ = "conversations"

    id = db.Column(db.Integer, primary_key=True)
    user_a_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    user_b_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    last_message_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(10), nullable=False, default="mutual")
    initiated_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    messages = db.relationship(
        "Message", backref="conversation", lazy="dynamic",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        db.UniqueConstraint("user_a_id", "user_b_id", name="unique_conversation_pair"),
        db.CheckConstraint("user_a_id < user_b_id", name="chk_conversation_order"),
    )

    def other_user_id(self, user_id):
        return self.user_b_id if user_id == self.user_a_id else self.user_a_id

    def has_member(self, user_id):
        return user_id in (self.user_a_id, self.user_b_id)


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversations.id"), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    body = db.Column(db.Text, nullable=True)

    # Tệp đính kèm (tùy chọn)
    file_path = db.Column(db.String(255), nullable=True)   # tên file ngẫu nhiên trên đĩa
    file_name = db.Column(db.String(255), nullable=True)   # tên gốc, chỉ để hiển thị
    file_kind = db.Column(db.String(10), nullable=True)    # image | video | file
    file_size = db.Column(db.Integer, nullable=True)

    is_read = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    reactions = db.relationship(
        "MessageReaction", backref="message", lazy="dynamic", cascade="all, delete-orphan"
    )


class MessageReaction(db.Model):
    """Lượt thả tim của 1 người vào 1 tin nhắn (mỗi người tối đa 1 tim / tin)."""
    __tablename__ = "message_reactions"

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey("messages.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("message_id", "user_id", name="unique_message_reaction"),
    )
