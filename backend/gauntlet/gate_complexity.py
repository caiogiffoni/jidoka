#!/usr/bin/env python3
"""Complexity gate: fail if any function/method has cyclomatic complexity > 10."""

import subprocess
import sys

source_files = [
    "main.py",
    "auth.py",
    "models.py",
    "db.py",
    "blocked_usernames.py",
    "services.py",
    "routers/health.py",
    "routers/tasks.py",
    "routers/projects.py",
    "routers/work_blocks.py",
]
max_cc = 10
# radon grades: A=1-5, B=6-10, C=11-20; use --min C to catch anything above 10.
min_grade = "C"

print("=== Cyclomatic complexity gate ===")
proc = subprocess.run(
    ["uv", "run", "radon", "cc", "--average", "--show-complexity", "--min", min_grade] + source_files,
    capture_output=True,
    text=True,
)

violations = proc.stdout.strip()

if violations:
    print(f"FAIL: functions with complexity > {max_cc}:")
    print(violations)
    sys.exit(1)

print(f"PASS: all functions have complexity <= {max_cc}")
