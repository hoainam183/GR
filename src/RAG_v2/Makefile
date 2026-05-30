.PHONY: setup backend frontend dev

setup:
	cd frontend/chat-companion && npm install
	.venv/bin/pip install -r requirements.txt

backend:
	.venv/Scripts/python backend/main.py

frontend:
	cd frontend/chat-companion && npm run dev

dev:
	@echo "Starting backend and frontend..."
	$(MAKE) backend & $(MAKE) frontend & wait

# --- Auto Crawler Pipeline Skills ---
crawl-kehoach:
	.venv/bin/python -m pipeline.auto_crawler --module crawl

chunk-kehoach:
	.venv/bin/python -m pipeline.auto_crawler --module chunk

index-kehoach:
	.venv/bin/python -m pipeline.auto_crawler --module index

retention-kehoach:
	.venv/bin/python -m pipeline.auto_crawler --module retention

autocrawl-all:
	.venv/bin/python -m pipeline.auto_crawler --module all

rerun-incorrect-sft:
	.venv/bin/python evaluation/rerun_incorrect_sft_backend.py
