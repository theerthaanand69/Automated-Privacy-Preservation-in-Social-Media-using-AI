from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
import asyncio
import cv2
import numpy as np
import io
import json
import os
import pytesseract
import re
import shutil
import uuid
import hashlib
import hmac
import inspect
from typing import Optional
from pathlib import Path
from textblob import TextBlob
from googletrans import Translator
from langdetect import detect
from database import engine, SessionLocal, ensure_sqlite_schema
from models import Base
from models import (
    User,
    Post,
    Comment,
    Like,
    SavedPost,
    Follow,
    FollowRequest,
    TagRequest,
    UserBlock,
    CloseFriend,
    Notification,
    ModerationLog,
    StegoScan,
    Message,
)
from sqlalchemy import desc, or_, func

# =============================================================================
# Backend API (FastAPI)
# - Auth + profiles
# - Feed/posts/comments/likes/saves
# - Follow + privacy + tag approvals
# - Messaging
# - Moderation (toxicity + stego + OCR/blur)
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent
YOLO_CONFIG_DIR = BASE_DIR / ".yolo-config"
YOLO_CONFIG_DIR.mkdir(exist_ok=True)
os.environ.setdefault("YOLO_CONFIG_DIR", str(YOLO_CONFIG_DIR))

from ultralytics import YOLO


# Create FastAPI app instance
app = FastAPI()

# Create tables and run lightweight migrations
Base.metadata.create_all(bind=engine)
ensure_sqlite_schema()

translator = Translator()

# Allow frontend calls (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Load license plate model
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)
app.mount("/media", StaticFiles(directory=str(UPLOADS_DIR)), name="media")


# Load YOLO model if weights are present
def _load_yolo_model(model_path: Path):
    try:
        if not model_path.exists():
            return None
        return YOLO(str(model_path))
    except Exception:
        return None


model = _load_yolo_model(BASE_DIR / "yolov8n-license-plate.pt")

# Configure Tesseract OCR path (Windows locations)
_tesseract_from_path = shutil.which("tesseract")
_tesseract_candidates = [
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path.home() / "AppData" / "Local" / "Programs" / "Tesseract-OCR" / "tesseract.exe",
]
if _tesseract_from_path:
    _tesseract_candidates.insert(0, Path(_tesseract_from_path))

for _exe in _tesseract_candidates:
    if _exe.exists():
        pytesseract.pytesseract.tesseract_cmd = str(_exe)
        break

# ---------------------------
# Steganography detection settings
# ---------------------------
STEGO_SENTINEL = b"::STEGO_END::"
PRINTABLE_BYTES = set(range(32, 127)) | {9, 10, 13}
STEGO_DEFAULT_PRINTABLE_RUN = 24
STEGO_STRICT_PRINTABLE_RUN = 12
STEGO_DEFAULT_MIN_LETTERS = 4
STEGO_STRICT_MIN_LETTERS = 6
# Define toxic keywords to block when found inside hidden steganography payloads.
TOXIC_KEYWORDS = {
    "kill",
    "murder",
    "bomb",
    "attack",
    "terror",
    "weapon",
    "explosive",
    "drugs",
    "poison",
    "suicide",
    "rape",
    "abuse",
    "threat",
    "hack",
    "malware",
}
DANGER_KEYWORDS = TOXIC_KEYWORDS
TOXIC_PATTERNS = {
    word: re.compile(
        rf"(?<![a-z0-9]){'[^a-z0-9]*'.join(re.escape(ch) for ch in word)}(?![a-z0-9])"
    )
    for word in sorted(TOXIC_KEYWORDS)
}
PASSWORD_HASH_PREFIX = "pbkdf2_sha256"


# ---------------------------
# Text/tag helpers
# ---------------------------
def _extract_tags(text: str, prefix: str) -> list[str]:
    pattern = rf"\{prefix}([A-Za-z0-9_]+)"
    if prefix == "@":
        pattern = rf"\{prefix}([A-Za-z0-9_.]+)"
    return sorted(set(match.lower() for match in re.findall(pattern, text or "")))


