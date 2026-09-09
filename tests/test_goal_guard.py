import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "goal_guard.py"


def run(root: Path, *args: str, check=True):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and result.returncode:
        raise AssertionError(result.stderr + result.stdout)
    return result


class GoalGuardTests(unittest.TestCase):
    def test_init_and_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(
                root,
                "init",
                "--title",
                "Build skill",
                "--objective",
                "Create a goal alignment skill",
                "--observe",
                "Skill is usable in a fresh task",
            )
            self.assertTrue((root / ".mainline" / "state.json").exists())
            self.assertTrue((root / ".mainline" / "checkpoint.md").exists())
            state = json.loads(
                (root / ".mainline" / "state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(state["active_goal_id"], "G1")
            self.assertEqual(state["goals"]["G1"]["criteria"]["C1"]["closer"], "user")

    def test_branch_close_emits_return_sentence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(
                root,
                "init",
                "--title",
                "Main",
                "--objective",
                "Finish the main task",
                "--observe",
                "Main task works",
            )
            run(
                root,
                "branch",
                "open",
                "--kind",
                "exploration",
                "--reason",
                "Inspect another tool",
                "--exit-criteria",
                "Record one conclusion",
                "--return-to",
                "main task",
            )
            run(
                root,
                "branch",
                "assess",
                "--id",
                "B1",
                "--mainline-relation",
                "May help the main task",
                "--target-criteria",
                "C1",
                "--ledger-refs",
                "none: first comparison",
                "--cost-risk",
                "low",
                "--recommendation",
                "test",
            )
            result = run(
                root,
                "branch",
                "close",
                "--id",
                "B1",
                "--result-type",
                "evidence",
                "--result",
                "Tool is compatible",
                "--remaining",
                "implementation",
                "--next",
                "implement main task",
            )
            self.assertIn("Back to: main task", result.stdout)
            self.assertIn("Next: implement main task", result.stdout)

    def test_explicit_switch_is_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(
                root,
                "init",
                "--title",
                "Main",
                "--objective",
                "Finish A",
                "--observe",
                "A works",
            )
            run(
                root,
                "goal",
                "add",
                "--title",
                "Second",
                "--objective",
                "Finish B",
                "--observe",
                "B works",
            )
            run(
                root,
                "goal",
                "switch",
                "--goal-id",
                "G2",
                "--reason",
                "explicit user request",
            )
            state = json.loads(
                (root / ".mainline" / "state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(state["active_goal_id"], "G2")
            self.assertEqual(state["events"][-1]["operation"], "switch_goal")

    def test_decision_is_written_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(
                root,
                "init",
                "--title",
                "Main",
                "--objective",
                "Finish A",
                "--observe",
                "A works",
            )
            run(
                root,
                "decision",
                "record",
                "--proposal",
                "A",
                "--mainline-relation",
                "reduces latency",
                "--ledger-refs",
                "v3 no gain",
                "--cost-risk",
                "medium",
                "--decision",
                "test",
            )
            lines = (
                (root / ".mainline" / "ledger.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            )
            self.assertEqual(json.loads(lines[-1])["kind"], "decision")

    def test_audit_rejects_missing_attestation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(
                root,
                "init",
                "--title",
                "Main",
                "--objective",
                "Finish task",
                "--observe",
                "Task works",
            )
            run(
                root,
                "criterion",
                "close",
                "--id",
                "C1",
                "--observed",
                "Task works in environment",
                "--object",
                "app-v1",
            )
            result = run(root, "audit", check=False)
            self.assertEqual(result.returncode, 1)
            self.assertIn("awaiting_attestation", result.stdout)


if __name__ == "__main__":
    unittest.main()
