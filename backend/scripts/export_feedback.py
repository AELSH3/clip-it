"""Export relevance feedback for a future curated training set. Does not train."""

import json

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Feedback


def main() -> None:
    db = SessionLocal()
    try:
        rows = list(db.scalars(select(Feedback).order_by(Feedback.created_at)))
    finally:
        db.close()
    for row in rows:
        print(
            json.dumps(
                {
                    "video_id": str(row.video_id),
                    "segment_id": str(row.segment_id) if row.segment_id else None,
                    "query": row.query,
                    "mode": row.mode,
                    "start_sec": row.start_sec,
                    "end_sec": row.end_sec,
                    "relevant": row.relevant,
                }
            )
        )


if __name__ == "__main__":
    main()