# Safe JSON parse with fallback
def _safe_json_loads(value: str, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


# Create a notification row
def _log_notification(db, username: str, actor_username: str, event_type: str, message: str) -> None:
    if not username or username == actor_username:
        return
    db.add(
        Notification(
            username=username,
            actor_username=actor_username,
            event_type=event_type,
            message=message,
        )
    )


# Create a moderation log row
def _log_moderation(db, username: str, target_type: str, content: str, status: str, reason: str) -> None:
    db.add(
        ModerationLog(
            username=(username or "user").strip() or "user",
            target_type=target_type,
            content=content or "",
            status=status,
            reason=reason or "",
        )
    )


# Store steganography scan result
def _store_stego_scan(db, username: str, filename: str, verdict: str, reason: str, preview: str, matches: list[str]) -> None:
    db.add(
        StegoScan(
            username=(username or "user").strip() or "user",
            filename=filename or "unknown",
            verdict=verdict,
            reason=reason or "",
            preview=preview or "",
            danger_keywords=", ".join(matches or []),
        )
    )


# Normalize a string to a limited set of allowed values
def _normalize_choice(value: str, allowed: set[str], default: str) -> str:
    clean = (value or default).strip().lower()
    return clean if clean in allowed else default


# Check block relationship between two users
def _is_blocked(db, username_a: str, username_b: str) -> bool:
    left = (username_a or "").strip()
    right = (username_b or "").strip()
    if not left or not right:
        return False
    return (
        db.query(UserBlock)
        .filter(
            or_(
                (UserBlock.blocker_username == left) & (UserBlock.blocked_username == right),
                (UserBlock.blocker_username == right) & (UserBlock.blocked_username == left),
            )
        )
        .first()
        is not None
    )


# Check if follower -> following exists
def _is_following(db, follower_username: str, following_username: str) -> bool:
    follower = (follower_username or "").strip()
    following = (following_username or "").strip()
    if not follower or not following:
        return False
    return (
        db.query(Follow)
        .filter(
            Follow.follower_username == follower,
            Follow.following_username == following,
        )
        .first()
        is not None
    )


# Check if viewer is in owner's close-friends list
def _is_close_friend(db, owner_username: str, viewer_username: str) -> bool:
    owner = (owner_username or "").strip()
    viewer = (viewer_username or "").strip()
    if not owner or not viewer:
        return False
    return (
        db.query(CloseFriend)
        .filter(
            CloseFriend.username == owner,
            CloseFriend.close_friend_username == viewer,
        )
        .first()
        is not None
    )


# Lookup a pending follow request (if any)
def _get_pending_follow_request(db, requester_username: str, target_username: str):
    return (
        db.query(FollowRequest)
        .filter(
            FollowRequest.requester_username == (requester_username or "").strip(),
            FollowRequest.target_username == (target_username or "").strip(),
            FollowRequest.status == "pending",
        )
        .first()
    )


# Map tagged_username -> status for a post
def _get_tag_request_map(db, post_id: int) -> dict[str, str]:
    rows = (
        db.query(TagRequest)
        .filter(TagRequest.post_id == post_id, TagRequest.comment_id.is_(None))
        .all()
    )
    return {(row.tagged_username or "").lower(): row.status for row in rows}


# Map tagged_username -> status for a comment
def _get_comment_tag_request_map(db, comment_id: int) -> dict[str, str]:
    rows = db.query(TagRequest).filter(TagRequest.comment_id == comment_id).all()
    return {(row.tagged_username or "").lower(): row.status for row in rows}


# Replace hidden @mentions with "@hidden"
def _redact_caption_mentions(caption: str, hidden_mentions: set[str]) -> str:
    if not caption or not hidden_mentions:
        return caption or ""
    hidden = {name.lower() for name in hidden_mentions}

    def replacer(match: re.Match[str]) -> str:
        name = match.group(1)
        if name.lower() in hidden:
            return "@hidden"
        return match.group(0)

    return re.sub(r"@([A-Za-z0-9_.]+)", replacer, caption)


# Determine which @mentions are visible vs hidden in a post caption
def _build_tag_visibility(post: Post, viewer_username: str, db) -> tuple[str, list[str], list[str]]:
    caption = post.caption or ""
    mentions = [name for name in (post.mentions or "").split(",") if name]
    if not mentions:
        return caption, mentions, []

    viewer = (viewer_username or "").strip()
    owner = (post.username or "").strip()
    viewer_key = viewer.lower()
    owner_key = owner.lower()
    statuses = _get_tag_request_map(db, post.id)
    hidden_mentions: set[str] = set()
    pending_for_viewer: list[str] = []

    for mention in mentions:
        mention_key = (mention or "").lower()
        status = statuses.get(mention_key)
        if status == "pending":
            if viewer_key == mention_key:
                pending_for_viewer.append(mention)
            if viewer_key not in {mention_key, owner_key}:
                hidden_mentions.add(mention)
        elif status in {"rejected", "reject"}:
            hidden_mentions.add(mention)

    caption_public = _redact_caption_mentions(caption, hidden_mentions)
    visible_mentions = [name for name in mentions if name not in hidden_mentions]
    return caption_public, visible_mentions, pending_for_viewer


# Determine visible comment text based on tag approvals
def _build_comment_visibility(comment: Comment, viewer_username: str, db) -> str:
    content = comment.content or ""
    statuses = _get_comment_tag_request_map(db, comment.id)
    if not statuses:
        return content

    viewer_key = (viewer_username or "").strip().lower()
    owner_key = (comment.username or "").strip().lower()
    hidden_mentions: set[str] = set()

    for mention_key, status in statuses.items():
        if status == "pending":
            if viewer_key not in {mention_key, owner_key}:
                hidden_mentions.add(mention_key)
        elif status in {"rejected", "reject"}:
            hidden_mentions.add(mention_key)

    return _redact_caption_mentions(content, hidden_mentions)


# Profile visibility rules
def _can_view_profile(user: User, viewer_username: str, db) -> bool:
    viewer = (viewer_username or "").strip()
    if not user:
        return False
    if viewer == user.username:
        return True
    if _is_blocked(db, user.username, viewer):
        return False
    if not bool(user.is_private):
        return True
    return _is_following(db, viewer, user.username)


# Message privacy rules
def _can_send_message_to(db, sender_username: str, target_user: User) -> bool:
    sender = (sender_username or "").strip()
    if not target_user or not sender:
        return False
    if sender == target_user.username:
        return True
    if _is_blocked(db, sender, target_user.username):
        return False
    policy = _normalize_choice(target_user.message_privacy, {"everyone", "followers", "no_one"}, "everyone")
    if policy == "everyone":
        return True
    if policy == "followers":
        return _is_following(db, sender, target_user.username)
    return False


# Comment privacy rules
def _can_comment_on_post(db, actor_username: str, post: Post, post_owner: User | None) -> bool:
    actor = (actor_username or "").strip()
    owner_name = (post.username or "").strip()
    if actor == owner_name:
        return True
    if _is_blocked(db, actor, owner_name):
        return False
    policy = _normalize_choice(
        post_owner.comment_privacy if post_owner else "everyone",
        {"everyone", "followers", "following", "no_one"},
        "everyone",
    )
    if policy == "everyone":
        return True
    if policy == "followers":
        return _is_following(db, actor, owner_name)
    if policy == "following":
        return _is_following(db, owner_name, actor)
    return False


# Apply manual blur rectangles from user input
def _apply_manual_blur(img: np.ndarray, blur_regions: str) -> tuple[np.ndarray, int]:
    if not blur_regions:
        return img, 0

    try:
        regions = json.loads(blur_regions)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid blur_regions JSON.") from exc

    applied = 0
    for region in regions if isinstance(regions, list) else []:
        try:
            x = max(0, int(region.get("x", 0)))
            y = max(0, int(region.get("y", 0)))
            w = max(1, int(region.get("width", 0)))
            h = max(1, int(region.get("height", 0)))
        except (TypeError, ValueError):
            continue

        roi = img[y:y + h, x:x + w]
        if roi.size == 0:
            continue
        img[y:y + h, x:x + w] = cv2.GaussianBlur(roi, (51, 51), 0)
        applied += 1
    return img, applied


# Post visibility rules
def _can_view_post(post: Post, current_user: str, db) -> bool:
    owner_username = (post.username or "").strip()
    viewer_username = (current_user or "").strip()
    if _is_blocked(db, owner_username, viewer_username):
        return False
    owner = db.query(User).filter(User.username == owner_username).first()
    if owner and not _can_view_profile(owner, viewer_username, db):
        return False

    visibility = (post.visibility or "public").strip().lower()
    if visibility == "public":
        return True
    if viewer_username and viewer_username == owner_username:
        return True
    if visibility == "private":
        return False
    if visibility == "followers":
        return _is_following(db, viewer_username, owner_username)
    if visibility == "close_friends":
        return _is_close_friend(db, owner_username, viewer_username)
    return True


# Raise if viewer cannot access a post
def _ensure_post_access(post: Post, current_user: str, db) -> None:
    if not _can_view_post(post, current_user, db):
        raise HTTPException(status_code=403, detail="You do not have access to this post.")


# Run YOLO plate detector
def _predict_license_plate_regions(img: np.ndarray):
    if model is None:
        return []
    try:
        return model(img)
    except Exception:
        return []


# Convert Post ORM object into API response dict
def _serialize_post(post: Post, current_user: str, db) -> dict:
    likes = db.query(Like).filter(Like.post_id == post.id).all()
    comments = (
        db.query(Comment)
        .filter(Comment.post_id == post.id)
        .order_by(Comment.id.asc())
        .all()
    )
    saved = (
        db.query(SavedPost)
        .filter(SavedPost.post_id == post.id, SavedPost.username == current_user)
        .first()
        is not None
    )
    saved_count = db.query(SavedPost).filter(SavedPost.post_id == post.id).count()
    owner = db.query(User).filter(User.username == post.username).first()
    caption_public, visible_mentions, pending_mentions = _build_tag_visibility(post, current_user, db)
    return {
        "id": post.id,
        "username": post.username,
        "caption": post.caption,
        "caption_public": caption_public,
        "image_url": post.image_path,
        "visibility": post.visibility or "public",
        "hashtags": [tag for tag in (post.hashtags or "").split(",") if tag],
        "mentions": visible_mentions,
        "mentions_pending": pending_mentions,
        "risk_report": _safe_json_loads(post.risk_report, {}),
        "likes_count": len(likes),
        "liked_by_user": any(like.username == current_user for like in likes),
        "saved_count": saved_count,
        "saved_by_user": saved,
        "owner_profile": {
            "full_name": owner.full_name if owner else "",
            "bio": owner.bio if owner else "",
            "avatar_url": owner.avatar_url if owner else "",
        },
        "viewer_follows_owner": _is_following(db, current_user, post.username),
        "viewer_is_close_friend": _is_close_friend(db, post.username, current_user),
        "comments": [
            {
                "id": c.id,
                "username": c.username,
                "content": _build_comment_visibility(c, current_user, db),
                "sentiment": c.sentiment,
            }
            for c in comments
        ],
    }


# Embed message in image using LSB steganography
def _embed_message_lsb(img: np.ndarray, message: str) -> np.ndarray:
    payload = message.encode("utf-8") + STEGO_SENTINEL
    payload_bits = "".join(f"{byte:08b}" for byte in payload)
    flat = img.reshape(-1)

    if len(payload_bits) > flat.size:
        max_bytes = flat.size // 8
        raise ValueError(
            f"Message too long for this image. Max capacity is about {max_bytes} bytes."
        )

    bits = np.fromiter((int(bit) for bit in payload_bits), dtype=np.uint8)
    encoded_flat = flat.copy()
    encoded_flat[: len(bits)] = (encoded_flat[: len(bits)] & 254) | bits
    return encoded_flat.reshape(img.shape)


# Extract LSB stego message
def _extract_message_lsb(img: np.ndarray) -> str:
    sentinel_len = len(STEGO_SENTINEL)
    message_bytes = bytearray()
    current_byte = 0
    bit_count = 0

    for value in img.reshape(-1):
        current_byte = (current_byte << 1) | (int(value) & 1)
        bit_count += 1

        if bit_count == 8:
            message_bytes.append(current_byte)
            if len(message_bytes) >= sentinel_len and message_bytes[-sentinel_len:] == STEGO_SENTINEL:
                try:
                    return message_bytes[:-sentinel_len].decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise ValueError("Hidden payload exists but is not valid text.") from exc
            current_byte = 0
            bit_count = 0

    raise ValueError("No hidden message found in this image.")


# Quick check for hidden payload
def _has_stego_payload(img: np.ndarray) -> bool:
    has_hidden, _, _, _, _ = _analyze_steganography(img)
    return has_hidden


# Read raw LSB bytes (used for stego detection)
def _extract_lsb_bytes(img: np.ndarray, max_bytes: int = 4096) -> bytes:
    flat = img.reshape(-1)
    n_bits = min(flat.size, max_bytes * 8)
    if n_bits < 8:
        return b""

    bits = (flat[:n_bits] & 1).astype(np.uint8)
    n_complete_bits = (n_bits // 8) * 8
    bits = bits[:n_complete_bits]
    return np.packbits(bits).tobytes()


def _extract_lsb_bytes_with_offset(img: np.ndarray, offset: int, max_bytes: int = 4096) -> bytes:
    flat = img.reshape(-1)
    if offset < 0 or offset > 7 or flat.size <= offset:
        return b""
    bits = (flat & 1).astype(np.uint8)
    chunk = bits[offset:]
    n_complete_bits = (chunk.size // 8) * 8
    if n_complete_bits < 8:
        return b""
    raw = np.packbits(chunk[:n_complete_bits]).tobytes()
    if len(raw) > max_bytes:
        raw = raw[:max_bytes]
    return raw


def _find_lsb_marker_across_offsets(img: np.ndarray, markers: list[bytes], max_bytes: int = 4096) -> tuple[bytes | None, int | None]:
    for offset in range(8):
        raw = _extract_lsb_bytes_with_offset(img, offset, max_bytes=max_bytes)
        if not raw:
            continue
        upper = raw.upper()
        for marker in markers:
            if marker in upper:
                return marker, offset
    return None, None


def _find_printable_run_across_offsets(img: np.ndarray, max_bytes: int = 4096) -> tuple[bytes, int]:
    best = b""
    best_offset = 0
    for offset in range(8):
        raw = _extract_lsb_bytes_with_offset(img, offset, max_bytes=max_bytes)
        if not raw:
            continue
        run = _longest_printable_run(raw)
        if len(run) > len(best):
            best = run
            best_offset = offset
    return best, best_offset


# Find the longest printable ASCII run
def _longest_printable_run(data: bytes) -> bytes:
    best = b""
    current = bytearray()

    for b in data:
        if b in PRINTABLE_BYTES:
            current.append(b)
            if len(current) > len(best):
                best = bytes(current)
        else:
            current.clear()

    return best


# Heuristic: does a byte run look like text?
def _looks_like_text(run: bytes, min_letters: int) -> bool:
    if not run:
        return False
    letters = sum(1 for b in run if 65 <= b <= 90 or 97 <= b <= 122)
    return letters >= min_letters


# Strict scan: look for toxic keywords across all bit offsets
def _scan_lsb_for_toxic_keywords(img: np.ndarray, max_bytes: int = 16384) -> tuple[bool, list[str], str]:
    bits = (img.reshape(-1) & 1).astype(np.uint8)
    if bits.size < 8:
        return False, [], ""
    max_bits = min(bits.size, max_bytes * 8 + 7)
    bits = bits[:max_bits]
    for offset in range(8):
        chunk = bits[offset:]
        n_complete = (chunk.size // 8) * 8
        if n_complete < 8:
            continue
        raw = np.packbits(chunk[:n_complete]).tobytes()
        text = raw.decode("latin1", errors="ignore")
        is_dangerous, matches = _contains_dangerous_text(text)
        if is_dangerous:
            preview = text[:120]
            return True, matches, preview
    return False, [], ""


# Check if text contains any toxic keywords
def _contains_dangerous_text(text: str) -> tuple[bool, list[str]]:
    if not text:
        return False, []
    lowered = text.lower()
    matches = [word for word, pattern in TOXIC_PATTERNS.items() if pattern.search(lowered)]
    return len(matches) > 0, matches


# Analyze an image for hidden payloads (LSB + heuristics)
def _analyze_steganography(
    img: np.ndarray,
    min_printable_run: int = STEGO_DEFAULT_PRINTABLE_RUN,
    min_letters: int = STEGO_DEFAULT_MIN_LETTERS,
    strict_mode: bool = False,
) -> tuple[bool, bool, str, str, list[str]]:
    try:
        message = _extract_message_lsb(img)
        preview = message[:120]
        is_dangerous, matches = _contains_dangerous_text(message)
        reason = "Known LSB steganography payload detected."
        if is_dangerous:
            reason = "Dangerous hidden message detected in known LSB payload."
        return True, is_dangerous, reason, preview, matches
    except ValueError:
        pass

    lsb_bytes = _extract_lsb_bytes(img, max_bytes=4096)
    if not lsb_bytes:
        return False, False, "No hidden payload indicators found.", "", []

    if strict_mode:
        found_toxic, matches, preview = _scan_lsb_for_toxic_keywords(img)
        if found_toxic:
            return True, True, "Dangerous hidden text pattern found in LSB data.", preview, matches

    common_markers = [
        b"STEGO",
        b"HIDDEN",
        b"SECRET",
        b"PAYLOAD",
        b"BEGIN",
        b"END",
        b"EOF",
    ]
    marker_hit, _ = _find_lsb_marker_across_offsets(img, common_markers, max_bytes=4096)
    if marker_hit:
        return True, False, f"Suspicious marker '{marker_hit.decode()}' found in LSB data.", "", []

    longest_run, _ = _find_printable_run_across_offsets(img, max_bytes=4096)
    if len(longest_run) >= min_printable_run and _looks_like_text(longest_run, min_letters):
        preview = longest_run[:120].decode("ascii", errors="ignore")
        is_dangerous, matches = _contains_dangerous_text(preview)
        reason = "Suspicious printable text pattern found in LSB data."
        if is_dangerous:
            reason = "Dangerous hidden text pattern found in LSB data."
        return True, is_dangerous, reason, preview, matches

    return False, False, "No hidden payload indicators found.", "", []


# API: encode stego message into image
@app.post("/steganography/encode")
async def encode_steganography(
    file: UploadFile = File(...),
    message: str = Form(...),
):
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    image_bytes = await file.read()
    img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)

    if img is None:
        raise HTTPException(status_code=400, detail="Invalid image file.")

    try:
        encoded_img = _embed_message_lsb(img, message)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    success, buffer = cv2.imencode(".png", encoded_img)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to encode stego image.")

    return StreamingResponse(io.BytesIO(buffer.tobytes()), media_type="image/png")


# API: decode stego message from image
@app.post("/steganography/decode")
async def decode_steganography(file: UploadFile = File(...)):
    image_bytes = await file.read()
    img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)

    if img is None:
        raise HTTPException(status_code=400, detail="Invalid image file.")

    try:
        hidden_message = _extract_message_lsb(img)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"message": hidden_message}


# API: detect hidden payload without uploading a post
@app.post("/steganography/detect")
async def detect_steganography(
    file: UploadFile = File(...),
    username: str = Form("user"),
    strict: str = Form("0"),
):
    image_bytes = await file.read()
    img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)

    if img is None:
        raise HTTPException(status_code=400, detail="Invalid image file.")

    strict_enabled = str(strict).strip().lower() in {"1", "true", "yes", "on"}
    min_run = STEGO_STRICT_PRINTABLE_RUN if strict_enabled else STEGO_DEFAULT_PRINTABLE_RUN
    min_letters = STEGO_STRICT_MIN_LETTERS if strict_enabled else STEGO_DEFAULT_MIN_LETTERS
    has_hidden, is_dangerous, reason, preview, matches = _analyze_steganography(
        img,
        min_printable_run=min_run,
        min_letters=min_letters,
        strict_mode=strict_enabled,
    )
    db = SessionLocal()
    try:
        _store_stego_scan(
            db,
            username,
            file.filename or "",
            "blocked" if has_hidden else "clean",
            reason,
            preview,
            matches,
        )
        db.commit()
    finally:
        db.close()
    return {
        "has_hidden_message": has_hidden,
        "danger_detected": is_dangerous,
        "danger_keywords": matches,
        "verdict": "blocked" if has_hidden else "clean",
        "reason": reason,
        "preview": preview,
    }


