#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

coverage_threshold=90

echo "=== Coverage gate (threshold ${coverage_threshold}%) ==="
uv run pytest tests/ \
    --cov=main --cov=auth --cov=models --cov=db --cov=blocked_usernames \
    --cov=services --cov=routers \
    --cov-report=term \
    --cov-fail-under="${coverage_threshold}"

echo "=== Coverage passed ==="
