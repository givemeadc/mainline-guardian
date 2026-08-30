#!/usr/bin/env python3
"""Emit a compact recovery brief; remain silent for unrelated workspaces."""
from pathlib import Path
import json
import subprocess
import sys

root = Path.cwd()
if not (root / ".mainline" / "state.json").exists():
    raise SystemExit(0)
script = Path(__file__).resolve().parents[1] / "scripts" / "goal_guard.py"
result = subprocess.run(
    [sys.executable, str(script), "--root", str(root), "brief"],
    capture_output=True,
    text=True,
    check=False,
)
if result.returncode == 0 and result.stdout.strip():
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": result.stdout.strip()}}))
