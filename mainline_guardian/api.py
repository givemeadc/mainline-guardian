"""Small Python API backed by the tested zero-dependency CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


class MainlineGuardianError(RuntimeError):
    """Raised when the controller cannot complete an operation."""


class MainlineGuardian:
    """Call Mainline Guardian from a host adapter or another agent.

    This is not a second planner or model. It records and evaluates signals
    against the active state; execution remains with the caller and user.
    """

    def __init__(self, root: str | Path = ".") -> None:
        self.root = Path(root).expanduser().resolve()
        source_script = Path(__file__).resolve().parents[1] / "scripts" / "goal_guard.py"
        packaged_script = Path(__file__).resolve().with_name("goal_guard.py")
        self._script = source_script if source_script.exists() else packaged_script
        if not self._script.exists():
            raise MainlineGuardianError(f"controller script not found: {self._script}")

    def _run(self, *args: str, check: bool = True) -> str:
        result = subprocess.run(
            [sys.executable, str(self._script), "--root", str(self.root), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if check and result.returncode:
            raise MainlineGuardianError((result.stderr or result.stdout).strip())
        return result.stdout.strip()

    def init(
        self,
        *,
        title: str,
        objective: str,
        observe: str,
        noise_band: float | None = None,
        plateau_threshold: int = 3,
    ) -> dict[str, Any]:
        args = ["init", "--title", title, "--objective", objective, "--observe", observe]
        if noise_band is not None:
            args += ["--noise-band", str(noise_band)]
        args += ["--plateau-threshold", str(plateau_threshold)]
        return json.loads(self._run(*args))

    def intake(self, message: str, *, record: bool = False) -> dict[str, Any]:
        args = ["intake", "--message", message]
        if record:
            args.append("--record")
        return json.loads(self._run(*args))

    def state(self) -> dict[str, Any]:
        path = self.root / ".mainline" / "state.json"
        if not path.exists():
            raise MainlineGuardianError(f"no state found at {path}; run init first")
        return json.loads(path.read_text(encoding="utf-8"))

    def brief(self) -> str:
        return self._run("brief")

    def audit(self) -> dict[str, Any]:
        output = self._run("audit", check=False)
        try:
            return json.loads(output)
        except json.JSONDecodeError as exc:
            raise MainlineGuardianError(output) from exc

    def checkpoint(self, note: str = "") -> str:
        args = ["checkpoint"]
        if note:
            args += ["--note", note]
        return self._run(*args)

    def handle_event(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle and persist a host event at a boundary without authorizing side effects."""
        allowed = {
            "prompt_received", "proposal_read", "tool_result", "branch_started",
            "branch_closed", "version_changed", "context_recovered", "checkout_requested",
        }
        if event_type not in allowed:
            raise ValueError(f"unsupported event type: {event_type}")
        response = json.loads(self._run(
            "event", "--type", event_type, "--payload", json.dumps(payload, ensure_ascii=False)
        ))
        response["active_goal_id"] = self.state().get("active_goal_id")
        response["execution_authorized"] = False
        return response


