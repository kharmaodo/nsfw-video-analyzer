.PHONY: up down logs test-backend build-frontend verify

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f api worker frontend

test-backend:
	cd backend && .venv/bin/pytest --cov=app

build-frontend:
	cd frontend && npm run lint && npm run build

verify: test-backend build-frontend
