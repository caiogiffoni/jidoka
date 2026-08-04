#!/usr/bin/env python3
"""CRAP gate: CRAP = comp^2 * (1 - cov)^3 + comp; fail if > 30."""

import json
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
crap_threshold = 30

# Run radon cc in JSON mode
cc_proc = subprocess.run(
    ["uv", "run", "radon", "cc", "-j"] + source_files,
    capture_output=True,
    text=True,
)
if cc_proc.returncode != 0:
    print(cc_proc.stderr)
    sys.exit(1)

cc_data = json.loads(cc_proc.stdout)

# Run coverage json report
cov_proc = subprocess.run(
    ["uv", "run", "coverage", "json", "--pretty-print", "-o", "-"],
    capture_output=True,
    text=True,
)
if cov_proc.returncode != 0:
    print("coverage json failed; run pytest with --cov first")
    print(cov_proc.stderr)
    sys.exit(1)

cov_data = json.loads(cov_proc.stdout)

print("=== CRAP gate ===")
violations = []
for filename, blocks in cc_data.items():
    # coverage keys are like "main.py"; radon keys are like "./main.py"
    basename = filename.lstrip("./")
    file_cov = cov_data["files"].get(basename, {})
    coverage_pct = file_cov.get("summary", {}).get("percent_covered", 0) / 100

    for block in blocks:
        name = block.get("name", "<unknown>")
        complexity = block.get("complexity", 1)
        crap = complexity ** 2 * (1 - coverage_pct) ** 3 + complexity
        if crap > crap_threshold:
            violations.append((basename, name, complexity, coverage_pct, crap))

if violations:
    print(f"FAIL: functions with CRAP > {crap_threshold}:")
    for filename, name, cc, cov, crap in violations:
        print(f"  {filename}::{name}  CC={cc}  cov={cov:.1%}  CRAP={crap:.1f}")
    sys.exit(1)

print(f"PASS: all functions have CRAP <= {crap_threshold}")
