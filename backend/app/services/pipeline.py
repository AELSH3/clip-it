from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.errors import PermanentProcessingError, RetryableProcessingError
from app.models import FrameEmbedding, OcrObservation, SearchSegment, TextEmbedding, TranscriptSegment, Video
from app.retrieval import build_windows
from app.services import video_dir
from app.services.media import extract_audio, extract_frames, probe, write_thumbnail

log = logging.getLogger(__name__)

STAGE_LABELS = {
    "queued": "Queued",
    "probe": "Inspecting the file",
    "extract": "Extracting audio and frames",
    "transcribe": "Transcribing speech",
    "ocr": "Reading text on screen",
    "segment": "Building searchable segments",
    "embed": "Creating embeddings",
    "done": "Ready",
}


def _warn(video: Video, message: str) -> None:
    notes = list(video.warnings or [])
    notes.append(message)
    video.warnings = notes


def _stage(db: Session, video: Video, key: str, message: str | None = None) -> None:
    video.status = "processing"
    video.stage = key
    video.stage_label = STAGE_LABELS[key]
    video.stage_message = message
    db.commit()


def _clear_derived(db: Session, video: Video) -> None:
    db.execute(delete(TextEmbedding).where(TextEmbedding.video_id == video.id))
    db.execute(delete(FrameEmbedding).where(FrameEmbedding.video_id == video.id))
    db.execute(delete(SearchSegment).where(SearchSegment.video_id == video.id))
    db.execute(delete(TranscriptSegment).where(TranscriptSegment.video_id == video.id))
    db.execute(delete(OcrObservation).where(OcrObservation.video_id == video.id))
    db.commit()


def _fail(video_id: uuid.UUID, message: str) -> None:
    db = SessionLocal()
    try:
        video = db.get(Video, video_id)
        if video is None:
            return
        video.status = "failed"
        video.stage = "failed"
        video.stage_label = "Failed"
        video.error_message = message
        video.processing_finished_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()


