import threading

from app.config import get_settings
from app.errors import AppError


def enqueue_video(video_id: str) -> None:
    settings = get_settings()
    if settings.inline_processing:
        from app.services.pipeline import run_pipeline

        threading.Thread(target=run_pipeline, args=(video_id,), daemon=True).start()
        return
    from app.workers.tasks import process_video_task

    try:
        process_video_task.delay(video_id)
    except Exception as exc:
        raise AppError(
            503,
            "queue_unavailable",
            f"Could not queue processing. Start Redis and the Celery worker. {exc}",
        ) from exc
