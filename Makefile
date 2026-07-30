.PHONY: dev backend frontend test test-coverage test-frontend \
  bandit complexity module-size crap coverage-gate \
  mutmut mutmut-results gauntlet gauntlet-mutmut test-complete \
  clean

# ---------------------------------------------------------------------------
# Local development
# ---------------------------------------------------------------------------

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
test:
	cd backend && uv run pytest tests/ -v

# pytest with terminal + HTML coverage report.
test-coverage:
	cd backend && uv run pytest tests/ --cov=. --cov-report=term-missing --cov-report=html

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
# Cleanup generated artifacts
# ---------------------------------------------------------------------------

clean:
	cd backend && rm -rf .pytest_cache htmlcov .coverage mutants/
	cd frontend && rm -rf .next
