.PHONY: setup backend frontend dev

setup:
	cd frontend/chat-companion && npm install
	.venv/bin/pip install -r requirements.txt

backend:
	.venv/bin/python backend/main.py

frontend:
	cd frontend/chat-companion && npm run dev

dev:
	@echo "Starting backend and frontend..."
	$(MAKE) backend & $(MAKE) frontend & wait
