.PHONY: api worker web test

api:
	cd backend && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000

worker:
	cd backend && .venv/bin/celery -A app.workers:celery_app worker --pool=solo --loglevel=info

web:
	cd frontend && npm run dev

test:
	cd backend && .venv/bin/pytest
