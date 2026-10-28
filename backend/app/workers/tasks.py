from app.errors import PermanentProcessingError, RetryableProcessingError
from app.services.pipeline import run_pipeline
from app.workers import celery_app


@celery_app.task(bind=True, max_retries=2, name="clipit.process_video")
def process_video_task(self, video_id: str) -> None:
    try:
        run_pipeline(video_id)
    except PermanentProcessingError:
        return
    except RetryableProcessingError as exc:
        raise self.retry(exc=exc, countdown=min(60, 2**self.request.retries)) from exc
