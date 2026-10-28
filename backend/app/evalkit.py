"""Optional QVHighlights adapter.

Official annotation notes: https://github.com/jayleicn/moment_detr/blob/main/data/README.md
Each JSONL row has qid, query, duration, vid, relevant_windows, relevant_clip_ids, and saliency_scores.
vid looks like "{youtube_id}_{start}_{end}". relevant_windows are [start, end] seconds inside that clip.
Test rows omit the relevance fields.

This adapter only converts annotations into Clip-It's local format. It does not download videos and it
does not read Moment-DETR's precomputed SlowFast or CLIP features. Those features are a different
embedding space from Clip-It's faster-whisper, MiniLM, and OpenCLIP ViT-B/32 indexes, so they must
not be inserted into text_embeddings or frame_embeddings.

QVHighlights is a YouTube moment-retrieval set (vlogs and everyday activities), not lecture or tutorial
video. Its terms are the dataset authors' research license; obtain the videos yourself.
"""

from __future__ import annotations

import json
from pathlib import Path


def convert_row(row: dict) -> dict:
    windows = row.get("relevant_windows") or []
    return {
        "video_key": row["vid"],
        "query": row["query"],
        "query_type": "qvhighlights",
        "qid": row.get("qid"),
        "duration": row.get("duration"),
        "relevant_windows": [{"start": float(start), "end": float(end)} for start, end in windows],
    }


def load_jsonl(path: Path) -> list[dict]:
    items = []
    for line in path.read_text().splitlines():
        if line.strip():
            items.append(convert_row(json.loads(line)))
    return items
