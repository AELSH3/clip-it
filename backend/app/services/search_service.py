from __future__ import annotations

import logging
import time
import uuid

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import AppError
from app.ml import text_embedder, vision_embedder
from app.models import FrameEmbedding, SearchSegment, TextEmbedding, Video
from app.ranking.runtime import RankerRuntime
from app.retrieval import FEATURE_NAMES, MODES, apply_scaler, dedupe_overlaps, reciprocal_rank_fusion
from app.services import safe_frame

log = logging.getLogger(__name__)
_ranker: RankerRuntime | None = None


def ranker() -> RankerRuntime:
    global _ranker
    if _ranker is None:
        _ranker = RankerRuntime(get_settings().ranker_dir)
    return _ranker


def _keyword(db: Session, query: str, column, video_id: uuid.UUID | None, limit: int):
    tsquery = func.plainto_tsquery("english", query)
    rank = func.ts_rank(column, tsquery)
    stmt = select(SearchSegment.id, rank.label("strength")).where(column.op("@@")(tsquery))
    if video_id is not None:
        stmt = stmt.where(SearchSegment.video_id == video_id)
    stmt = stmt.order_by(rank.desc()).limit(limit)
    return list(db.execute(stmt))


def _semantic(db: Session, vector: np.ndarray, source: str, video_id: uuid.UUID | None, limit: int):
    settings = get_settings()
    distance = TextEmbedding.embedding.cosine_distance(vector.tolist())
    similarity = (1 - distance).label("similarity")
    stmt = (
        select(TextEmbedding.segment_id, similarity)
        .where(TextEmbedding.model_id == settings.text_model_id, TextEmbedding.source == source)
        .order_by(distance)
        .limit(limit)
    )
    if video_id is not None:
        stmt = stmt.where(TextEmbedding.video_id == video_id)
    return list(db.execute(stmt))


def _visual(db: Session, vector: np.ndarray, video_id: uuid.UUID | None, limit: int):
    settings = get_settings()
    distance = FrameEmbedding.embedding.cosine_distance(vector.tolist())
    similarity = (1 - distance).label("similarity")
    stmt = (
        select(FrameEmbedding.video_id, FrameEmbedding.timestamp_sec, similarity)
        .where(FrameEmbedding.model_id == settings.visual_model_id)
        .order_by(distance)
        .limit(limit * 3)
    )
    if video_id is not None:
        stmt = stmt.where(FrameEmbedding.video_id == video_id)
    frames = list(db.execute(stmt))
    if not frames:
        return []
    video_ids = {row.video_id for row in frames}
    segments = list(db.scalars(select(SearchSegment).where(SearchSegment.video_id.in_(video_ids))))
    best: dict[uuid.UUID, float] = {}
    for frame in frames:
        covering = [
            segment
            for segment in segments
            if segment.video_id == frame.video_id and segment.start_sec <= frame.timestamp_sec <= segment.end_sec
        ]
        if not covering:
            continue
        midpoint_target = frame.timestamp_sec
        chosen = min(covering, key=lambda segment: abs(((segment.start_sec + segment.end_sec) / 2) - midpoint_target))
        score = float(frame.similarity)
        best[chosen.id] = max(best.get(chosen.id, score), score)
    ordered = sorted(best.items(), key=lambda item: item[1], reverse=True)[:limit]
    return ordered


def _record(bucket: dict, segment_id: str, channel: str, rank: int, similarity, keyword_strength) -> None:
    bucket.setdefault(segment_id, {})[channel] = {
        "name": channel,
        "similarity": None if similarity is None else round(float(similarity), 4),
        "keyword_strength": None if keyword_strength is None else round(float(keyword_strength), 4),
        "rank": rank,
    }


