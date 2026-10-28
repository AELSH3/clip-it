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

No held-out video evaluation has been written into `data/evaluation/latest.json` as part of this commit. The evaluation page is an empty state until `scripts/evaluate.py` completes against videos that are actually in the database. This report does not claim Recall, nDCG, latency, or an ingestion-time number, and it does not claim the ranker improves retrieval.

## Limitations

- Windowed retrieval, not temporal boundary detection.
- CPU is the tested path. GPU is selected only when CUDA is visible and `CLIPIT_TORCH_DEVICE=auto`.
- OCR quality depends on Tesseract and the frame sample (default every 2 seconds).
- Whisper tiny will miss names and mumble. That shows up as a weak transcript, not a hidden confidence score.
- QVHighlights features are a different vector space and are intentionally unused.
