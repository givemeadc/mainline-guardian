#!/usr/bin/env python3
"""Classify the latest host prompt without executing work."""

import json
import subprocess
import sys
from pathlib import Path


if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    root = Path.cwd()
    if not (root / ".mainline" / "state.json").exists():
        return 0
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 0
    prompt = payload.get("prompt") or payload.get("user_prompt") or ""
    if not isinstance(prompt, str) or not prompt.strip():
        return 0
    script = Path(__file__).resolve().parents[1] / "scripts" / "goal_guard.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--root",
            str(root),
            "intake",
            "--message",
            prompt,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return 0
    signal = json.loads(result.stdout)
    if signal.get("relation") != "candidate_branch":
        return 0
    context = (
        "Mainline signal: this prompt may be a candidate_branch. "
        "Evaluate it against the active mainline before acting; it will not automatically open a branch, "
        "switch goals, or authorize execution. 不会自动开支线、切换主线或执行。"
    )
    context = (
        "Mainline signal: this prompt may be a candidate_branch. "
        "Evaluate it against the active mainline before acting; it will not automatically open a branch, "
        "switch goals, or authorize execution. "
        "This is advisory only; no branch, goal switch, or execution is authorized."
    )
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": context,
                }
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
