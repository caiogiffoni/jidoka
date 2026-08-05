.PHONY: install install-backend install-frontend dev backend frontend \
  test test-coverage test-frontend bandit complexity module-size \
  crap coverage-gate mutmut mutmut-results gauntlet gauntlet-mutmut \
  test-complete db-purge clean

# ---------------------------------------------------------------------------
# Local development
# ---------------------------------------------------------------------------

# Install all project dependencies (backend + frontend).
install: install-backend install-frontend

# Install backend Python dependencies using uv.
install-backend:
	cd backend && uv sync --locked

# Install frontend Node.js dependencies using pnpm.
install-frontend:
	cd frontend && pnpm install

# Start the whole stack (Postgres + backend) via Docker Compose.
# Run `make frontend` in another terminal for the Next.js dev server.
dev:
	docker compose up --watch

# Start only the backend dev server (expects Postgres on :5432).
backend:
	cd backend && uv run fastapi dev main.py

# Start the Next.js frontend dev server.
frontend:
	cd frontend && pnpm dev

# ---------------------------------------------------------------------------
# Backend tests
# ---------------------------------------------------------------------------

# Full pytest suite against the local Postgres dev DB (must be on :5432).
# Excludes LLM tests by default.
test:
	cd backend && uv run pytest tests/ -v

# pytest with terminal + HTML coverage report.
# Excludes LLM tests by default.
test-coverage:
	cd backend && uv run pytest tests/ --cov=. --cov-report=term-missing --cov-report=html

# Run tests that exercise the real LLM via OpenRouter (requires OPENROUTER_API_KEY).
test-llm:
	cd backend && uv run pytest tests/llm/ -v -m llm

# ---------------------------------------------------------------------------
# Frontend tests
# ---------------------------------------------------------------------------

test-frontend:
	cd frontend && pnpm test

# ---------------------------------------------------------------------------
# Structural gates (Layer 0.5)
# ---------------------------------------------------------------------------

bandit:
	cd backend && bash gauntlet/gate_bandit.sh

complexity:
	cd backend && uv run python gauntlet/gate_complexity.py

module-size:
	cd backend && uv run python gauntlet/gate_module_size.py

crap:
	cd backend && uv run python gauntlet/gate_crap.py

coverage-gate:
	cd backend && bash gauntlet/gate_coverage.sh

# ---------------------------------------------------------------------------
# Mutation testing (Layer 1.5)
# ---------------------------------------------------------------------------

mutmut:
	cd backend && uv run mutmut run

mutmut-results:
	cd backend && uv run mutmut results

# ---------------------------------------------------------------------------
# Full gauntlet
# ---------------------------------------------------------------------------

# All gates + unit + acceptance + property tests + coverage gate.
# Requires Postgres running on :5432. Mutation testing is excluded by default
# because it is slow; use `make gauntlet-mutmut` or `make test-complete`.
gauntlet:
	cd backend && bash gauntlet/run_gauntlet.sh

gauntlet-mutmut: gauntlet
	cd backend && uv run mutmut run

# Complete verification: every gate, every test, plus mutation testing.
test-complete: gauntlet-mutmut

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

# Purge the local Postgres volume and recreate the stack.
# This is destructive: all local data is lost. Pass FORCE=1 to skip the prompt.
db-purge:
	@if [ "$(FORCE)" != "1" ]; then \
	  read -p "Delete local Postgres data? [y/N] " confirm && [ "$$confirm" = "y" ] || (echo "Aborted."; exit 1); \
	fi
	docker compose down -v
	docker compose up -d

# ---------------------------------------------------------------------------
# Cleanup generated artifacts
# ---------------------------------------------------------------------------

clean:
	cd backend && rm -rf .pytest_cache htmlcov .coverage mutants/
	cd frontend && rm -rf .next