def run_pipeline(video_id: str) -> None:
    settings = get_settings()
    parsed = uuid.UUID(video_id)
    db = SessionLocal()
    try:
        video = db.get(Video, parsed)
        if video is None:
            return
        video.error_message = None
        video.warnings = []
        video.processing_started_at = datetime.now(timezone.utc)
        video.modalities = {"speech": False, "screen_text": False, "visual": False}
        db.commit()
        _clear_derived(db, video)
        folder = video_dir(video.id)
        source = folder / f"original{video.extension}"
        if not source.is_file():
            raise PermanentProcessingError("The uploaded file is missing from storage.")

        _stage(db, video, "probe")
        info = probe(source)
        if info.duration_sec is not None and info.duration_sec > settings.max_duration_sec:
            raise PermanentProcessingError(
                f"Videos must be {int(settings.max_duration_sec // 60)} minutes or shorter."
            )
        video.duration_sec = info.duration_sec
        video.width = info.width
        video.height = info.height
        video.fps = info.fps
        video.has_audio = info.has_audio
        db.commit()

        _stage(db, video, "extract")
        frames = extract_frames(source, folder / "frames", settings.frame_sample_sec)
        write_thumbnail(frames, folder / "thumb.jpg")
        audio_path = folder / "audio.wav"
        if info.has_audio:
            try:
                extract_audio(source, audio_path)
            except PermanentProcessingError as exc:
                _warn(video, f"Audio could not be extracted: {exc.message}")
                info.has_audio = False
                video.has_audio = False
                db.commit()
        else:
            _warn(video, "This video has no audio track, so speech search is empty.")

        _stage(db, video, "transcribe")
        transcript_rows: list[dict] = []
        if info.has_audio and audio_path.exists():
            try:
                from app.ml import speech_model

                transcript_rows = speech_model().transcribe(audio_path)
                video.speech_model_id = settings.speech_model_id
            except Exception as exc:
                raise RetryableProcessingError(f"Speech recognition failed: {exc}") from exc
        for row in transcript_rows:
            db.add(
                TranscriptSegment(
                    video_id=video.id,
                    start_sec=row["start"],
                    end_sec=row["end"],
                    text=row["text"],
                    words=row["words"],
                )
            )
        db.commit()
        if info.has_audio and not transcript_rows:
            _warn(video, "No speech was detected. Speech search will be empty for this video.")

        _stage(db, video, "ocr")
        ocr_rows: list[OcrObservation] = []
        try:
            from app.ml import read_screen_text

            for timestamp, frame in frames:
                rel = f"frames/{frame.name}"
                try:
                    text = read_screen_text(frame)
                except Exception as exc:
                    log.warning("ocr frame failed", extra={"frame": str(frame), "error": str(exc)})
                    continue
                if text:
                    obs = OcrObservation(
                        video_id=video.id, timestamp_sec=timestamp, text=text, frame_relpath=rel
                    )
                    db.add(obs)
                    ocr_rows.append(obs)
            db.commit()
        except Exception as exc:
            _warn(video, f"Screen-text reading failed: {exc}")
            db.commit()

        _stage(db, video, "segment")
        duration = info.duration_sec or (frames[-1][0] + settings.frame_sample_sec)
        windows = build_windows(duration, settings.window_sec, settings.window_stride_sec)
        segments: list[SearchSegment] = []
        for start, end in windows:
            transcript_text = " ".join(
                row["text"] for row in transcript_rows if row["start"] < end and row["end"] > start
            ).strip()
            ocr_text = " ".join(
                obs.text for obs in ocr_rows if start <= obs.timestamp_sec <= end
            ).strip()
            midpoint = (start + end) / 2
            frame = min(frames, key=lambda item: abs(item[0] - midpoint))
            segment = SearchSegment(
                video_id=video.id,
                start_sec=start,
                end_sec=end,
                transcript_text=transcript_text,
                ocr_text=ocr_text,
                frame_relpath=f"frames/{frame[1].name}",
            )
            db.add(segment)
            segments.append(segment)
        db.commit()
        db.execute(
            update(SearchSegment)
            .where(SearchSegment.video_id == video.id)
            .values(
                transcript_tsv=func.to_tsvector("english", SearchSegment.transcript_text),
                ocr_tsv=func.to_tsvector("english", SearchSegment.ocr_text),
            )
        )
        db.commit()

        _stage(db, video, "embed")
        modalities = {"speech": bool(transcript_rows), "screen_text": bool(ocr_rows), "visual": False}
        try:
            from app.ml import text_embedder

            embedder = text_embedder()
            for source_name, attr in (("transcript", "transcript_text"), ("ocr", "ocr_text")):
                chosen = [segment for segment in segments if getattr(segment, attr).strip()]
                if not chosen:
                    continue
                vectors = embedder.embed([getattr(segment, attr) for segment in chosen])
                for segment, vector in zip(chosen, vectors, strict=True):
                    db.add(
                        TextEmbedding(
                            segment_id=segment.id,
                            video_id=video.id,
                            source=source_name,
                            model_id=settings.text_model_id,
                            embedding=vector.tolist(),
                        )
                    )
            video.text_model_id = settings.text_model_id
            db.commit()
        except Exception as exc:
            if transcript_rows or ocr_rows:
                raise RetryableProcessingError(f"Text embeddings failed: {exc}") from exc
            _warn(video, f"Text embeddings were skipped: {exc}")

        try:
            from app.ml import vision_embedder

            vision = vision_embedder()
            paths = [frame for _ts, frame in frames]
            vectors = vision.embed_images(paths)
            for (timestamp, frame), vector in zip(frames, vectors, strict=True):
                db.add(
                    FrameEmbedding(
                        video_id=video.id,
                        timestamp_sec=timestamp,
                        frame_relpath=f"frames/{frame.name}",
                        model_id=settings.visual_model_id,
                        embedding=vector.tolist(),
                    )
                )
            video.visual_model_id = settings.visual_model_id
            modalities["visual"] = True
            db.commit()
        except Exception as exc:
            _warn(video, f"Visual embeddings were not created: {exc}")
            db.commit()

        video.modalities = modalities
        video.status = "ready"
        video.stage = "done"
        video.stage_label = "Ready"
        video.stage_message = None
        video.processing_finished_at = datetime.now(timezone.utc)
        if not any(modalities.values()):
            _warn(video, "The video can play, but no speech, screen text, or visual index was produced.")
        db.commit()
    except PermanentProcessingError as exc:
        db.rollback()
        _fail(parsed, exc.message)
    except RetryableProcessingError as exc:
        db.rollback()
        _fail(parsed, exc.message)
        raise
    except Exception as exc:
        db.rollback()
        log.exception("pipeline failed")
        _fail(parsed, f"Processing failed: {exc}")
        raise RetryableProcessingError(str(exc)) from exc
    finally:
        db.close()


def segment_count(db: Session, video_id: uuid.UUID) -> int:
    return int(db.scalar(select(func.count()).select_from(SearchSegment).where(SearchSegment.video_id == video_id)) or 0)
