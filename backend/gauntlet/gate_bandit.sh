#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== Bandit security gate ==="
uv run bandit -r main.py auth.py models.py db.py blocked_usernames.py -ll

echo "=== Bandit passed: no high/critical issues ==="
