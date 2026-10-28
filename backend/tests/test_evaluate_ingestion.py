from scripts.evaluate import ingestion_from_rows


def test_ingestion_weights_by_duration():
    report = ingestion_from_rows(
        [
            {"title": "short", "duration_sec": 30, "elapsed_sec": 30},
            {"title": "long", "duration_sec": 90, "elapsed_sec": 90},
        ]
    )
    assert report is not None
    assert report["videos"] == 2
    assert report["mean_seconds_per_video_minute"] == 60.0


def test_ingestion_skips_missing_times():
    assert ingestion_from_rows([{"title": "x", "duration_sec": 10, "elapsed_sec": None}]) is None
