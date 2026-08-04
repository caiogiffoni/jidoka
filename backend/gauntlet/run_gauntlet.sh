#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "================================"
echo "Jidoka backend testing gauntlet"
echo "================================"

# Layer 0.5: structural gates (bandit, complexity, module-size; CRAP needs
# coverage data, so it runs after the coverage gate below).
echo ""
echo "[Layer 0.5] Structural gates"
bash gauntlet/gate_bandit.sh
uv run python gauntlet/gate_complexity.py
uv run python gauntlet/gate_module_size.py

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
uv run pytest tests/test_properties.py tests/test_agent_properties.py -v --hypothesis-seed=0

# Agent-specific mutation target list
echo ""
echo "[Layer 1.5] Mutation targets"
cat gauntlet/agent_mutation_targets.txt

# Coverage gate (generates coverage data for the CRAP gate).
echo ""
echo "[Coverage] Coverage gate"
bash gauntlet/gate_coverage.sh

# CRAP gate depends on coverage data generated above.
echo ""
echo "[Layer 0.5] CRAP gate"
uv run python gauntlet/gate_crap.py

echo ""
echo "================================"
echo "Gauntlet passed"
echo "================================"
