from __future__ import annotations

import math


def build_windows(duration: float, window: float, stride: float) -> list[tuple[float, float]]:
    """Overlapping retrieval windows. Boundaries are the window grid, not predicted event edges."""
    if duration <= 0:
        return [(0.0, 0.0)]
    window = max(float(window), 0.5)
    stride = max(float(stride), 0.1)
    if duration <= window:
        return [(0.0, float(duration))]
    spans: list[tuple[float, float]] = []
    start = 0.0
    while start < duration - 1e-6:
        end = min(duration, start + window)
        spans.append((round(start, 3), round(end, 3)))
        if end >= duration - 1e-6:
            break
        start += stride
    return spans


def reciprocal_rank_fusion(rankings: dict[str, list[str]], k: int = 60) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ids in rankings.values():
        for rank, item_id in enumerate(ids, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)
    return scores


def overlap_coefficient(a: tuple[float, float], b: tuple[float, float]) -> float:
    inter = max(0.0, min(a[1], b[1]) - max(a[0], b[0]))
    denom = min(max(a[1] - a[0], 0.0), max(b[1] - b[0], 0.0))
    if denom <= 1e-6:
        return 0.0
    return inter / denom


def dedupe_overlaps(items: list[dict], threshold: float = 0.5) -> list[dict]:
    """Keep the higher-scoring segment when two hits on the same video overlap heavily."""
    ordered = sorted(items, key=lambda item: item["score"], reverse=True)
    kept: list[dict] = []
    for item in ordered:
        span = (item["start"], item["end"])
        if any(
            other["video_id"] == item["video_id"]
            and overlap_coefficient(span, (other["start"], other["end"])) >= threshold
            for other in kept
        ):
            continue
        kept.append(item)
    return kept


def temporal_iou(pred: tuple[float, float], truth: tuple[float, float]) -> float:
    inter = max(0.0, min(pred[1], truth[1]) - max(pred[0], truth[0]))
    union = max(pred[1] - pred[0], 0.0) + max(truth[1] - truth[0], 0.0) - inter
    if union <= 1e-6:
        return 0.0
    return inter / union


def is_relevant(pred: tuple[float, float], truths: list[tuple[float, float]]) -> bool:
    """A segment is relevant when at least half of it lies inside a labeled interval,
    or it covers at least half of a labeled interval.
    """
    pred_len = max(pred[1] - pred[0], 1e-6)
    for truth in truths:
        inter = max(0.0, min(pred[1], truth[1]) - max(pred[0], truth[0]))
        truth_len = max(truth[1] - truth[0], 1e-6)
        if inter / pred_len >= 0.5 or inter / truth_len >= 0.5:
            return True
    return False


def best_iou(pred: tuple[float, float], truths: list[tuple[float, float]]) -> float:
    if not truths:
        return 0.0
    return max(temporal_iou(pred, truth) for truth in truths)


def dcg(flags: list[bool]) -> float:
    return sum((1.0 if flag else 0.0) / math.log2(index + 2) for index, flag in enumerate(flags))


def ndcg_at_k(ranked_flags: list[bool], relevant_count: int, k: int) -> float:
    ideal_hits = min(k, relevant_count)
    ideal = dcg([True] * ideal_hits)
    if ideal <= 0:
        return 0.0
    return dcg(ranked_flags[:k]) / ideal


def recall_at_k(flags: list[bool], k: int) -> float:
    return 1.0 if any(flags[:k]) else 0.0


def assert_video_disjoint(splits: dict[str, list[str]]) -> None:
    seen: dict[str, str] = {}
    for name, videos in splits.items():
        for video in videos:
            if video in seen:
                raise ValueError(f"{video} is in both {seen[video]} and {name}")
            seen[video] = name


def split_for_video(video_key: str, splits: dict[str, list[str]]) -> str:
    owners = [name for name, videos in splits.items() if video_key in videos]
    if len(owners) != 1:
        raise ValueError(f"{video_key} must belong to exactly one split")
    return owners[0]


FEATURE_NAMES = [
    "transcript_similarity",
    "ocr_similarity",
    "visual_similarity",
    "keyword_strength",
    "transcript_rrf",
    "ocr_rrf",
    "visual_rrf",
    "keyword_rrf",
    "missing_transcript",
    "missing_ocr",
    "missing_visual",
    "log_duration",
]


def fit_scaler(rows: list[list[float]]) -> tuple[list[float], list[float]]:
    if not rows:
        raise ValueError("scaler requires training rows")
    width = len(rows[0])
    means = []
    stds = []
    for index in range(width):
        column = [row[index] for row in rows]
        mean = sum(column) / len(column)
        variance = sum((value - mean) ** 2 for value in column) / len(column)
        std = variance**0.5
        means.append(mean)
        stds.append(std if std >= 1e-8 else 1.0)
    return means, stds


def apply_scaler(row: list[float], mean: list[float], std: list[float]) -> list[float]:
    return [(value - center) / scale for value, center, scale in zip(row, mean, std, strict=True)]


MODES = {
    "all": {
        "transcript_keyword",
        "ocr_keyword",
        "transcript_semantic",
        "ocr_semantic",
        "visual",
    },
    "speech": {"transcript_keyword", "transcript_semantic"},
    "screen_text": {"ocr_keyword", "ocr_semantic"},
    "visual": {"visual"},
}
