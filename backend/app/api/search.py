import uuid
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError

router = APIRouter(prefix="/api/search", tags=["search"])


class SearchIn(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    mode: Literal["all", "speech", "screen_text", "visual"] = "all"
    video_id: uuid.UUID | None = None
    limit: int = Field(default=12, ge=1, le=50)


class SummarizeIn(SearchIn):
    pass


@router.post("")
def run_search(body: SearchIn, db: Session = Depends(get_db)):
    from app.services.search_service import search

    return search(db, body.query.strip(), body.mode, body.video_id, body.limit)


@router.post("/summarize")
def summarize_search(body: SummarizeIn, db: Session = Depends(get_db)):
    from app.config import get_settings
    from app.services.present import summarize
    from app.services.search_service import search

    if not get_settings().llm_enabled:
        raise AppError(
            409,
            "llm_disabled",
            "Summaries are off until CLIPIT_LLM_BASE_URL and CLIPIT_LLM_MODEL are configured.",
        )
    found = search(db, body.query.strip(), body.mode, body.video_id, body.limit)
    evidence = []
    for hit in found["results"]:
        for item in hit["evidence"]:
            evidence.append(
                {
                    "video_id": hit["video_id"],
                    "video_title": hit["video_title"],
                    "start_sec": item["start_sec"],
                    "end_sec": item["end_sec"],
                    "type": item["type"],
                    "text": item["text"],
                }
            )
    try:
        summary = summarize(body.query.strip(), evidence)
    except Exception as exc:
        raise AppError(502, "llm_failed", f"The summary model did not respond. {exc}") from exc
    return summary
