#!/usr/bin/env python3
"""Module-size advisory gate: warn if source modules exceed a guideline LOC."""

import subprocess
import sys

source_files = ["main.py", "auth.py", "models.py", "db.py", "blocked_usernames.py"]
soft_limit = 300
hard_limit = 500

print("=== Module-size gate ===")
proc = subprocess.run(
    ["uv", "run", "radon", "raw", "-s"] + source_files,
    capture_output=True,
    text=True,
)

if proc.returncode != 0:
    print(proc.stderr)
    sys.exit(1)

print(proc.stdout)

# Parse SLOC values: filename line followed by indented metrics
violations = []
current_file = None
for line in proc.stdout.splitlines():
    stripped = line.strip()
    if not stripped:
        continue
    if not line.startswith(" ") and not line.startswith("\t"):
        if stripped.endswith(".py"):
            current_file = stripped.lstrip("./")
        else:
            current_file = None
    elif stripped.startswith("SLOC:") and current_file:
        sloc = int(stripped.split(":", 1)[1].strip())
        if sloc > hard_limit:
            violations.append((current_file, sloc, "HARD"))
        elif sloc > soft_limit:
            violations.append((current_file, sloc, "SOFT"))

if violations:
    print("Module-size findings:")
    for filename, sloc, level in violations:
        print(f"  {level}: {filename} has {sloc} SLOC (soft limit {soft_limit}, hard limit {hard_limit})")
    if any(level == "HARD" for _, _, level in violations):
        sys.exit(1)

print("PASS: modules within size guidelines")