def search(db: Session, query: str, mode: str, video_id: uuid.UUID | None, limit: int) -> dict:
    if mode not in MODES:
        raise AppError(400, "bad_mode", "Search mode must be all, speech, screen_text, or visual.")
    settings = get_settings()
    started = time.perf_counter()
    channels = MODES[mode]
    rankings: dict[str, list[str]] = {}
    channel_info: dict[str, dict] = {}
    notice = None

    if "transcript_keyword" in channels:
        rows = _keyword(db, query, SearchSegment.transcript_tsv, video_id, settings.channel_limit)
        rankings["transcript_keyword"] = [str(row.id) for row in rows]
        for rank, row in enumerate(rows, start=1):
            strength = float(row.strength or 0) / (float(row.strength or 0) + 1)
            _record(channel_info, str(row.id), "transcript_keyword", rank, None, strength)
    if "ocr_keyword" in channels:
        rows = _keyword(db, query, SearchSegment.ocr_tsv, video_id, settings.channel_limit)
        rankings["ocr_keyword"] = [str(row.id) for row in rows]
        for rank, row in enumerate(rows, start=1):
            strength = float(row.strength or 0) / (float(row.strength or 0) + 1)
            _record(channel_info, str(row.id), "ocr_keyword", rank, None, strength)
    if "transcript_semantic" in channels or "ocr_semantic" in channels:
        try:
            query_text = text_embedder().embed([query])[0]
        except Exception as exc:
            raise AppError(503, "model_unavailable", f"The text embedding model is not available: {exc}") from exc
        if "transcript_semantic" in channels:
            rows = _semantic(db, query_text, "transcript", video_id, settings.channel_limit)
            rankings["transcript_semantic"] = [str(row.segment_id) for row in rows]
            for rank, row in enumerate(rows, start=1):
                _record(channel_info, str(row.segment_id), "transcript_semantic", rank, row.similarity, None)
        if "ocr_semantic" in channels:
            rows = _semantic(db, query_text, "ocr", video_id, settings.channel_limit)
            rankings["ocr_semantic"] = [str(row.segment_id) for row in rows]
            for rank, row in enumerate(rows, start=1):
                _record(channel_info, str(row.segment_id), "ocr_semantic", rank, row.similarity, None)
    if "visual" in channels:
        try:
            query_image = vision_embedder().embed_text(query)
        except Exception as exc:
            raise AppError(503, "model_unavailable", f"The visual model is not available: {exc}") from exc
        rows = _visual(db, query_image, video_id, settings.channel_limit)
        rankings["visual"] = [str(segment_id) for segment_id, _score in rows]
        for rank, (segment_id, score) in enumerate(rows, start=1):
            _record(channel_info, str(segment_id), "visual", rank, score, None)
        if not rows:
            notice = "No visual index matched. Videos still processing, or visual embeddings were not created."

    fused = reciprocal_rank_fusion(rankings, settings.rrf_k)
    if not fused:
        return _empty(query, mode, started, notice or "Nothing in the library matched this search.")

    ids = [uuid.UUID(item_id) for item_id in fused]
    segments = {segment.id: segment for segment in db.scalars(select(SearchSegment).where(SearchSegment.id.in_(ids)))}
    videos = {
        video.id: video
        for video in db.scalars(select(Video).where(Video.id.in_({segment.video_id for segment in segments.values()})))
    }
    items = []
    for item_id, score in fused.items():
        segment = segments.get(uuid.UUID(item_id))
        if segment is None:
            continue
        items.append(
            {
                "id": item_id,
                "video_id": str(segment.video_id),
                "start": segment.start_sec,
                "end": segment.end_sec,
                "score": score,
                "segment": segment,
                "video": videos[segment.video_id],
            }
        )
    items = dedupe_overlaps(items)
    runtime = ranker()
    ranker_applied = False
    rank_scores: dict[str, float] = {}
    if runtime.available and items:
        features = [_features(item, channel_info, mode) for item in items]
        scaled = [apply_scaler(row, runtime.mean, runtime.std) for row in features]
        try:
            scores = runtime.score(scaled)
            ranker_applied = True
            for item, value in zip(items, scores, strict=True):
                rank_scores[item["id"]] = value
            items.sort(key=lambda item: rank_scores[item["id"]], reverse=True)
        except Exception:
            log.exception("ranker inference failed")
            ranker_applied = False

    hits = []
    for item in items[:limit]:
        segment: SearchSegment = item["segment"]
        video: Video = item["video"]
        info = channel_info.get(item["id"], {})
        excerpt = segment.transcript_text or segment.ocr_text or "Visual match without transcript text."
        evidence = []
        if segment.transcript_text and mode in {"all", "speech"}:
            evidence.append(
                {
                    "type": "transcript",
                    "text": segment.transcript_text,
                    "start_sec": segment.start_sec,
                    "end_sec": segment.end_sec,
                    "similarity": (info.get("transcript_semantic") or {}).get("similarity"),
                }
            )
        if segment.ocr_text and mode in {"all", "screen_text"}:
            evidence.append(
                {
                    "type": "ocr",
                    "text": segment.ocr_text,
                    "start_sec": segment.start_sec,
                    "end_sec": segment.end_sec,
                    "similarity": (info.get("ocr_semantic") or {}).get("similarity"),
                }
            )
        if mode in {"all", "visual"} and "visual" in info:
            evidence.append(
                {
                    "type": "visual",
                    "text": None,
                    "start_sec": segment.start_sec,
                    "end_sec": segment.end_sec,
                    "similarity": info["visual"]["similarity"],
                }
            )
        thumb = None
        if segment.frame_relpath:
            try:
                safe_frame(video.id, segment.frame_relpath)
                thumb = f"/api/videos/{video.id}/preview?path={segment.frame_relpath}"
            except AppError:
                thumb = None
        fusion_score = round(float(item["score"]), 4)
        rank_score = round(rank_scores[item["id"]], 4) if item["id"] in rank_scores else None
        hits.append(
            {
                "video_id": str(video.id),
                "video_title": video.title,
                "segment_id": str(segment.id),
                "start_sec": segment.start_sec,
                "end_sec": segment.end_sec,
                "fusion_score": fusion_score,
                "rank_score": rank_score,
                "display_score": rank_score if ranker_applied and rank_score is not None else fusion_score,
                "score_label": "Rank score" if ranker_applied else "Match score",
                "excerpt": excerpt[:500],
                "thumbnail_url": thumb,
                "channels": list(info.values()),
                "evidence": evidence,
            }
        )
    latency_ms = round((time.perf_counter() - started) * 1000, 1)
    return {
        "query": query,
        "mode": mode,
        "ranker_applied": ranker_applied,
        "ranker_version": runtime.version if ranker_applied else None,
        "latency_ms": latency_ms,
        "notice": notice,
        "results": hits,
    }