AADHAAR_COMPACT_PATTERN = re.compile(r"^\d{12}$")
AADHAAR_GROUPED_PATTERN = re.compile(r"^\d{4}\s\d{4}\s\d{4}$")
CARD_COMPACT_PATTERN = re.compile(r"^\d{13,19}$")
CARD_EXPIRY_PATTERN = re.compile(r"^(0[1-9]|1[0-2])[\/-]\d{2,4}$")
CARD_KEYWORDS = {
    "card",
    "credit",
    "debit",
    "visa",
    "mastercard",
    "rupay",
    "maestro",
    "amex",
    "discover",
    "diners",
    "jcb",
    "cvv",
    "cvc",
    "expiry",
    "exp",
    "valid",
    "thru",
}


def _normalize_ocr_token(text: str) -> str:
    return re.sub(r"[^0-9]", "", text or "")


def _normalize_ocr_word(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").strip().lower())


def _build_aadhaar_box(ocr_data: dict, indexes: list[int]) -> tuple[int, int, int, int] | None:
    if not indexes:
        return None

    try:
        lefts = [int(ocr_data["left"][i]) for i in indexes]
        tops = [int(ocr_data["top"][i]) for i in indexes]
        widths = [int(ocr_data["width"][i]) for i in indexes]
        heights = [int(ocr_data["height"][i]) for i in indexes]
    except (KeyError, TypeError, ValueError, IndexError):
        return None

    x1 = min(lefts)
    y1 = min(tops)
    x2 = max(left + width for left, width in zip(lefts, widths))
    y2 = max(top + height for top, height in zip(tops, heights))
    return x1, y1, x2, y2


def _expand_box(
    box: tuple[int, int, int, int],
    image_shape: tuple[int, ...],
    pad_x: int,
    pad_y: int,
) -> tuple[int, int, int, int]:
    height, width = image_shape[:2]
    x1, y1, x2, y2 = box
    return (
        max(0, x1 - pad_x),
        max(0, y1 - pad_y),
        min(width, x2 + pad_x),
        min(height, y2 + pad_y),
    )


def _passes_luhn(number: str) -> bool:
    digits = [int(char) for char in number if char.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False

    checksum = 0
    parity = len(digits) % 2
    for idx, digit in enumerate(digits):
        if idx % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


def _is_card_context_token(text: str) -> bool:
    return _normalize_ocr_word(text) in CARD_KEYWORDS


def _is_expiry_token(text: str) -> bool:
    return CARD_EXPIRY_PATTERN.fullmatch((text or "").strip()) is not None


# OCR helpers: detect Aadhaar/card number regions
def _find_aadhaar_boxes(ocr_data: dict) -> list[tuple[int, int, int, int]]:
    texts = ocr_data.get("text", [])
    if not texts:
        return []

    boxes: list[tuple[int, int, int, int]] = []
    matched_indexes: set[int] = set()

    for idx, raw_text in enumerate(texts):
        token_digits = _normalize_ocr_token(raw_text)
        if len(token_digits) == 12 and AADHAAR_COMPACT_PATTERN.fullmatch(token_digits):
            box = _build_aadhaar_box(ocr_data, [idx])
            if box:
                boxes.append(box)
                matched_indexes.add(idx)

    total_tokens = len(texts)
    for idx in range(total_tokens - 2):
        group_indexes = [idx, idx + 1, idx + 2]
        if any(group_idx in matched_indexes for group_idx in group_indexes):
            continue

        group_tokens = [texts[group_idx].strip() for group_idx in group_indexes]
        group_digits = [_normalize_ocr_token(token) for token in group_tokens]
        if any(len(token) != 4 for token in group_digits):
            continue

        grouped_value = " ".join(group_digits)
        if not AADHAAR_GROUPED_PATTERN.fullmatch(grouped_value):
            continue

        box = _build_aadhaar_box(ocr_data, group_indexes)
        if box:
            boxes.append(box)
            matched_indexes.update(group_indexes)

    return boxes


# OCR helper: detect bank/card number regions
def _find_card_boxes(ocr_data: dict, image_shape: tuple[int, ...]) -> list[tuple[int, int, int, int]]:
    texts = ocr_data.get("text", [])
    if not texts:
        return []

    boxes: list[tuple[int, int, int, int]] = []
    matched_indexes: set[int] = set()
    total_tokens = len(texts)

    for start_idx in range(total_tokens):
        if start_idx in matched_indexes:
            continue

        combined_digits = ""
        group_indexes: list[int] = []
        for end_idx in range(start_idx, min(total_tokens, start_idx + 5)):
            token = texts[end_idx]
            digits = _normalize_ocr_token(token)
            if not digits:
                break
            if len(digits) > 6:
                break

            group_indexes.append(end_idx)
            combined_digits += digits
            if len(combined_digits) > 19:
                break
            if len(combined_digits) < 13:
                continue

            if not CARD_COMPACT_PATTERN.fullmatch(combined_digits):
                continue
            if not _passes_luhn(combined_digits):
                continue

            box = _build_aadhaar_box(ocr_data, group_indexes)
            if not box:
                continue

            x1, y1, x2, y2 = box
            nearby_indexes = [
                idx
                for idx, raw_text in enumerate(texts)
                if idx not in group_indexes
                and abs(int(ocr_data["top"][idx]) - y1) <= max(70, (y2 - y1) * 3)
                and abs(int(ocr_data["left"][idx]) - x1) <= max(220, (x2 - x1) * 2)
                and (_is_card_context_token(raw_text) or _is_expiry_token(raw_text))
            ]

            expanded_box = _expand_box(
                box,
                image_shape,
                pad_x=max(20, int((x2 - x1) * 0.12)),
                pad_y=max(20, int((y2 - y1) * 1.4)),
            )
            if nearby_indexes:
                context_box = _build_aadhaar_box(ocr_data, group_indexes + nearby_indexes)
                if context_box:
                    context_x1, context_y1, context_x2, context_y2 = context_box
                    expanded_box = _expand_box(
                        (context_x1, context_y1, context_x2, context_y2),
                        image_shape,
                        pad_x=max(20, int((context_x2 - context_x1) * 0.12)),
                        pad_y=max(20, int((context_y2 - context_y1) * 0.8)),
                    )

            boxes.append(expanded_box)
            matched_indexes.update(group_indexes)
            matched_indexes.update(nearby_indexes)
            break

    return boxes

# API: upload a new post (with stego + OCR + blur checks)
@app.post("/upload")
async def upload_image(
    file: UploadFile = File(...),
    hide: bool = Form(True),
    caption: str = Form(""),
    username: str = Form("user"),
    visibility: str = Form("public"),
    blur_regions: str = Form(""),
    stego_strict: str = Form("1"),
):
    clean_username = (username or "user").strip() or "user"
    image_bytes = await file.read()
    img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)

    if img is None:
        raise HTTPException(status_code=400, detail="Invalid image file.")

    db = SessionLocal()
    owner = db.query(User).filter(User.username == clean_username).first()
    if not owner:
        db.close()
        raise HTTPException(status_code=404, detail="User not found.")

    # Always enforce strict stego blocking on uploads.
    strict_enabled = True
    min_run = STEGO_STRICT_PRINTABLE_RUN if strict_enabled else STEGO_DEFAULT_PRINTABLE_RUN
    min_letters = STEGO_STRICT_MIN_LETTERS if strict_enabled else STEGO_DEFAULT_MIN_LETTERS
    has_hidden, is_dangerous, reason, _, matches = _analyze_steganography(
        img,
        min_printable_run=min_run,
        min_letters=min_letters,
        strict_mode=strict_enabled,
    )
    verdict = "clean"
    if has_hidden and (is_dangerous or strict_enabled):
        verdict = "blocked"
    elif has_hidden:
        verdict = "flagged"
    _store_stego_scan(
        db,
        clean_username,
        file.filename or "",
        verdict,
        reason,
        "",
        matches,
    )
    if has_hidden and (is_dangerous or strict_enabled):
        try:
            extra = ""
            if is_dangerous and matches:
                extra = f" Matched keywords: {', '.join(matches)}."
            if not is_dangerous:
                extra = " Hidden data detected (strict mode)."
            _log_moderation(db, clean_username, "upload", caption, "blocked", f"{reason}{extra}")
            db.commit()
        finally:
            db.close()
        raise HTTPException(status_code=400, detail=f"Upload blocked: {reason}{extra}")

    plate_detections = 0
    results = _predict_license_plate_regions(img)
    if hide:
        for r in results:
            if r.boxes is None:
                continue

            for box, cls in zip(r.boxes.xyxy, r.boxes.cls):
                if int(cls) == 0:  # license plate
                    x1, y1, x2, y2 = map(int, box)
                    roi = img[y1:y2, x1:x2]
                    if roi.size > 0:
                        roi = cv2.GaussianBlur(roi, (31, 31), 0)
                        img[y1:y2, x1:x2] = roi
                        plate_detections += 1

    # ---------------------------
    # 2️⃣ OCR TEXT DETECTION
    # ---------------------------
    aadhaar_boxes = 0
    card_boxes = 0
    try:
        ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        for x1, y1, x2, y2 in _find_aadhaar_boxes(ocr_data):
            roi = img[y1:y2, x1:x2]
            if roi.size > 0:
                img[y1:y2, x1:x2] = cv2.GaussianBlur(roi, (51, 51), 0)
                aadhaar_boxes += 1
        for x1, y1, x2, y2 in _find_card_boxes(ocr_data, img.shape):
            roi = img[y1:y2, x1:x2]
            if roi.size > 0:
                img[y1:y2, x1:x2] = cv2.GaussianBlur(roi, (51, 51), 0)
                card_boxes += 1
    except (pytesseract.TesseractNotFoundError, pytesseract.TesseractError):
        pass

    img, manual_blur_count = _apply_manual_blur(img, blur_regions)
    hashtags = _extract_tags(caption, "#")
    mentions = _extract_tags(caption, "@")
    normalized_visibility = _normalize_choice(
        visibility,
        {"public", "followers", "private", "close_friends"},
        "public",
    )

    risk_report = {
        "license_plate_found": plate_detections > 0,
        "license_plate_blurs": plate_detections,
        "license_plate_model_available": model is not None,
        "aadhaar_number_found": aadhaar_boxes > 0,
        "aadhaar_blurs": aadhaar_boxes,
        "card_number_found": card_boxes > 0,
        "card_blurs": card_boxes,
        "stego_suspicion_found": bool(has_hidden),
        "stego_reason": reason,
        "danger_keywords": matches,
        "manual_blur_regions": manual_blur_count,
    }

    # ---------------------------
    # SAVE IMAGE + POST
    # ---------------------------
    success, buffer = cv2.imencode(".png", img)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to process upload image.")

    filename = f"{uuid.uuid4().hex}.png"
    output_path = UPLOADS_DIR / filename
    output_path.write_bytes(buffer.tobytes())

    post = Post(
        image_path=f"/media/{filename}",
        username=clean_username,
        caption=caption.strip(),
        visibility=normalized_visibility,
        hashtags=",".join(hashtags),
        mentions=",".join(mentions),
        risk_report=json.dumps(risk_report),
    )
    try:
        db.add(post)
        db.flush()
        _log_moderation(db, clean_username, "upload", caption, "allowed", "Upload accepted")
        seen_mentions: set[str] = set()
        for mention in mentions:
            if mention in seen_mentions:
                continue
            seen_mentions.add(mention)
            if mention == clean_username:
                continue
            tagged_user = (
                db.query(User)
                .filter(func.lower(User.username) == mention.lower())
                .first()
            )
            if not tagged_user or not bool(tagged_user.tagged_post_approval):
                continue
            existing_tag = (
                db.query(TagRequest)
                .filter(
                    TagRequest.post_id == post.id,
                    TagRequest.comment_id.is_(None),
                    func.lower(TagRequest.tagged_username) == mention.lower(),
                )
                .first()
            )
            if existing_tag:
                existing_tag.status = "pending"
            else:
                db.add(
                    TagRequest(
                        post_id=post.id,
                        requester_username=clean_username,
                        tagged_username=mention,
                        status="pending",
                    )
                )
            _log_notification(
                db,
                mention,
                clean_username,
                "tag_request",
                f"{clean_username} tagged you in a post.",
            )
        db.commit()
        db.refresh(post)
        fresh_post = db.query(Post).filter(Post.id == post.id).first()
        return _serialize_post(fresh_post, clean_username, db)
    finally:
        db.close()
# ===============================
# NLP COMMENT MODERATION  ✅ ADD HERE
# ===============================

# Hash a password with PBKDF2
def _hash_password(password: str) -> str:
    salt = uuid.uuid4().hex
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        200000,
    ).hex()
    return f"{PASSWORD_HASH_PREFIX}${salt}${digest}"


