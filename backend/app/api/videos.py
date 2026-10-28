import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.errors import AppError
from app.models import Video
from app.services import (
    ensure_size,
    extension_for,
    media_type_for,
    remove_video_files,
    sanitize_filename,
    video_dir,
)
from app.services.jobs import enqueue_video
from app.services.media import probe
from app.services.present import video_out
from app.services.streaming import InvalidRange, iter_file_range, parse_byte_range

router = APIRouter(prefix="/api/videos", tags=["videos"])


def _get(db: Session, video_id: uuid.UUID) -> Video:
    video = db.get(Video, video_id)
    if video is None:
        raise AppError(404, "not_found", "That video does not exist.")
    return video


@router.get("")
def list_videos(limit: int = 24, offset: int = 0, db: Session = Depends(get_db)):
    limit = min(max(limit, 1), 100)
    offset = max(offset, 0)
    total = int(db.scalar(select(func.count()).select_from(Video)) or 0)
    rows = list(db.scalars(select(Video).order_by(Video.created_at.desc()).limit(limit).offset(offset)))
    return {"items": [video_out(video) for video in rows], "total": total}


@router.post("", status_code=201)
async def upload_video(
    file: UploadFile = File(...),
    title: str | None = Form(None),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    ext = extension_for(file.filename)
    video_id = uuid.uuid4()
    folder = video_dir(video_id)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"original{ext}"
    size = 0
    try:
        with target.open("wb") as handle:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                ensure_size(size)
                handle.write(chunk)
        ensure_size(size)
        info = probe(target)
        if info.duration_sec is not None and info.duration_sec > settings.max_duration_sec:
            minutes = int(settings.max_duration_sec // 60)
            raise AppError(400, "too_long", f"Videos must be {minutes} minutes or shorter.")
    except AppError:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(folder, ignore_errors=True)
        raise AppError(400, "unreadable_video", f"Could not read this file as a video. {exc}") from exc

    display = sanitize_filename(title or file.filename)
    if display.lower().endswith(ext):
        display = display[: -len(ext)] or display
    video = Video(
        id=video_id,
        title=display[:300] or "Untitled video",
        original_filename=sanitize_filename(file.filename),
        extension=ext,
        file_size_bytes=size,
        duration_sec=info.duration_sec,
        width=info.width,
        height=info.height,
        fps=info.fps,
        has_audio=info.has_audio,
        status="pending",
        stage="queued",
        stage_label="Queued",
        warnings=[],
        modalities={"speech": False, "screen_text": False, "visual": False},
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    try:
        enqueue_video(str(video.id))
    except AppError as exc:
        video.status = "failed"
        video.stage = "failed"
        video.stage_label = "Failed"
        video.error_message = exc.message
        db.commit()
        raise
    return video_out(video)


@router.get("/{video_id}")
def get_video(video_id: uuid.UUID, db: Session = Depends(get_db)):
    return video_out(_get(db, video_id))


@router.delete("/{video_id}", status_code=204)
def delete_video(video_id: uuid.UUID, db: Session = Depends(get_db)):
    video = _get(db, video_id)
    db.delete(video)
    db.commit()
    remove_video_files(video_id)
    return Response(status_code=204)


@router.post("/{video_id}/retry")
def retry_video(video_id: uuid.UUID, db: Session = Depends(get_db)):
    video = _get(db, video_id)
    if video.status != "failed":
        raise AppError(409, "not_failed", "Only a failed video can be retried.")
    video.status = "pending"
    video.stage = "queued"
    video.stage_label = "Queued"
    video.stage_message = None
    video.error_message = None
    db.commit()
    try:
        enqueue_video(str(video.id))
    except AppError as exc:
        video.status = "failed"
        video.error_message = exc.message
        db.commit()
        raise
    return video_out(video)


@router.get("/{video_id}/thumbnail")
def thumbnail(video_id: uuid.UUID, db: Session = Depends(get_db)):
    _get(db, video_id)
    path = video_dir(video_id) / "thumb.jpg"
    if not path.is_file():
        raise AppError(404, "not_found", "This video does not have a thumbnail yet.")
    return FileResponse(path, media_type="image/jpeg")


@router.get("/{video_id}/preview")
def preview(video_id: uuid.UUID, path: str, db: Session = Depends(get_db)):
    from app.services import safe_frame

    _get(db, video_id)
    return FileResponse(safe_frame(video_id, path), media_type="image/jpeg")


@router.get("/{video_id}/transcript")
def transcript(video_id: uuid.UUID, db: Session = Depends(get_db)):
    from app.models import TranscriptSegment

    _get(db, video_id)
    rows = list(
        db.scalars(
            select(TranscriptSegment)
            .where(TranscriptSegment.video_id == video_id)
            .order_by(TranscriptSegment.start_sec)
        )
    )
    return {
        "segments": [
            {"id": str(row.id), "start_sec": row.start_sec, "end_sec": row.end_sec, "text": row.text}
            for row in rows
        ]
    }


@router.get("/{video_id}/stream")
def stream(video_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    video = _get(db, video_id)
    path = Path(video_dir(video.id) / f"original{video.extension}")
    if not path.is_file():
        raise AppError(404, "not_found", "The video file is missing.")
    size = path.stat().st_size
    try:
        byte_range = parse_byte_range(request.headers.get("range"), size)
    except (InvalidRange, ValueError) as exc:
        raise AppError(416, "bad_range", "The requested byte range is outside this file.") from exc
    if byte_range is None:
        start, end = 0, size - 1
        status = 200
        headers = {"Accept-Ranges": "bytes", "Content-Length": str(size)}
    else:
        start, end = byte_range
        status = 206
        headers = {
            "Accept-Ranges": "bytes",
            "Content-Range": f"bytes {start}-{end}/{size}",
            "Content-Length": str(end - start + 1),
        }
    return StreamingResponse(
        iter_file_range(path, start, end),
        status_code=status,
        media_type=media_type_for(video.extension),
        headers=headers,
    )
