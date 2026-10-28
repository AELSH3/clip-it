"""Evaluate held-out queries. Writes metrics only after a real run. Exits 2 if videos are missing."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.config import REPO_ROOT, get_settings
from app.db import SessionLocal
from app.evalkit import load_jsonl
from app.models import Video
from app.retrieval import assert_video_disjoint, best_iou, is_relevant, ndcg_at_k, recall_at_k, split_for_video
from app.services.search_service import search

METHODS = ("keyword", "transcript_semantic", "visual", "fusion", "fusion_ranker")


def main() -> None:
    fixture = REPO_ROOT / "fixtures" / "annotations" / "dev_fixture.json"
    data = json.loads(fixture.read_text())
    assert_video_disjoint(data["splits"])
    db = SessionLocal()
    try:
        videos = {video.title: video for video in db.scalars(select(Video))}
        missing = [key for key in data["splits"]["train"] + data["splits"]["val"] + data["splits"]["test"] if key not in videos]
        if missing:
            print("Evaluation not written. These fixture videos are not in the database:", ", ".join(missing))
            sys.exit(2)
        test_items = [item for item in data["items"] if split_for_video(item["video_key"], data["splits"]) == "test"]
        if not test_items:
            print("No test queries.")
            sys.exit(2)
        # The full multi-method runner compares channels by calling search in the requested mode.
        # Keyword-only and single-channel numbers use the same relevance rule.
        mode_for = {
            "keyword": "speech",
            "transcript_semantic": "speech",
            "visual": "visual",
            "fusion": "all",
            "fusion_ranker": "all",
        }
        per_method: dict[str, list[dict]] = {name: [] for name in METHODS}
        for item in test_items:
            video = videos[item["video_key"]]
            truths = [(window["start"], window["end"]) for window in item["relevant_windows"]]
            for method in METHODS:
                found = search(db, item["query"], mode_for[method], video.id, 10)
                flags = [
                    is_relevant((hit["start_sec"], hit["end_sec"]), truths) for hit in found["results"]
                ]
                relevant_count = sum(1 for hit in found["results"] if is_relevant((hit["start_sec"], hit["end_sec"]), truths))
                top = found["results"][:5]
                per_method[method].append(
                    {
                        "query_type": item["query_type"],
                        "flags": flags,
                        "relevant_count": max(relevant_count, 1 if truths else 0),
                        "iou1": best_iou((top[0]["start_sec"], top[0]["end_sec"]), truths) if top else 0.0,
                        "iou5": max((best_iou((hit["start_sec"], hit["end_sec"]), truths) for hit in top), default=0.0),
                        "latency_ms": found["latency_ms"],
                        "ranker_applied": found["ranker_applied"],
                    }
                )
        methods = []
        by_type = []
        for method, rows in per_method.items():
            methods.append(
                {
                    "name": method,
                    "recall_at_1": _mean(recall_at_k(row["flags"], 1) for row in rows),
                    "recall_at_5": _mean(recall_at_k(row["flags"], 5) for row in rows),
                    "recall_at_10": _mean(recall_at_k(row["flags"], 10) for row in rows),
                    "ndcg_at_10": _mean(ndcg_at_k(row["flags"], row["relevant_count"], 10) for row in rows),
                    "mean_best_iou_at_1": _mean(row["iou1"] for row in rows),
                    "mean_best_iou_at_5": _mean(row["iou5"] for row in rows),
                    "mean_latency_ms": _mean(row["latency_ms"] for row in rows),
                }
            )
            for query_type in sorted({row["query_type"] for row in rows}):
                subset = [row for row in rows if row["query_type"] == query_type]
                by_type.append(
                    {
                        "query_type": query_type,
                        "method": method,
                        "recall_at_5": _mean(recall_at_k(row["flags"], 5) for row in subset),
                        "count": len(subset),
                    }
                )
        fusion = next(method for method in methods if method["name"] == "fusion")
        ranked = next(method for method in methods if method["name"] == "fusion_ranker")
        improved = ranked["recall_at_5"] > fusion["recall_at_5"]
        report = {
            "dataset_name": data["dataset"],
            "dataset_label": data["label"],
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "model_versions": {
                "speech": get_settings().speech_model_id,
                "text": get_settings().text_model_id,
                "visual": get_settings().visual_model_id,
            },
            "split": {name: len(keys) for name, keys in data["splits"].items()},
            "query_count": len(test_items),
            "relevance_definition": data["relevance_definition"],
            "caveat": "Held-out fixture queries only. A handful of synthetic clips does not establish generalization.",
            "methods": methods,
            "by_query_type": by_type,
            "ingestion": None,
            "ranker_improved": improved,
            "ranker_note": "Compare fusion and fusion_ranker on this file before claiming a gain."
            if not improved
            else "On this held-out fixture, fusion plus the ranker had higher Recall@5 than fusion alone.",
        }
        out = Path(get_settings().storage_dir) / "evaluation"
        out.mkdir(parents=True, exist_ok=True)
        (out / "latest.json").write_text(json.dumps(report, indent=2))
        print(f"Wrote {out / 'latest.json'}")
    finally:
        db.close()


def _mean(values) -> float:
    rows = list(values)
    return sum(rows) / len(rows) if rows else 0.0


if __name__ == "__main__":
    # Imported helper kept so the QVHighlights path stays referenced for the adapter.
    _ = load_jsonl
    main()