# Verify password against stored hash (supports legacy SHA256)
def _verify_password(password: str, stored_hash: str) -> tuple[bool, bool]:
    if not stored_hash:
        return False, False

    if stored_hash.startswith(f"{PASSWORD_HASH_PREFIX}$"):
        parts = stored_hash.split("$", 2)
        if len(parts) != 3:
            return False, False
        _, salt, digest = parts
        computed = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            200000,
        ).hex()
        return hmac.compare_digest(computed, digest), False

    legacy_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(legacy_hash, stored_hash), True


# API: register a new user
@app.post("/auth/register")
def register_user(
    username: str = Form(...),
    password: str = Form(...),
):
    clean_username = (username or "").strip()
    if len(clean_username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters.")
    if len(password or "") < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters.")

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == clean_username).first()
        if existing:
            raise HTTPException(status_code=400, detail="Username already exists.")

        user = User(
            username=clean_username,
            password_hash=_hash_password(password),
            full_name=clean_username,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return {
            "message": "Account created successfully.",
            "username": user.username,
            "full_name": user.full_name or "",
            "bio": user.bio or "",
            "avatar_url": user.avatar_url or "",
            "privacy": {
                "is_private": bool(user.is_private),
                "profile_visibility": user.profile_visibility or "public",
                "message_privacy": user.message_privacy or "everyone",
                "comment_privacy": user.comment_privacy or "everyone",
                "activity_status_visible": bool(user.activity_status_visible),
                "read_receipts_enabled": bool(user.read_receipts_enabled),
                "tagged_post_approval": bool(user.tagged_post_approval),
            },
        }
    finally:
        db.close()


# API: login
@app.post("/auth/login")
def login_user(
    username: str = Form(...),
    password: str = Form(...),
):
    clean_username = (username or "").strip()
    if not clean_username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required.")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == clean_username).first()
        verified, needs_upgrade = _verify_password(password, user.password_hash if user else "")
        if not user or not verified:
            raise HTTPException(status_code=401, detail="Invalid username or password.")

        if needs_upgrade:
            user.password_hash = _hash_password(password)
            db.commit()
            db.refresh(user)

        return {
            "message": "Login successful.",
            "username": user.username,
            "full_name": user.full_name or "",
            "bio": user.bio or "",
            "avatar_url": user.avatar_url or "",
            "privacy": {
                "is_private": bool(user.is_private),
                "profile_visibility": user.profile_visibility or "public",
                "message_privacy": user.message_privacy or "everyone",
                "comment_privacy": user.comment_privacy or "everyone",
                "activity_status_visible": bool(user.activity_status_visible),
                "read_receipts_enabled": bool(user.read_receipts_enabled),
                "tagged_post_approval": bool(user.tagged_post_approval),
            },
        }
    finally:
        db.close()


# API: view profile + posts
@app.get("/profile/{username}")
def get_profile(username: str, viewer: str = ""):
    clean_username = (username or "").strip()
    viewer_username = (viewer or "").strip()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == clean_username).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if _is_blocked(db, clean_username, viewer_username):
            raise HTTPException(status_code=403, detail="Profile is unavailable.")

        posts = db.query(Post).filter(Post.username == clean_username).order_by(desc(Post.id)).all()
        visible_posts = [post for post in posts if _can_view_post(post, viewer_username, db)]
        followers_count = db.query(Follow).filter(Follow.following_username == clean_username).count()
        following_count = db.query(Follow).filter(Follow.follower_username == clean_username).count()
        is_following = _is_following(db, viewer_username, clean_username)
        pending_request = _get_pending_follow_request(db, viewer_username, clean_username)
        can_view_profile = _can_view_profile(user, viewer_username, db)
        details_visibility = _normalize_choice(
            user.profile_visibility,
            {"public", "followers", "private"},
            "public",
        )
        viewer_is_owner = clean_username == viewer_username
        can_view_details = viewer_is_owner or details_visibility == "public"
        if details_visibility == "followers" and is_following:
            can_view_details = True
        if details_visibility == "private" and viewer_is_owner:
            can_view_details = True

        return {
            "username": user.username,
            "full_name": (user.full_name or "") if can_view_details else "",
            "bio": (user.bio or "") if can_view_details else "",
            "avatar_url": user.avatar_url or "",
            "followers_count": followers_count if can_view_details else 0,
            "following_count": following_count if can_view_details else 0,
            "is_following": is_following,
            "is_private": bool(user.is_private),
            "profile_access": can_view_profile,
            "profile_details_visible": can_view_details,
            "has_pending_follow_request": pending_request is not None,
            "posts": [_serialize_post(post, viewer_username, db) for post in visible_posts] if can_view_profile else [],
            "privacy": {
                "profile_visibility": details_visibility,
                "message_privacy": user.message_privacy or "everyone",
                "comment_privacy": user.comment_privacy or "everyone",
                "activity_status_visible": bool(user.activity_status_visible),
                "read_receipts_enabled": bool(user.read_receipts_enabled),
                "tagged_post_approval": bool(user.tagged_post_approval),
            } if viewer_is_owner else {},
        }
    finally:
        db.close()


