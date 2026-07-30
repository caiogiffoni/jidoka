#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "================================"
echo "Jidoka backend testing gauntlet"
echo "================================"

# Layer 0.5: structural gates
echo ""
echo "[Layer 0.5] Structural gates"
bash gauntlet/gate_bandit.sh
uv run python gauntlet/gate_complexity.py
uv run python gauntlet/gate_module_size.py
uv run python gauntlet/gate_crap.py

# Layer 1: unit / gap-fill tests
echo ""
echo "[Layer 1] Unit tests"
uv run pytest tests/ -v

# Layer 2: acceptance tests
echo ""
echo "[Layer 2] Acceptance tests"
uv run pytest tests/acceptance/ -v -m "critical or standard"

# Layer 2.5: property tests
echo ""
echo "[Layer 2.5] Property tests"
uv run pytest tests/test_properties.py -v --hypothesis-seed=0

# Coverage gate
echo ""
echo "[Coverage] Coverage gate"
bash gauntlet/gate_coverage.sh

echo ""
echo "================================"
echo "Gauntlet passed"
echo "================================"
