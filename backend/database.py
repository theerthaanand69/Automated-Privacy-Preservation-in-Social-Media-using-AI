from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "instagram.db"
DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


def ensure_sqlite_schema():
    """Apply lightweight SQLite migrations for added columns."""
    with engine.begin() as conn:
        tables = {
            row[0]
            for row in conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

        if "posts" in tables:
            post_columns = {
                row[1]
                for row in conn.exec_driver_sql("PRAGMA table_info(posts)").fetchall()
            }
            if "caption" not in post_columns:
                conn.exec_driver_sql("ALTER TABLE posts ADD COLUMN caption VARCHAR")
            if "visibility" not in post_columns:
                conn.exec_driver_sql("ALTER TABLE posts ADD COLUMN visibility VARCHAR DEFAULT 'public'")
            if "hashtags" not in post_columns:
                conn.exec_driver_sql("ALTER TABLE posts ADD COLUMN hashtags TEXT DEFAULT ''")
            if "mentions" not in post_columns:
                conn.exec_driver_sql("ALTER TABLE posts ADD COLUMN mentions TEXT DEFAULT ''")
            if "risk_report" not in post_columns:
                conn.exec_driver_sql("ALTER TABLE posts ADD COLUMN risk_report TEXT DEFAULT ''")

        if "comments" in tables:
            comment_columns = {
                row[1]
                for row in conn.exec_driver_sql("PRAGMA table_info(comments)").fetchall()
            }
            if "sentiment" not in comment_columns:
                conn.exec_driver_sql("ALTER TABLE comments ADD COLUMN sentiment VARCHAR")

        if "likes" not in tables:
            conn.exec_driver_sql(
                """
                CREATE TABLE likes (
                    id INTEGER PRIMARY KEY,
                    post_id INTEGER,
                    username VARCHAR NOT NULL
                )
                """
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_likes_post_id ON likes (post_id)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_likes_username ON likes (username)"
            )

        if "users" in tables:
            user_columns = {
                row[1]
                for row in conn.exec_driver_sql("PRAGMA table_info(users)").fetchall()
            }
            if "full_name" not in user_columns:
                conn.exec_driver_sql("ALTER TABLE users ADD COLUMN full_name VARCHAR DEFAULT ''")
            if "bio" not in user_columns:
                conn.exec_driver_sql("ALTER TABLE users ADD COLUMN bio TEXT DEFAULT ''")
            if "avatar_url" not in user_columns:
                conn.exec_driver_sql("ALTER TABLE users ADD COLUMN avatar_url VARCHAR DEFAULT ''")
            if "is_private" not in user_columns:
                conn.exec_driver_sql("ALTER TABLE users ADD COLUMN is_private INTEGER DEFAULT 0")
            if "profile_visibility" not in user_columns:
                conn.exec_driver_sql("ALTER TABLE users ADD COLUMN profile_visibility VARCHAR DEFAULT 'public'")
            if "message_privacy" not in user_columns:
                conn.exec_driver_sql("ALTER TABLE users ADD COLUMN message_privacy VARCHAR DEFAULT 'everyone'")
            if "comment_privacy" not in user_columns:
                conn.exec_driver_sql("ALTER TABLE users ADD COLUMN comment_privacy VARCHAR DEFAULT 'everyone'")
            if "activity_status_visible" not in user_columns:
                conn.exec_driver_sql("ALTER TABLE users ADD COLUMN activity_status_visible INTEGER DEFAULT 1")
            if "read_receipts_enabled" not in user_columns:
                conn.exec_driver_sql("ALTER TABLE users ADD COLUMN read_receipts_enabled INTEGER DEFAULT 1")
            if "tagged_post_approval" not in user_columns:
                conn.exec_driver_sql("ALTER TABLE users ADD COLUMN tagged_post_approval INTEGER DEFAULT 1")

        if "saved_posts" not in tables:
            conn.exec_driver_sql(
                """
                CREATE TABLE saved_posts (
                    id INTEGER PRIMARY KEY,
                    post_id INTEGER,
                    username VARCHAR NOT NULL
                )
                """
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_saved_posts_post_id ON saved_posts (post_id)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_saved_posts_username ON saved_posts (username)"
            )

        if "follows" not in tables:
            conn.exec_driver_sql(
                """
                CREATE TABLE follows (
                    id INTEGER PRIMARY KEY,
                    follower_username VARCHAR NOT NULL,
                    following_username VARCHAR NOT NULL
                )
                """
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_follows_follower ON follows (follower_username)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_follows_following ON follows (following_username)"
            )

        if "follow_requests" not in tables:
            conn.exec_driver_sql(
                """
                CREATE TABLE follow_requests (
                    id INTEGER PRIMARY KEY,
                    requester_username VARCHAR NOT NULL,
                    target_username VARCHAR NOT NULL,
                    status VARCHAR DEFAULT 'pending'
                )
                """
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_follow_requests_requester ON follow_requests (requester_username)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_follow_requests_target ON follow_requests (target_username)"
            )

        if "tag_requests" not in tables:
            conn.exec_driver_sql(
                """
                CREATE TABLE tag_requests (
                    id INTEGER PRIMARY KEY,
                    post_id INTEGER NOT NULL,
                    comment_id INTEGER,
                    requester_username VARCHAR NOT NULL,
                    tagged_username VARCHAR NOT NULL,
                    status VARCHAR DEFAULT 'pending'
                )
                """
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_tag_requests_post_id ON tag_requests (post_id)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_tag_requests_tagged ON tag_requests (tagged_username)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_tag_requests_comment_id ON tag_requests (comment_id)"
            )
        else:
            tag_request_columns = {
                row[1]
                for row in conn.exec_driver_sql("PRAGMA table_info(tag_requests)").fetchall()
            }
            if "comment_id" not in tag_request_columns:
                conn.exec_driver_sql("ALTER TABLE tag_requests ADD COLUMN comment_id INTEGER")
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_tag_requests_comment_id ON tag_requests (comment_id)"
            )

        if "user_blocks" not in tables:
            conn.exec_driver_sql(
                """
                CREATE TABLE user_blocks (
                    id INTEGER PRIMARY KEY,
                    blocker_username VARCHAR NOT NULL,
                    blocked_username VARCHAR NOT NULL
                )
                """
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_user_blocks_blocker ON user_blocks (blocker_username)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_user_blocks_blocked ON user_blocks (blocked_username)"
            )

        if "close_friends" not in tables:
            conn.exec_driver_sql(
                """
                CREATE TABLE close_friends (
                    id INTEGER PRIMARY KEY,
                    username VARCHAR NOT NULL,
                    close_friend_username VARCHAR NOT NULL
                )
                """
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_close_friends_username ON close_friends (username)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_close_friends_friend ON close_friends (close_friend_username)"
            )

        if "notifications" not in tables:
            conn.exec_driver_sql(
                """
                CREATE TABLE notifications (
                    id INTEGER PRIMARY KEY,
                    username VARCHAR NOT NULL,
                    actor_username VARCHAR NOT NULL,
                    event_type VARCHAR NOT NULL,
                    message TEXT NOT NULL,
                    is_read INTEGER DEFAULT 0
                )
                """
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_notifications_username ON notifications (username)"
            )

        if "moderation_logs" not in tables:
            conn.exec_driver_sql(
                """
                CREATE TABLE moderation_logs (
                    id INTEGER PRIMARY KEY,
                    username VARCHAR NOT NULL,
                    target_type VARCHAR NOT NULL,
                    content TEXT DEFAULT '',
                    status VARCHAR NOT NULL,
                    reason TEXT DEFAULT ''
                )
                """
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_moderation_logs_username ON moderation_logs (username)"
            )

        if "stego_scans" not in tables:
            conn.exec_driver_sql(
                """
                CREATE TABLE stego_scans (
                    id INTEGER PRIMARY KEY,
                    username VARCHAR NOT NULL,
                    filename VARCHAR NOT NULL,
                    verdict VARCHAR NOT NULL,
                    reason TEXT DEFAULT '',
                    preview TEXT DEFAULT '',
                    danger_keywords TEXT DEFAULT ''
                )
                """
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_stego_scans_username ON stego_scans (username)"
            )

        if "messages" not in tables:
            conn.exec_driver_sql(
                """
                CREATE TABLE messages (
                    id INTEGER PRIMARY KEY,
                    sender_username VARCHAR NOT NULL,
                    receiver_username VARCHAR NOT NULL,
                    content TEXT NOT NULL
                )
                """
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_messages_sender ON messages (sender_username)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_messages_receiver ON messages (receiver_username)"
            )
        else:
            message_columns = {
                row[1]
                for row in conn.exec_driver_sql("PRAGMA table_info(messages)").fetchall()
            }
            if "is_seen" not in message_columns:
                conn.exec_driver_sql("ALTER TABLE messages ADD COLUMN is_seen INTEGER DEFAULT 0")