# API: update profile + privacy settings
@app.post("/profile/update")
def update_profile(
    username: str = Form(...),
    full_name: str = Form(""),
    bio: str = Form(""),
    avatar_url: str = Form(""),
    is_private: str = Form("0"),
    profile_visibility: str = Form("public"),
    message_privacy: str = Form("everyone"),
    comment_privacy: str = Form("everyone"),
    activity_status_visible: str = Form("1"),
    read_receipts_enabled: str = Form("1"),
    tagged_post_approval: str = Form("1"),
):
    clean_username = (username or "").strip()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == clean_username).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user.full_name = (full_name or "").strip()
        user.bio = (bio or "").strip()
        user.avatar_url = (avatar_url or "").strip()
        user.is_private = 1 if str(is_private).strip().lower() in {"1", "true", "yes", "on"} else 0
        user.profile_visibility = _normalize_choice(profile_visibility, {"public", "followers", "private"}, "public")
        user.message_privacy = _normalize_choice(message_privacy, {"everyone", "followers", "no_one"}, "everyone")
        user.comment_privacy = _normalize_choice(comment_privacy, {"everyone", "followers", "following", "no_one"}, "everyone")
        user.activity_status_visible = 1 if str(activity_status_visible).strip().lower() in {"1", "true", "yes", "on"} else 0
        user.read_receipts_enabled = 1 if str(read_receipts_enabled).strip().lower() in {"1", "true", "yes", "on"} else 0
        user.tagged_post_approval = 1 if str(tagged_post_approval).strip().lower() in {"1", "true", "yes", "on"} else 0
        db.commit()
        db.refresh(user)

        return {
            "username": user.username,
            "full_name": user.full_name or "",
            "bio": user.bio or "",
            "avatar_url": user.avatar_url or "",
            "privacy": {
                "is_private": bool(user.is_private),
                "profile_visibility": user.profile_visibility or "public",
                "message_privacy": user.message_privacy or "everyone",
                "comment_privacy": user.comment_privacy or "everyone",
                "activity_status_visible": bool(user.activity_status_visible),
                "read_receipts_enabled": bool(user.read_receipts_enabled),
                "tagged_post_approval": bool(user.tagged_post_approval),
            },
        }
    finally:
        db.close()


