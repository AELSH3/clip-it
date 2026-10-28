# Model and data report

## Provenance

| Piece | Source | Id stored with vectors |
| --- | --- | --- |
| Speech | faster-whisper 1.2.1, default checkpoint name `tiny` | `faster-whisper:tiny` |
| Transcript and OCR text | sentence-transformers 6.2.0, `all-MiniLM-L6-v2` | `sentence-transformers/all-MiniLM-L6-v2` |
| Frames and visual queries | open_clip_torch 3.3.0, ViT-B-32, pretrained `openai` | `open_clip:ViT-B-32:openai` |
| On-screen text | Tesseract via pytesseract 0.3.13 | not an embedding |
| Ranker | trained in this repo when an artifact exists | version field inside `preprocessor.json` |

Weights download on first use into `models/`. They are not committed.

The ranker is a 12-feature MLP. Features are transcript similarity, OCR similarity, visual similarity, keyword strength, reciprocal ranks for those channels, missing-modality flags, and log segment duration. Training uses pairwise logistic loss on query-grouped positives and negatives. The scaler mean and standard deviation are fit on training rows only.

`python -m scripts.train_ranker --synthetic` trains on made-up separable features. That artifact, if you create it, verifies the loop. It is not evidence that the ranker helps video search. The API will load it only because the file says `"trained": true`, and the note in the file says the data is synthetic. Do not describe that run as a video benchmark.

Feedback from the Relevant / Not relevant buttons is stored and can be exported. Nothing retrains on those clicks automatically.

## Measured results

One evaluation file was produced locally on 2026-10-27 from the synthetic fixture after all four clips were Ready. `data/evaluation/latest.json` is runtime output and is not committed. The numbers below are copied from that file. They are not a benchmark.

- Dataset `clipit-dev-fixture`. Splits: train 2 (`lecture-deadlocks`, `demo-docker`), val 1 (`slide-architecture`), test 1 (`lecture-queues`). Test queries: 1, “Where are message queues explained?”, labeled speech from 0 to 8 seconds.
- Speech model `faster-whisper:tiny`. Text model `sentence-transformers/all-MiniLM-L6-v2`. Visual model `open_clip:ViT-B-32:openai`.
- The test transcript was “This lecture explains message cues and how workers pull jobs.” Whisper tiny wrote “cues”, not “queues”.
- In-video search (restricted to `lecture-queues`, one window about 0–3.46s, IoU against the 0–8s label = 0.432): keyword Recall@5 0.000 because “queues” is not in the transcript. Transcript semantic, visual, fusion, and fusion-plus-ranker each returned that only window, so Recall@1, Recall@5, Recall@10, and nDCG@10 were 1.000. Visual’s 1.000 is that single-window effect, not evidence it understood the question.
- Whole-library first hit on the same query: keyword returned nothing (top-1 0). Transcript semantic first hit `lecture-queues` (top-1 1). Visual first hit `lecture-deadlocks` (top-1 0). Fusion first hit `lecture-queues` (top-1 1). Fusion-plus-ranker also first-hit `lecture-queues`, and `ranker_improved` is false. No ranker artifact was loaded, so that method is fusion.
- Ingestion, measured from stored start and finish times on the same four Ready clips: 253.2 seconds of processing per minute of video. `slide-architecture` took 49.4 seconds and `lecture-queues` took 21.5 seconds because those jobs downloaded models. The later clips, `lecture-deadlocks` and `demo-docker`, took 3.9 and 4.6 seconds. This is not a warm steady-state rate. A rerun of the retrieval script on 2026-10-28 left the Recall and top-1 results above unchanged.

Separate manual checks on the same four clips, not part of the held-out file: a speech query about deadlocks ranked `lecture-deadlocks` first, a speech query about Docker ranked `demo-docker` first, and a screen-text query for the architecture diagram ranked `slide-architecture` first. Opening that deadlocks hit and then `?t=2` started playback at 2.0 seconds of a 4.3 second file.

## Limitations

- Windowed retrieval, not temporal boundary detection.
- CPU is the tested path. GPU is selected only when CUDA is visible and `CLIPIT_TORCH_DEVICE=auto`.
- OCR quality depends on Tesseract and the frame sample (default every 2 seconds).
- Whisper tiny will miss names and mumble. That shows up as a weak transcript, not a hidden confidence score.
- QVHighlights features are a different vector space and are intentionally unused.
