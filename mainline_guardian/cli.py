"""Console entry point for source checkouts and editable installs."""

from __future__ import annotations

import runpy
from pathlib import Path


def main() -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "goal_guard.py"
    if not script.exists():
        raise SystemExit("mainline-guardian source scripts are missing")
    runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()