BAD_WORDS = [
    "fuck", "shit", "bitch", "asshole",
    "bastard", "idiot", "stupid","hell","whore"
]

# Translate to English for consistent toxicity checks
def _translate_to_english(text: str) -> str:
    try:
        translated = translator.translate(text, dest="en")
        if inspect.isawaitable(translated):
            translated = asyncio.run(translated)
        return getattr(translated, "text", text)
    except Exception:
        return text

# Moderate comment text (language detect + toxicity + sentiment)
def moderate_comment(comment: str):
    original_text = (comment or "").strip()

    if not original_text:
        return {
            "status": "blocked",
            "reason": "Comment cannot be empty.",
            "language": "unknown",
        }

    try:
        lang = detect(original_text)
    except Exception:
        lang = "en"

    # 🔹 Translate to English if needed
    if lang != "en":
        text = _translate_to_english(original_text).lower()
    else:
        text = original_text.lower()

    # 🔹 Vulgar word filtering
    for word in BAD_WORDS:
        if word in text:
            return {
                "status": "blocked",
                "reason": "Vulgar language detected",
                "language": lang
            }

    # 🔹 Sentiment Analysis
    blob = TextBlob(text)
    polarity = blob.sentiment.polarity

    if polarity > 0.2:
        sentiment = "positive"
    elif polarity < -0.2:
        sentiment = "negative"
    else:
        sentiment = "neutral"

    return {
        "status": "allowed",
        "sentiment": sentiment,
        "language": lang
    }


@app.post("/check_comment")
def check_comment(comment: str = Form(...), username: str = Form("user")):
    moderation = moderate_comment(comment)
    db = SessionLocal()
    try:
        _log_moderation(
            db,
            username,
            "comment",
            comment,
            moderation.get("status", "unknown"),
            moderation.get("reason", moderation.get("sentiment", "")),
        )
        db.commit()
    finally:
        db.close()
    return moderation


# API: fetch feed posts (all or following)
@app.get("/posts")
def get_posts(username: str = "", feed_mode: str = "all"):
    current_user = (username or "").strip()
    db = SessionLocal()
    try:
        posts = db.query(Post).order_by(desc(Post.id)).all()
        followed = {
            row.following_username
            for row in db.query(Follow).filter(Follow.follower_username == current_user).all()
        }
        payload = []
        for post in posts:
            if not _can_view_post(post, current_user, db):
                continue
            if feed_mode == "following" and post.username not in followed and post.username != current_user:
                continue
            payload.append(_serialize_post(post, current_user, db))
        return payload
    finally:
        db.close()


# API: privacy overview + requests
@app.get("/privacy/overview")
def get_privacy_overview(username: str):
    clean_username = (username or "").strip()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == clean_username).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        follow_requests = (
            db.query(FollowRequest)
            .filter(FollowRequest.target_username == clean_username, FollowRequest.status == "pending")
            .order_by(desc(FollowRequest.id))
            .all()
        )
        blocked_users = (
            db.query(UserBlock)
            .filter(UserBlock.blocker_username == clean_username)
            .order_by(desc(UserBlock.id))
            .all()
        )
        close_friends = (
            db.query(CloseFriend)
            .filter(CloseFriend.username == clean_username)
            .order_by(desc(CloseFriend.id))
            .all()
        )
        tag_requests = (
            db.query(TagRequest)
            .filter(
                func.lower(TagRequest.tagged_username) == clean_username.lower(),
                TagRequest.status == "pending",
            )
            .order_by(desc(TagRequest.id))
            .all()
        )
        tag_request_payload = []
        for row in tag_requests:
            caption_preview = ""
            if row.comment_id:
                comment = db.query(Comment).filter(Comment.id == row.comment_id).first()
                if comment:
                    caption_preview = (comment.content or "").strip()
                    if caption_preview:
                        caption_preview = f"Comment: {caption_preview}"
            else:
                post = db.query(Post).filter(Post.id == row.post_id).first()
                caption_preview = (post.caption or "").strip() if post else ""
            if len(caption_preview) > 120:
                caption_preview = f"{caption_preview[:120]}..."
            tag_request_payload.append(
                {
                    "post_id": row.post_id,
                    "comment_id": row.comment_id,
                    "requester_username": row.requester_username,
                    "caption_preview": caption_preview,
                }
            )

        return {
            "privacy": {
                "is_private": bool(user.is_private),
                "profile_visibility": user.profile_visibility or "public",
                "message_privacy": user.message_privacy or "everyone",
                "comment_privacy": user.comment_privacy or "everyone",
                "activity_status_visible": bool(user.activity_status_visible),
                "read_receipts_enabled": bool(user.read_receipts_enabled),
                "tagged_post_approval": bool(user.tagged_post_approval),
            },
            "follow_requests": [
                {"requester_username": row.requester_username, "status": row.status}
                for row in follow_requests
            ],
            "tag_requests": tag_request_payload,
            "blocked_users": [row.blocked_username for row in blocked_users],
            "close_friends": [row.close_friend_username for row in close_friends],
        }
    finally:
        db.close()


# API: saved posts list
@app.get("/saved-posts")
def get_saved_posts(username: str):
    clean_username = (username or "").strip()
    db = SessionLocal()
    try:
        saved_rows = (
            db.query(SavedPost)
            .filter(SavedPost.username == clean_username)
            .order_by(desc(SavedPost.id))
            .all()
        )
        posts = []
        for row in saved_rows:
            post = db.query(Post).filter(Post.id == row.post_id).first()
            if post and _can_view_post(post, clean_username, db):
                posts.append(_serialize_post(post, clean_username, db))
        return posts
    finally:
        db.close()


# API: search users/posts/comments
@app.get("/search")
def search_content(q: str = "", username: str = ""):
    term = (q or "").strip().lower()
    # Allow hashtag/mention-style queries like "#topic" or "@user"
    term = term.lstrip("#@").strip()
    current_user = (username or "").strip()
    db = SessionLocal()
    try:
        users = db.query(User).all()
        posts = db.query(Post).order_by(desc(Post.id)).all()
        comments = db.query(Comment).order_by(desc(Comment.id)).all()

        matching_users = [
            {
                "username": user.username,
                "full_name": user.full_name or "",
                "bio": user.bio or "",
                "avatar_url": user.avatar_url or "",
                "is_private": bool(user.is_private),
            }
            for user in users
            if term and (
                _can_view_profile(user, current_user, db)
                and
                (
                term in (user.username or "").lower()
                or term in (user.full_name or "").lower()
                or term in (user.bio or "").lower()
                )
            )
        ]

        matching_posts = []
        for post in posts:
            if not term or not _can_view_post(post, current_user, db):
                continue
            caption_public, visible_mentions, _ = _build_tag_visibility(post, current_user, db)
            mention_blob = ",".join(visible_mentions).lower()
            if (
                term in (caption_public or "").lower()
                or term in (post.hashtags or "").lower()
                or term in mention_blob
            ):
                matching_posts.append(_serialize_post(post, current_user, db))

        matching_comments = []
        for comment in comments:
            if not term:
                continue
            post = db.query(Post).filter(Post.id == comment.post_id).first()
            if post is None or not _can_view_post(post, current_user, db):
                continue
            safe_content = _build_comment_visibility(comment, current_user, db)
            if term in (safe_content or "").lower():
                matching_comments.append(
                    {
                        "post_id": comment.post_id,
                        "username": comment.username,
                        "content": safe_content,
                        "sentiment": comment.sentiment,
                    }
                )

        return {
            "users": matching_users,
            "posts": matching_posts,
            "comments": matching_comments,
        }
    finally:
        db.close()


