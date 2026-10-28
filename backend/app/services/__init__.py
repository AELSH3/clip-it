import re
import shutil
import uuid
from pathlib import Path

from app.config import get_settings
from app.errors import AppError

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}
_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_FRAME = re.compile(r"^frames/frame_\d{4}\.jpg$")


def storage_root() -> Path:
    root = get_settings().storage_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def sanitize_filename(name: str | None) -> str:
    base = Path(name or "").name
    cleaned = "".join(ch for ch in base if ch.isprintable() and ch not in "/\\")
    cleaned = cleaned.strip().lstrip(".")
    return cleaned[:200] or "video"


def extension_for(name: str | None) -> str:
    suffix = Path(sanitize_filename(name)).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise AppError(
            400,
            "unsupported_type",
            "Upload an mp4, mov, m4v, webm, mkv, or avi file.",
        )
    return suffix


def ensure_size(num_bytes: int) -> None:
    limit = get_settings().max_upload_bytes
    if num_bytes > limit:
        raise AppError(413, "file_too_large", f"Files must be {limit // (1024 * 1024)} MB or smaller.")
    if num_bytes <= 0:
        raise AppError(400, "empty_file", "The uploaded file is empty.")


def video_dir(video_id: uuid.UUID | str) -> Path:
    token = str(video_id)
    if not _UUID.fullmatch(token):
        raise AppError(400, "bad_id", "Video id is not valid.")
    root = storage_root()
    path = (root / "videos" / token).resolve()
    if not path.is_relative_to(root):
        raise AppError(400, "bad_path", "Storage path escaped the data directory.")
    return path


def safe_frame(video_id: uuid.UUID, relpath: str) -> Path:
    if relpath != "thumb.jpg" and not _FRAME.fullmatch(relpath):
        raise AppError(404, "not_found", "That preview does not exist.")
    path = (video_dir(video_id) / relpath).resolve()
    if not path.is_relative_to(video_dir(video_id)):
        raise AppError(400, "bad_path", "Preview path escaped the video directory.")
    if not path.is_file():
        raise AppError(404, "not_found", "That preview does not exist.")
    return path


def remove_video_files(video_id: uuid.UUID) -> None:
    path = video_dir(video_id)
    if path.exists():
        shutil.rmtree(path)


def media_type_for(extension: str) -> str:
    return {
        ".mp4": "video/mp4",
        ".m4v": "video/mp4",
        ".mov": "video/quicktime",
        ".webm": "video/webm",
        ".mkv": "video/x-matroska",
        ".avi": "video/x-msvideo",
    }.get(extension.lower(), "application/octet-stream")
