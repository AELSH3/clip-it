# Annotations

Put queries in JSON:

```json
{
  "dataset": "my-lectures",
  "label": "Describe what this set is, and what it is not.",
  "relevance_definition": "Copy the rule you will score with.",
  "splits": { "train": ["video-title-a"], "val": ["video-title-b"], "test": ["video-title-c"] },
  "items": [
    {
      "video_key": "video-title-a",
      "query": "Where does the instructor explain deadlocks?",
      "query_type": "speech",
      "relevant_windows": [{ "start": 12.0, "end": 27.5 }]
    }
  ]
}
```

`video_key` must match the video title stored in Clip-It. A video id may appear in only one split. Every query stays with its video's split. The checked-in example is `fixtures/annotations/dev_fixture.json`.

A returned segment counts as relevant when at least half of the segment lies inside a labeled interval, or the segment covers at least half of a labeled interval. Intersection-over-union is reported separately so a coarse window is not mistaken for a precise boundary.

Workflow for a larger test set:

1. Upload videos and wait until they are Ready.
2. Watch them and write `relevant_windows` in seconds.
3. Assign whole videos to train, validation, or test. Do not split queries from the same video across sets.
4. Run `python -m scripts.evaluate` from `backend` after pointing it at your file if you replace the fixture path.
5. Export clicks with `python -m scripts.export_feedback`. Those rows are not used for training until you curate them.

## QVHighlights

`app/evalkit.py` reads the official JSONL shape from the Moment-DETR data notes: `qid`, `query`, `duration`, `vid`, `relevant_windows`, `relevant_clip_ids`, `saliency_scores`. Test rows omit the relevance fields.

Do not load their precomputed SlowFast or CLIP features into Clip-It's tables. Those vectors were produced by a different model and a different preprocessing pipeline. Clip-It only embeds video it has processed itself.

QVHighlights is YouTube lifestyle and activity footage with moment queries, not lecture or tutorial video. Follow the dataset authors' terms and download videos yourself. The adapter does not fetch them.