# API: toggle like
@app.post("/posts/{post_id}/like")
def toggle_like(post_id: int, username: str = Form(...)):
    clean_username = (username or "").strip()
    if not clean_username:
        raise HTTPException(status_code=400, detail="Username is required.")

    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        _ensure_post_access(post, clean_username, db)

        existing_like = (
            db.query(Like)
            .filter(Like.post_id == post_id, Like.username == clean_username)
            .first()
        )

        liked = False
        if existing_like:
            db.delete(existing_like)
        else:
            db.add(Like(post_id=post_id, username=clean_username))
            _log_notification(
                db,
                post.username,
                clean_username,
                "like",
                f"{clean_username} liked your post.",
            )
            liked = True

        db.commit()
        likes_count = db.query(Like).filter(Like.post_id == post_id).count()

        return {
            "post_id": post_id,
            "liked": liked,
            "likes_count": likes_count,
        }
    finally:
        db.close()


# API: toggle save/bookmark
@app.post("/posts/{post_id}/save")
def toggle_save(post_id: int, username: str = Form(...)):
    clean_username = (username or "").strip()
    if not clean_username:
        raise HTTPException(status_code=400, detail="Username is required.")

    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        _ensure_post_access(post, clean_username, db)

        existing_save = (
            db.query(SavedPost)
            .filter(SavedPost.post_id == post_id, SavedPost.username == clean_username)
            .first()
        )
        saved = False
        if existing_save:
            db.delete(existing_save)
        else:
            db.add(SavedPost(post_id=post_id, username=clean_username))
            saved = True
        db.commit()
        saved_count = db.query(SavedPost).filter(SavedPost.post_id == post_id).count()
        return {"post_id": post_id, "saved": saved, "saved_count": saved_count}
    finally:
        db.close()


# API: follow/unfollow (and requests if private)
@app.post("/follow")
def toggle_follow(
    follower_username: str = Form(...),
    following_username: str = Form(...),
):
    follower = (follower_username or "").strip()
    following = (following_username or "").strip()
    if not follower or not following:
        raise HTTPException(status_code=400, detail="Both usernames are required.")
    if follower == following:
        raise HTTPException(status_code=400, detail="You cannot follow yourself.")

    db = SessionLocal()
    try:
        actor = db.query(User).filter(User.username == follower).first()
        if not actor:
            raise HTTPException(status_code=404, detail="Follower user not found")

        target_user = db.query(User).filter(User.username == following).first()
        if not target_user:
            raise HTTPException(status_code=404, detail="Target user not found")
        if _is_blocked(db, follower, following):
            raise HTTPException(status_code=403, detail="Follow is unavailable for this account.")

        existing_follow = (
            db.query(Follow)
            .filter(
                Follow.follower_username == follower,
                Follow.following_username == following,
            )
            .first()
        )
        is_following = False
        request_status = "none"
        if existing_follow:
            db.delete(existing_follow)
            db.query(FollowRequest).filter(
                FollowRequest.requester_username == follower,
                FollowRequest.target_username == following,
            ).delete()
        else:
            if bool(target_user.is_private):
                pending_request = _get_pending_follow_request(db, follower, following)
                if pending_request:
                    db.delete(pending_request)
                    request_status = "none"
                else:
                    db.add(FollowRequest(requester_username=follower, target_username=following, status="pending"))
                    _log_notification(
                        db,
                        following,
                        follower,
                        "follow_request",
                        f"{follower} requested to follow you.",
                    )
                    request_status = "pending"
            else:
                db.add(Follow(follower_username=follower, following_username=following))
                _log_notification(
                    db,
                    following,
                    follower,
                    "follow",
                    f"{follower} started following you.",
                )
                is_following = True
                request_status = "approved"
        db.commit()

        followers_count = db.query(Follow).filter(Follow.following_username == following).count()
        following_count = db.query(Follow).filter(Follow.follower_username == follower).count()
        return {
            "following_username": following,
            "is_following": is_following,
            "request_status": request_status,
            "followers_count": followers_count,
            "following_count": following_count,
        }
    finally:
        db.close()


# API: list follow requests
@app.get("/follow-requests")
def get_follow_requests(username: str):
    clean_username = (username or "").strip()
    db = SessionLocal()
    try:
        rows = (
            db.query(FollowRequest)
            .filter(FollowRequest.target_username == clean_username, FollowRequest.status == "pending")
            .order_by(desc(FollowRequest.id))
            .all()
        )
        return [
            {
                "id": row.id,
                "requester_username": row.requester_username,
                "target_username": row.target_username,
                "status": row.status,
            }
            for row in rows
        ]
    finally:
        db.close()


# API: respond to follow request
@app.post("/follow-requests/respond")
def respond_follow_request(
    username: str = Form(...),
    requester_username: str = Form(...),
    action: str = Form(...),
):
    target = (username or "").strip()
    requester = (requester_username or "").strip()
    clean_action = _normalize_choice(action, {"approve", "reject"}, "reject")
    db = SessionLocal()
    try:
        row = _get_pending_follow_request(db, requester, target)
        if not row:
            raise HTTPException(status_code=404, detail="Follow request not found.")
        row.status = clean_action
        if clean_action == "approve":
            if not _is_following(db, requester, target):
                db.add(Follow(follower_username=requester, following_username=target))
            _log_notification(
                db,
                requester,
                target,
                "follow_request_approved",
                f"{target} approved your follow request.",
            )
        else:
            _log_notification(
                db,
                requester,
                target,
                "follow_request_rejected",
                f"{target} rejected your follow request.",
            )
        db.commit()
        followers_count = db.query(Follow).filter(Follow.following_username == target).count()
        return {"status": clean_action, "followers_count": followers_count}
    finally:
        db.close()


# API: approve/reject tag request
@app.post("/tags/respond")
def respond_tag_request(
    username: str = Form(...),
    post_id: int = Form(...),
    action: str = Form(...),
    comment_id: Optional[int] = Form(None),
):
    clean_username = (username or "").strip()
    clean_action = _normalize_choice(action, {"approve", "reject"}, "reject")
    db = SessionLocal()
    try:
        query = db.query(TagRequest).filter(
            func.lower(TagRequest.tagged_username) == clean_username.lower()
        )
        if comment_id is not None:
            query = query.filter(TagRequest.comment_id == comment_id)
        else:
            query = query.filter(TagRequest.post_id == post_id, TagRequest.comment_id.is_(None))
        row = query.first()
        if not row:
            raise HTTPException(status_code=404, detail="Tag request not found.")
        row.status = clean_action
        if clean_action == "approve":
            _log_notification(
                db,
                row.requester_username,
                clean_username,
                "tag_approved",
                f"{clean_username} approved your tag.",
            )
        else:
            _log_notification(
                db,
                row.requester_username,
                clean_username,
                "tag_rejected",
                f"{clean_username} hid your tag.",
            )
        db.commit()
        return {"status": clean_action}
    finally:
        db.close()


# API: block/unblock user
@app.post("/privacy/block")
def toggle_block(
    username: str = Form(...),
    target_username: str = Form(...),
):
    blocker = (username or "").strip()
    blocked = (target_username or "").strip()
    if not blocker or not blocked or blocker == blocked:
        raise HTTPException(status_code=400, detail="A valid target is required.")
    db = SessionLocal()
    try:
        existing = (
            db.query(UserBlock)
            .filter(UserBlock.blocker_username == blocker, UserBlock.blocked_username == blocked)
            .first()
        )
        blocked_now = False
        if existing:
            db.delete(existing)
        else:
            db.add(UserBlock(blocker_username=blocker, blocked_username=blocked))
            db.query(Follow).filter(
                or_(
                    (Follow.follower_username == blocker) & (Follow.following_username == blocked),
                    (Follow.follower_username == blocked) & (Follow.following_username == blocker),
                )
            ).delete(synchronize_session=False)
            db.query(FollowRequest).filter(
                or_(
                    (FollowRequest.requester_username == blocker) & (FollowRequest.target_username == blocked),
                    (FollowRequest.requester_username == blocked) & (FollowRequest.target_username == blocker),
                )
            ).delete(synchronize_session=False)
            blocked_now = True
        db.commit()
        return {"target_username": blocked, "blocked": blocked_now}
    finally:
        db.close()


# API: toggle close friend
@app.post("/privacy/close-friends")
def toggle_close_friend(
    username: str = Form(...),
    target_username: str = Form(...),
):
    owner = (username or "").strip()
    target = (target_username or "").strip()
    if not owner or not target or owner == target:
        raise HTTPException(status_code=400, detail="A valid target is required.")
    db = SessionLocal()
    try:
        if _is_blocked(db, owner, target):
            raise HTTPException(status_code=403, detail="Blocked users cannot be added to close friends.")
        existing = (
            db.query(CloseFriend)
            .filter(CloseFriend.username == owner, CloseFriend.close_friend_username == target)
            .first()
        )
        active = False
        if existing:
            db.delete(existing)
        else:
            db.add(CloseFriend(username=owner, close_friend_username=target))
            active = True
        db.commit()
        return {"target_username": target, "is_close_friend": active}
    finally:
        db.close()


