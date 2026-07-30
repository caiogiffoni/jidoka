.PHONY: test test-coverage bandit complexity module-size crap coverage-gate mutmut mutmut-results gauntlet gauntlet-mutmut clean

# Default: run the full pytest suite against the local Postgres dev DB
test:
	uv run pytest tests/ -v

# Run pytest with coverage report (must have Postgres running on :5432)
test-coverage:
	uv run pytest tests/ --cov=. --cov-report=term-missing --cov-report=html

# --- Structural gates (Layer 0.5) ---

bandit:
	bash gauntlet/gate_bandit.sh

complexity:
	uv run python gauntlet/gate_complexity.py

module-size:
	uv run python gauntlet/gate_module_size.py

crap:
	uv run python gauntlet/gate_crap.py

coverage-gate:
	bash gauntlet/gate_coverage.sh

# --- Mutation testing (Layer 1.5) ---

mutmut:
	uv run mutmut run

mutmut-results:
	uv run mutmut results

# --- Full gauntlet ---
# Requires Postgres running on :5432. Excludes mutation testing by default
# because it is slow; run `make gauntlet-mutmut` when you want that too.
gauntlet:
	bash gauntlet/run_gauntlet.sh

gauntlet-mutmut: gauntlet
	uv run mutmut run

# Complete verification alias: same as gauntlet-mutmut.
# Runs every gate + all pytest suites + property tests + coverage + mutation testing.
test-complete: gauntlet-mutmut

# Remove generated artifacts
clean:
	rm -rf .pytest_cache htmlcov .coverage mutants/
