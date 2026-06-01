from sqlalchemy import Column, Integer, String, Text
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, default="")
    bio = Column(Text, default="")
    avatar_url = Column(String, default="")
    is_private = Column(Integer, default=0)
    profile_visibility = Column(String, default="public")
    message_privacy = Column(String, default="everyone")
    comment_privacy = Column(String, default="everyone")
    activity_status_visible = Column(Integer, default=1)
    read_receipts_enabled = Column(Integer, default=1)
    tagged_post_approval = Column(Integer, default=1)

class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    image_path = Column(String)
    username = Column(String)
    caption = Column(String)
    visibility = Column(String, default="public")
    hashtags = Column(Text, default="")
    mentions = Column(Text, default="")
    risk_report = Column(Text, default="")

class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer)
    username = Column(String)
    content = Column(Text)
    sentiment = Column(String)


class Like(Base):
    __tablename__ = "likes"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, index=True)
    username = Column(String, index=True, nullable=False)


class SavedPost(Base):
    __tablename__ = "saved_posts"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, index=True)
    username = Column(String, index=True, nullable=False)


class Follow(Base):
    __tablename__ = "follows"

    id = Column(Integer, primary_key=True, index=True)
    follower_username = Column(String, index=True, nullable=False)
    following_username = Column(String, index=True, nullable=False)


class FollowRequest(Base):
    __tablename__ = "follow_requests"

    id = Column(Integer, primary_key=True, index=True)
    requester_username = Column(String, index=True, nullable=False)
    target_username = Column(String, index=True, nullable=False)
    status = Column(String, default="pending")


class TagRequest(Base):
    __tablename__ = "tag_requests"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, index=True, nullable=False)
    comment_id = Column(Integer, index=True, nullable=True)
    requester_username = Column(String, index=True, nullable=False)
    tagged_username = Column(String, index=True, nullable=False)
    status = Column(String, default="pending")


class UserBlock(Base):
    __tablename__ = "user_blocks"

    id = Column(Integer, primary_key=True, index=True)
    blocker_username = Column(String, index=True, nullable=False)
    blocked_username = Column(String, index=True, nullable=False)


class CloseFriend(Base):
    __tablename__ = "close_friends"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True, nullable=False)
    close_friend_username = Column(String, index=True, nullable=False)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True, nullable=False)
    actor_username = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Integer, default=0)


class ModerationLog(Base):
    __tablename__ = "moderation_logs"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True, nullable=False)
    target_type = Column(String, nullable=False)
    content = Column(Text, default="")
    status = Column(String, nullable=False)
    reason = Column(Text, default="")


class StegoScan(Base):
    __tablename__ = "stego_scans"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True, nullable=False)
    filename = Column(String, nullable=False)
    verdict = Column(String, nullable=False)
    reason = Column(Text, default="")
    preview = Column(Text, default="")
    danger_keywords = Column(Text, default="")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    sender_username = Column(String, index=True, nullable=False)
    receiver_username = Column(String, index=True, nullable=False)
    content = Column(Text, nullable=False)
    is_seen = Column(Integer, default=0)