# API: notifications list
@app.get("/notifications")
def get_notifications(username: str):
    clean_username = (username or "").strip()
    db = SessionLocal()
    try:
        notifications = (
            db.query(Notification)
            .filter(Notification.username == clean_username)
            .order_by(desc(Notification.id))
            .all()
        )
        return [
            {
                "id": item.id,
                "actor_username": item.actor_username,
                "event_type": item.event_type,
                "message": item.message,
                "is_read": bool(item.is_read),
            }
            for item in notifications
        ]
    finally:
        db.close()


# API: mark notifications read
@app.post("/notifications/read-all")
def mark_notifications_read(username: str = Form(...)):
    clean_username = (username or "").strip()
    db = SessionLocal()
    try:
        db.query(Notification).filter(Notification.username == clean_username).update({"is_read": 1})
        db.commit()
        return {"status": "ok"}
    finally:
        db.close()


# API: moderation logs
@app.get("/moderation/logs")
def get_moderation_logs(username: str = ""):
    clean_username = (username or "").strip()
    db = SessionLocal()
    try:
        query = db.query(ModerationLog).order_by(desc(ModerationLog.id))
        if clean_username:
            query = query.filter(ModerationLog.username == clean_username)
        rows = query.all()
        return [
            {
                "id": row.id,
                "username": row.username,
                "target_type": row.target_type,
                "content": row.content,
                "status": row.status,
                "reason": row.reason,
            }
            for row in rows
        ]
    finally:
        db.close()


# API: stego history
@app.get("/stego/history")
def get_stego_history(username: str = ""):
    clean_username = (username or "").strip()
    db = SessionLocal()
    try:
        query = db.query(StegoScan).order_by(desc(StegoScan.id))
        if clean_username:
            query = query.filter(StegoScan.username == clean_username)
        rows = query.all()
        return [
            {
                "id": row.id,
                "username": row.username,
                "filename": row.filename,
                "verdict": row.verdict,
                "reason": row.reason,
                "preview": row.preview,
                "danger_keywords": row.danger_keywords,
            }
            for row in rows
        ]
    finally:
        db.close()


# API: list messages (all or by peer)
@app.get("/messages")
def get_messages(username: str, peer: str = ""):
    clean_username = (username or "").strip()
    clean_peer = (peer or "").strip()
    db = SessionLocal()
    try:
        query = db.query(Message).order_by(Message.id.asc())
        if clean_peer:
            if _is_blocked(db, clean_username, clean_peer):
                raise HTTPException(status_code=403, detail="Conversation unavailable.")
            query = query.filter(
                or_(
                    (Message.sender_username == clean_username) & (Message.receiver_username == clean_peer),
                    (Message.sender_username == clean_peer) & (Message.receiver_username == clean_username),
                )
            )
        else:
            query = query.filter(
                or_(Message.sender_username == clean_username, Message.receiver_username == clean_username)
            )
        rows = query.all()
        peer_user = db.query(User).filter(User.username == clean_peer).first() if clean_peer else None
        return [
            {
                "id": row.id,
                "sender_username": row.sender_username,
                "receiver_username": row.receiver_username,
                "content": row.content,
                "is_seen": bool(row.is_seen) if (peer_user and bool(peer_user.read_receipts_enabled)) or row.sender_username == clean_username else False,
            }
            for row in rows
        ]
    finally:
        db.close()


# API: send message
@app.post("/messages")
def send_message(
    sender_username: str = Form(...),
    receiver_username: str = Form(...),
    content: str = Form(...),
):
    sender = (sender_username or "").strip()
    receiver = (receiver_username or "").strip()
    body = (content or "").strip()
    if not sender or not receiver or not body:
        raise HTTPException(status_code=400, detail="Sender, receiver, and content are required.")

    db = SessionLocal()
    try:
        sender_user = db.query(User).filter(User.username == sender).first()
        if not sender_user:
            raise HTTPException(status_code=404, detail="Sender not found")

        target_user = db.query(User).filter(User.username == receiver).first()
        if not target_user:
            raise HTTPException(status_code=404, detail="Receiver not found")
        if not _can_send_message_to(db, sender, target_user):
            raise HTTPException(status_code=403, detail="Receiver privacy settings do not allow messages from you.")

        message = Message(
            sender_username=sender,
            receiver_username=receiver,
            content=body,
        )
        db.add(message)
        _log_notification(
            db,
            receiver,
            sender,
            "message",
            f"New message from {sender}.",
        )
        db.commit()
        db.refresh(message)
        return {
            "id": message.id,
            "sender_username": message.sender_username,
            "receiver_username": message.receiver_username,
            "content": message.content,
            "is_seen": False,
        }
    finally:
        db.close()


# API: mark messages as seen
@app.post("/messages/read")
def mark_messages_seen(username: str = Form(...), peer: str = Form(...)):
    clean_username = (username or "").strip()
    clean_peer = (peer or "").strip()
    db = SessionLocal()
    try:
        db.query(Message).filter(
            Message.sender_username == clean_peer,
            Message.receiver_username == clean_username,
        ).update({"is_seen": 1})
        db.commit()
        return {"status": "ok"}
    finally:
        db.close()


# API: add comment with moderation
@app.post("/posts/{post_id}/comments")
def add_comment(
    post_id: int,
    comment: str = Form(...),
    username: str = Form("user"),
):
    moderation = moderate_comment(comment)
    clean_username = (username or "user").strip() or "user"

    db = SessionLocal()
    try:
        if moderation["status"] == "blocked":
            _log_moderation(
                db,
                clean_username,
                "comment",
                comment,
                "blocked",
                moderation.get("reason", "Comment blocked"),
            )
            db.commit()
            raise HTTPException(status_code=400, detail=moderation.get("reason", "Comment blocked"))

        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        _ensure_post_access(post, clean_username, db)
        post_owner = db.query(User).filter(User.username == post.username).first()
        if not _can_comment_on_post(db, clean_username, post, post_owner):
            raise HTTPException(status_code=403, detail="Comment privacy prevents commenting on this post.")

        new_comment = Comment(
            post_id=post_id,
            username=clean_username,
            content=comment.strip(),
            sentiment=moderation["sentiment"],
        )
        db.add(new_comment)
        db.flush()
        _log_moderation(db, clean_username, "comment", comment, "allowed", moderation["sentiment"])
        _log_notification(
            db,
            post.username,
            clean_username,
            "comment",
            f"{clean_username} commented on your post.",
        )
        comment_mentions = _extract_tags(comment, "@")
        for mention in comment_mentions:
            if mention == clean_username:
                continue
            tagged_user = (
                db.query(User)
                .filter(func.lower(User.username) == mention.lower())
                .first()
            )
            if not tagged_user or not bool(tagged_user.tagged_post_approval):
                continue
            existing_tag = (
                db.query(TagRequest)
                .filter(
                    TagRequest.comment_id == new_comment.id,
                    func.lower(TagRequest.tagged_username) == mention.lower(),
                )
                .first()
            )
            if existing_tag:
                existing_tag.status = "pending"
            else:
                db.add(
                    TagRequest(
                        post_id=post_id,
                        comment_id=new_comment.id,
                        requester_username=clean_username,
                        tagged_username=mention,
                        status="pending",
                    )
                )
            _log_notification(
                db,
                mention,
                clean_username,
                "tag_request",
                f"{clean_username} tagged you in a comment.",
            )
        db.commit()
        db.refresh(new_comment)

        return {
            "id": new_comment.id,
            "post_id": post_id,
            "username": new_comment.username,
            "content": new_comment.content,
            "sentiment": new_comment.sentiment,
        }
    finally:
        db.close()


# API: delete post (owner only)
@app.delete("/posts/{post_id}")
def delete_post(post_id: int, username: str = "user"):
    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")

        request_user = (username or "").strip() or "user"
        post_owner = (post.username or "").strip()
        if post_owner != request_user:
            raise HTTPException(status_code=403, detail="You can delete only your own posts.")

        image_name = Path(post.image_path or "").name
        image_path = UPLOADS_DIR / image_name if image_name else None

        db.query(Comment).filter(Comment.post_id == post_id).delete()
        db.query(Like).filter(Like.post_id == post_id).delete()
        db.query(SavedPost).filter(SavedPost.post_id == post_id).delete()
        db.delete(post)
        db.commit()

        if image_path and image_path.exists():
            image_path.unlink()

        return {"status": "deleted", "post_id": post_id}
    finally:
        db.close()
