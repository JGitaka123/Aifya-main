.PHONY: dev dev-down dev-logs test test-web test-api test-api-full test-billing test-sync lint lint-web lint-api lint-api-full lint-go typecheck typecheck-full typecheck-shared typecheck-web typecheck-api db-migrate db-revision db-downgrade clean

# --- Development ---
dev:
	docker compose up -d

dev-down:
	docker compose down

dev-logs:
	docker compose logs -f

# --- Testing ---
test: test-web test-api test-billing test-sync

test-web:
	cd apps/web && pnpm test

test-api:
	cd services/api-gateway && python -m pytest -q

test-api-full:
	cd services/api-gateway && python -m pytest -v

test-billing:
	cd services/billing-service && go test ./...

test-sync:
	cd services/sync-service && go test ./...

# --- Linting ---
lint: lint-web lint-api lint-go

lint-web:
	cd apps/web && pnpm lint

lint-api:
	cd services/api-gateway && python -m ruff check app && python -m mypy app

lint-api-full:
	cd services/api-gateway && python -m ruff check . && python -m ruff format --check .

lint-go:
	test -z "$$(gofmt -l services/billing-service services/sync-service)"
	cd services/billing-service && go vet ./...
	cd services/sync-service && go vet ./...

# --- Type Checking ---
typecheck: typecheck-shared typecheck-web

typecheck-full: typecheck typecheck-api

typecheck-shared:
	# packages/shared has no package.json (it is consumed via the
	# @aifya/shared tsconfig path alias), so check it with tsc directly.
	pnpm --filter @aifya/web exec tsc --noEmit -p ../../packages/shared/tsconfig.json

typecheck-web:
	cd apps/web && pnpm typecheck

typecheck-api:
	cd services/api-gateway && python -m mypy app

# --- Database ---
db-migrate:
	cd services/api-gateway && alembic upgrade head

db-revision:
	cd services/api-gateway && alembic revision --autogenerate -m "$(msg)"

db-downgrade:
	cd services/api-gateway && alembic downgrade -1

# --- Clean ---
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name node_modules -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .next -exec rm -rf {} + 2>/dev/null || true
