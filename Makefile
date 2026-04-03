.PHONY: install dev backend frontend

install:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

backend:
	cd backend && python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm run dev

dev:
	@echo "Starting backend and frontend..."
	@make backend & make frontend
