# Clip-It

Search inside your own videos. Ask in ordinary language and jump to the moment: speech, words on screen, or a visual match.

Clip-It is a local, single-user application. The public Docker config refuses to boot unless `CLIPIT_API_TOKEN` is set. It does not have accounts or per-user ownership. Do not put it on the internet without a real authentication layer in front of the API and the video files.

## What is implemented

- Upload, ffprobe validation, background processing, transcript, OCR, frame embeddings, and search.
- Search modes: All, Speech, Screen text, Visual. Modes change which channels run.
- Reciprocal rank fusion, overlap suppression, and evidence on each hit.
- A small PyTorch ranker with pairwise logistic loss. If no artifact is present, search stays on fusion and says so.
- Saved moments, collections, relevant / not relevant feedback (stored, not auto-trained).
- Evaluation page that stays empty until `scripts/evaluate.py` writes a real report.
- Optional OpenAI-compatible summaries, off unless configured. Transcripts and OCR are sent as untrusted evidence.

## What is not done

- No multi-user accounts.
- No learned moment-boundary model. Results are overlapping windows (default 8 seconds, stride 4).
- QVHighlights is an adapter only. Its precomputed features are not loaded into Clip-It's embedding tables.
- Docker Compose is included and was not executed here, because Docker is not installed on the machine that built this repo.
- The development fixture is synthetic speech and a title card. It is not a generalization benchmark.

## Local setup

Requirements: Python 3.12, Node 22+, ffmpeg, ffprobe, Tesseract, PostgreSQL 16 with pgvector, Redis.

```bash
cp .env.example .env
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another shell, from `backend`:

```bash
celery -A app.workers:celery_app worker --pool=solo --loglevel=info
```

Use `--pool=solo` on macOS. Prefork workers and PyTorch do not get along there.

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173. The dev server proxies `/api` to port 8000.

The first speech or visual search downloads model weights into `models/` (Whisper tiny, all-MiniLM-L6-v2, OpenCLIP ViT-B-32). CPU is the default. Set `CLIPIT_TORCH_DEVICE=cuda` when a GPU is available. Whisper stays on CPU int8 unless you change `CLIPIT_WHISPER_DEVICE`.

## Docker

Host ports are 5433 for Postgres and 6380 for Redis so they do not collide with a local install. Set `CLIPIT_API_TOKEN` in `.env` before `docker compose up`, because the API container sets `CLIPIT_PUBLIC_DEPLOYMENT=true` and exits without a token.

This compose file was not run in the environment used to write the app.

## Demo

1. Upload a short video from the library.
2. Wait until the card says Ready. Failures show the stage error and a Retry button.
3. Search for a phrase you heard, then switch the mode to Speech, Screen text, or Visual.
4. Open a result. The player seeks to that timestamp. The transcript highlights the current line.
5. Save the moment, add it to a collection, and mark it relevant or not.

Generate the local fixture (macOS `say` plus ffmpeg):

```bash
cd backend
python -m scripts.generate_fixture
```

Upload each file in `fixtures/videos` using the file name as the title (`lecture-deadlocks`, and so on). Then:

```bash
python -m scripts.evaluate
```

If those titles are not in the database, the script exits without writing scores.

Train the ranker smoke test (synthetic features only):

```bash
python -m scripts.train_ranker --synthetic
```

## Troubleshooting

- Upload says the file is unreadable: ffprobe could not find a video stream.
- Processing stays queued: Redis or the Celery worker is not running. The API error says so if the queue itself is down.
- Speech search is empty on a silent file: that is expected. The video can still be Ready with a warning.
- Visual search returns a model error: the OpenCLIP weights have not downloaded, or the process cannot reach Hugging Face.
- `alembic upgrade` cannot find `vector`: install pgvector for the same PostgreSQL major version.

## Models

Recorded from the environment used to develop this repo (Python 3.12, macOS arm64):

- fastapi 0.162.0, sqlalchemy 2.1.6, alembic 1.20.1, celery 5.6.3
- torch 2.14.1, faster-whisper 1.2.1, sentence-transformers 6.2.0, open_clip_torch 3.3.0
- pgvector Python 0.5.1 against the pgvector 0.8.7 Postgres extension

See `docs/MODEL_REPORT.md` for provenance and the fact that held-out video metrics are not claimed until an evaluation file exists.
