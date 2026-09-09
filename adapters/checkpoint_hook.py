#!/usr/bin/env python3
"""Save a checkpoint when a workspace has Mainline Guardian state."""
from pathlib import Path
import subprocess
import sys

root = Path.cwd()
if not (root / ".mainline" / "state.json").exists():
    raise SystemExit(0)
script = Path(__file__).resolve().parents[1] / "scripts" / "goal_guard.py"
subprocess.run(
    [sys.executable, str(script), "--root", str(root), "checkpoint"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    check=False,
)
