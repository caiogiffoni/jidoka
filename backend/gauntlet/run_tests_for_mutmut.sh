#!/bin/bash
set -e

export JWT_SECRET_KEY="${JWT_SECRET_KEY:-test-secret-for-pytest}"
python -m pytest -x -q
