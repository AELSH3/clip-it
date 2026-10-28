from app.retrieval import (
    apply_scaler,
    assert_video_disjoint,
    best_iou,
    build_windows,
    dedupe_overlaps,
    fit_scaler,
    is_relevant,
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank_fusion,
    split_for_video,
)


def test_windows_cover_the_end_and_overlap():
    spans = build_windows(20, 8, 4)
    assert spans[0] == (0.0, 8.0)
    assert spans[-1][1] == 20.0
    assert spans[1][0] == 4.0


def test_short_video_is_one_window():
    assert build_windows(3, 8, 4) == [(0.0, 3.0)]


def test_reciprocal_rank_fusion_prefers_agreement():
    scores = reciprocal_rank_fusion({"a": ["x", "y"], "b": ["x", "z"]}, k=60)
    assert scores["x"] > scores["y"]
    assert scores["x"] > scores["z"]


def test_dedupe_drops_overlapping_lower_score():
    items = [
        {"video_id": "v", "start": 0, "end": 8, "score": 0.2},
        {"video_id": "v", "start": 1, "end": 9, "score": 0.9},
        {"video_id": "v", "start": 30, "end": 38, "score": 0.4},
    ]
    kept = dedupe_overlaps(items, threshold=0.5)
    assert [item["score"] for item in kept] == [0.9, 0.4]


def test_relevance_half_overlap_rule():
    assert is_relevant((0, 8), [(0, 6)])
    assert not is_relevant((0, 8), [(20, 28)])
    assert best_iou((0, 10), [(0, 10)]) == 1


def test_recall_and_ndcg():
    flags = [False, True, False]
    assert recall_at_k(flags, 1) == 0
    assert recall_at_k(flags, 5) == 1
    assert ndcg_at_k(flags, relevant_count=1, k=10) > 0
    assert ndcg_at_k([False, False], relevant_count=0, k=10) == 0


def test_splits_are_disjoint_and_queries_follow_video():
    splits = {"train": ["a"], "val": ["b"], "test": ["c"]}
    assert_video_disjoint(splits)
    assert split_for_video("b", splits) == "val"
    try:
        assert_video_disjoint({"train": ["a"], "test": ["a"]})
        raise AssertionError("expected overlap to fail")
    except ValueError:
        pass


def test_scaler_uses_only_the_rows_it_is_given():
    mean, std = fit_scaler([[0, 0], [2, 4]])
    assert mean == [1, 2]
    assert apply_scaler([1, 2], mean, std) == [0, 0]
