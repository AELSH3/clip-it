# Architecture

Clip-It keeps three retrieval spaces apart.

- Speech and on-screen text use `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions) in `text_embeddings`, tagged with `source` `transcript` or `ocr` and the model id.
- Frames use OpenCLIP ViT-B-32 / openai (512 dimensions) in `frame_embeddings`, with that model's id.
- A query is embedded only with the encoder that matches the table it searches. Scores are never compared across those tables except as ranks inside reciprocal rank fusion.

Windows default to 8 seconds with a 4 second stride. A hit's start and end are the window edges. That is the timestamp resolution. The app does not predict tighter boundaries.

Search modes:

- Speech: transcript keywords and transcript embeddings.
- Screen text: OCR keywords and OCR embeddings.
- Visual: frame embeddings only, mapped back to the window that contains the frame.
- All: every channel, fused with reciprocal rank fusion (`1 / (60 + rank)`), then overlapping hits on the same video are suppressed.

Keyword strength is a squashed `ts_rank`. Cosine similarity is the raw embedding similarity. Neither is shown as a probability.

The ranker is a two-layer network trained with pairwise logistic loss. It reranks the fused list when `backend/artifacts/ranker/preprocessor.json` says `"trained": true`. Otherwise the API sets `ranker_applied` to false.

Processing runs in Celery. Each stage rewrites derived rows for that video and keeps the original file, so a retry is idempotent. Delete removes the database rows (foreign keys cascade) and the video directory under `data/videos/{uuid}`. Paths are UUID-based. ffmpeg and ffprobe are invoked with argument lists, not a shell.

Local mode has no authentication. `CLIPIT_PUBLIC_DEPLOYMENT=true` without `CLIPIT_API_TOKEN` aborts startup. Token mode checks a bearer token on video, search, and library routes. That is still one shared secret, not per-user ownership.

Optional summaries call an OpenAI-compatible `/chat/completions` endpoint only when `CLIPIT_LLM_BASE_URL` and `CLIPIT_LLM_MODEL` are set. The prompt tells the model to treat transcript and OCR text as untrusted data and to cite timestamps.
