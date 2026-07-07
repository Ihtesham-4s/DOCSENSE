.PHONY: run backend frontend build-frontend ingest cli

run:
	python dev.py

backend:
	cd backend && python -m uvicorn app:app --reload

frontend:
	cd frontend && npm run dev

build-frontend:
	cd frontend && npm run build

ingest:
	python database_create.py

cli:
	python main.py