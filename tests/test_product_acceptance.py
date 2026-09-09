import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PACKAGE = Path(__file__).parents[1]
SOURCE = PACKAGE / "scripts" / "goal_guard.py"


def run(script: Path, root: Path, *args: str, check: bool = True):
    result = subprocess.run(
        [sys.executable, str(script), "--root", str(root), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and result.returncode:
        raise AssertionError(result.stderr + result.stdout)
    return result


class ProductAcceptanceTests(unittest.TestCase):
    def test_clean_package_supports_the_real_mainline_workflow(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            installed = Path(directory) / "mainline-guardian"
            workspace.mkdir()
            shutil.copytree(
                PACKAGE,
                installed,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".mainline"),
            )
            script = installed / "scripts" / "goal_guard.py"

            run(
                script,
                workspace,
                "init",
                "--title",
                "Deploy the software",
                "--objective",
                "Make the software usable in the target environment",
                "--observe",
                "A real user completes the core workflow in a clean target environment",
                "--noise-band",
                "0.5",
                "--plateau-threshold",
                "3",
            )

            signal = json.loads(
                run(
                    script,
                    workspace,
                    "intake",
                    "--message",
                    "I found a new cache architecture paper that may reduce deployment latency",
                ).stdout
            )
            self.assertEqual(signal["relation"], "candidate_branch")
            state = json.loads(
                (workspace / ".mainline" / "state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(state["branches"], {})

            run(
                script,
                workspace,
                "branch",
                "open",
                "--kind",
                "exploration",
                "--reason",
                "Evaluate one cache mechanism",
                "--exit-criteria",
                "Decide whether one bounded benchmark is justified",
                "--return-to",
                "Deploy the software",
                "--target-criteria",
                "C1",
            )
            run(
                script,
                workspace,
                "branch",
                "assess",
                "--id",
                "B1",
                "--mainline-relation",
                "May reduce deployment latency",
                "--target-criteria",
                "C1",
                "--ledger-refs",
                "none: no comparable local attempt",
                "--cost-risk",
                "one hour and reversible",
                "--recommendation",
                "test",
            )
            returned = run(
                script,
                workspace,
                "branch",
                "close",
                "--id",
                "B1",
                "--result-type",
                "decision_candidate",
                "--result",
                "The paper supports a bounded cache benchmark",
                "--helped",
                "It suggests one low-risk deployment experiment",
                "--not-adopted",
                "Do not replace the current architecture",
                "--remaining",
                "Benchmark not run",
                "--next",
                "Return to deployment and run one bounded benchmark",
                "--decision",
                "test",
            )
            self.assertIn("Back to: Deploy the software", returned.stdout)
            self.assertIn(
                "Not adopted: Do not replace the current architecture", returned.stdout
            )

            for index in range(3):
                run(
                    script,
                    workspace,
                    "version",
                    "log",
                    "--route",
                    "current",
                    "--change",
                    f"Small tuning {index}",
                    "--hypothesis",
                    "A local parameter change will improve deployment",
                    "--metric",
                    "latency unchanged",
                    "--delta",
                    "0.1",
                    "--verdict",
                    "improved",
                )
            review = json.loads(
                run(
                    script,
                    workspace,
                    "review",
                    "--decision",
                    "explore",
                    "--reason",
                    "The current route has reached a continuous plateau",
                ).stdout
            )
            self.assertTrue(review["plateau_signal"])
            self.assertEqual(review["route_decision"], "explore")

            pending = run(script, workspace, "audit", check=False)
            self.assertEqual(pending.returncode, 1)
            self.assertIn("not_proved", pending.stdout)
            run(
                script,
                workspace,
                "criterion",
                "close",
                "--id",
                "C1",
                "--observed",
                "A clean target environment completed the core workflow",
                "--object",
                "build/app-v1",
            )
            run(
                script,
                workspace,
                "criterion",
                "attest",
                "--id",
                "C1",
                "--note",
                "User said: 'the core workflow works for me'",
            )
            final = json.loads(run(script, workspace, "audit").stdout)
            self.assertEqual(final["status"], "complete")
            self.assertTrue((workspace / ".mainline" / "checkpoint.md").exists())
            self.assertTrue((workspace / ".mainline" / "audit.json").exists())

            # A clean package must not ship runtime state or interpreter caches.
            shipped = [p for p in installed.rglob("*") if p.is_file()]
            self.assertFalse(any(".mainline" in p.parts for p in shipped))
            self.assertFalse(
                any(p.suffix == ".pyc" or "__pycache__" in p.parts for p in shipped)
            )


if __name__ == "__main__":
    unittest.main()