def _empty(query: str, mode: str, started: float, notice: str) -> dict:
    runtime = ranker()
    return {
        "query": query,
        "mode": mode,
        "ranker_applied": False,
        "ranker_version": runtime.version if runtime.available else None,
        "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        "notice": notice,
        "results": [],
    }


def _rrf(rank: int | None, k: int) -> float:
    if not rank:
        return 0.0
    return 1.0 / (k + rank)


def _features(item: dict, channel_info: dict, mode: str) -> list[float]:
    info = channel_info.get(item["id"], {})
    settings = get_settings()
    segment: SearchSegment = item["segment"]
    active = MODES[mode]

    def sim(channel: str, enabled: bool) -> tuple[float, float]:
        if not enabled:
            return 0.0, 1.0
        row = info.get(channel)
        if row is None or row.get("similarity") is None:
            return 0.0, 0.0
        return float(row["similarity"]), 0.0

    transcript_similarity, missing_transcript = sim("transcript_semantic", "transcript_semantic" in active)
    ocr_similarity, missing_ocr = sim("ocr_semantic", "ocr_semantic" in active)
    visual_similarity, missing_visual = sim("visual", "visual" in active)
    keyword_values = []
    keyword_rank = None
    if "transcript_keyword" in active and "transcript_keyword" in info:
        keyword_values.append(info["transcript_keyword"]["keyword_strength"] or 0)
        keyword_rank = info["transcript_keyword"]["rank"]
    if "ocr_keyword" in active and "ocr_keyword" in info:
        keyword_values.append(info["ocr_keyword"]["keyword_strength"] or 0)
        if keyword_rank is None or info["ocr_keyword"]["rank"] < keyword_rank:
            keyword_rank = info["ocr_keyword"]["rank"]
    raw = {
        "transcript_similarity": transcript_similarity,
        "ocr_similarity": ocr_similarity,
        "visual_similarity": visual_similarity,
        "keyword_strength": max(keyword_values) if keyword_values else 0.0,
        "transcript_rrf": _rrf((info.get("transcript_semantic") or {}).get("rank"), settings.rrf_k)
        if "transcript_semantic" in active
        else 0.0,
        "ocr_rrf": _rrf((info.get("ocr_semantic") or {}).get("rank"), settings.rrf_k) if "ocr_semantic" in active else 0.0,
        "visual_rrf": _rrf((info.get("visual") or {}).get("rank"), settings.rrf_k) if "visual" in active else 0.0,
        "keyword_rrf": _rrf(keyword_rank, settings.rrf_k) if keyword_rank else 0.0,
        "missing_transcript": missing_transcript if "transcript_semantic" in active else 1.0,
        "missing_ocr": missing_ocr if "ocr_semantic" in active else 1.0,
        "missing_visual": missing_visual if "visual" in active else 1.0,
        "log_duration": float(np.log1p(max(segment.end_sec - segment.start_sec, 0.0))),
    }
    return [float(raw[name]) for name in FEATURE_NAMES]
