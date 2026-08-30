import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "goal_guard.py"

def run(root: Path, *args: str, check=True):
    result = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), *args], capture_output=True, text=True)
    if check and result.returncode:
        raise AssertionError(result.stderr + result.stdout)
    return result

class V2ContractTests(unittest.TestCase):
    def test_init_uses_mainline_and_minimal_user_observation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = run(root, "init", "--title", "Deploy app", "--objective", "App works in target environment", "--observe", "Run the core user flow successfully")
            state = json.loads((root / ".mainline" / "state.json").read_text(encoding="utf-8"))
            criterion = state["goals"]["G1"]["criteria"]["C1"]
            self.assertEqual(criterion["closer"], "user")
            self.assertEqual(criterion["observe"], "Run the core user flow successfully")

    def test_user_criterion_waits_for_attestation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(root, "init", "--title", "Deploy app", "--objective", "App works", "--observe", "Core flow succeeds")
            result = run(root, "criterion", "close", "--id", "C1", "--observed", "Core flow succeeds in clean environment", "--object", "app-v1")
            self.assertIn("awaiting-attestation", result.stdout)
            audit = run(root, "audit", check=False)
            self.assertIn("awaiting_attestation", audit.stdout)
            self.assertEqual(audit.returncode, 1)

    def test_version_log_and_brief_persist_negative_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(root, "init", "--title", "Optimize model", "--objective", "Reach target latency", "--observe", "Target latency is met in production-like run")
            run(root, "version", "log", "--change", "Wider context window", "--hypothesis", "More context improves latency", "--metric", "latency unchanged", "--verdict", "no_gain")
            ledger = (root / ".mainline" / "ledger.jsonl").read_text(encoding="utf-8")
            self.assertIn("no_gain", ledger)
            brief = run(root, "brief")
            self.assertIn("Reach target latency", brief.stdout)

    def test_version_change_stales_observation_for_changed_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(root, "init", "--title", "Main", "--objective", "Finish task", "--observe", "Task works")
            run(root, "criterion", "close", "--id", "C1", "--observed", "Task works in clean flow", "--object", "app-v1")
            run(root, "criterion", "attest", "--id", "C1", "--note", "用户说 \"看起来可以\"")
            run(root, "version", "log", "--change", "v2", "--hypothesis", "fix bug", "--metric", "pass", "--verdict", "improved", "--artifact", "app-v1")
            state = json.loads((root / ".mainline" / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["goals"]["G1"]["criteria"]["C1"]["status"], "stale")

    def test_contract_amendment_supersedes_prior_attestation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(root, "init", "--title", "Main", "--objective", "Finish task", "--observe", "Task works")
            run(root, "criterion", "close", "--id", "C1", "--observed", "Task works in clean flow", "--object", "app-v1")
            run(root, "criterion", "attest", "--id", "C1", "--note", "用户说 \"看起来可以\"")
            run(root, "contract", "amend", "--reason", "Core flow requirement changed", "--affects", "C1")
            state = json.loads((root / ".mainline" / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["goals"]["G1"]["criteria"]["C1"]["status"], "superseded")

    def test_discovery_requires_an_exit_outcome(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(root, "init", "--title", "Main", "--objective", "Finish task", "--observe", "Task works")
            run(root, "criterion", "add", "--text", "Find viable runtime", "--observe", "Compare two runtimes", "--closer", "agent", "--kind", "discovery", "--budget", "2 experiments / 1 hour")
            missing_exit = run(root, "criterion", "close", "--id", "C2", "--observed", "Runtime A is viable", "--object", "runtime-a", check=False)
            self.assertNotEqual(missing_exit.returncode, 0)
            run(root, "criterion", "close", "--id", "C2", "--observed", "Runtime A is viable in benchmark", "--object", "runtime-a", "--discovery-outcome", "result_criterion")

    def test_review_requires_route_decision(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(root, "init", "--title", "Main", "--objective", "Finish task", "--observe", "Task works")
            result = run(root, "review", check=False)
            self.assertNotEqual(result.returncode, 0)
            run(root, "review", "--decision", "explore", "--reason", "No gain after comparable runs")

    def test_action_requires_failure_decision(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(root, "init", "--title", "Build app", "--objective", "App works", "--observe", "Core flow succeeds")
            result = run(root, "action", "declare", "--description", "Compute hash", "--target", "app.zip", "--failure-action", "", check=False)
            self.assertNotEqual(result.returncode, 0)

    def test_contract_amend_requires_scope_and_preserves_unaffected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(root, "init", "--title", "Main", "--objective", "Finish task", "--observe", "Task works")
            run(root, "criterion", "add", "--text", "Docs exist", "--observe", "README renders in viewer", "--closer", "agent")
            result = run(root, "contract", "amend", "--reason", "Changed one requirement", check=False)
            self.assertNotEqual(result.returncode, 0)
            run(root, "criterion", "close", "--id", "C2", "--observed", "README renders in viewer", "--object", "docs-v1")
            run(root, "contract", "amend", "--reason", "Changed one requirement", "--affects", "C1")
            state = json.loads((root / ".mainline" / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["goals"]["G1"]["criteria"]["C2"]["status"], "verified")

    def test_observed_completion_label_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(root, "init", "--title", "Main", "--objective", "Finish task", "--observe", "Task works")
            result = run(root, "criterion", "close", "--id", "C1", "--observed", "done", "--object", "app-v1", check=False)
            self.assertNotEqual(result.returncode, 0)

    def test_attestation_requires_a_user_quote(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(root, "init", "--title", "Main", "--objective", "Finish task", "--observe", "Task works")
            run(root, "criterion", "close", "--id", "C1", "--observed", "Task works in clean flow", "--object", "app-v1")
            result = run(root, "criterion", "attest", "--id", "C1", "--note", "confirmed by agent", check=False)
            self.assertNotEqual(result.returncode, 0)

    def test_artifact_stale_matches_relative_and_absolute_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(root, "init", "--title", "Main", "--objective", "Finish task", "--observe", "Task works")
            run(root, "criterion", "close", "--id", "C1", "--observed", "Task works in clean flow", "--object", "output/app")
            run(root, "version", "log", "--change", "v2", "--hypothesis", "fix", "--metric", "pass", "--verdict", "improved", "--artifact", str(root / "output" / "app"))
            state = json.loads((root / ".mainline" / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["goals"]["G1"]["criteria"]["C1"]["status"], "stale")

    def test_audit_lists_other_goal_work(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(root, "init", "--title", "One", "--objective", "Finish one", "--observe", "One works")
            run(root, "goal", "add", "--title", "Two", "--objective", "Finish two")
            run(root, "goal", "switch", "--goal-id", "G2", "--reason", "user requested parallel work")
            audit = json.loads(run(root, "audit", check=False).stdout)
            self.assertEqual(audit["other_goals"][0]["goal_id"], "G1")
            self.assertEqual(audit["other_goals"][0]["unproved_count"], 1)

    def test_brief_is_compact_and_contains_ledger_knowledge(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(root, "init", "--title", "Optimize", "--objective", "Reach target", "--observe", "Target run works")
            run(root, "version", "log", "--change", "Wider window", "--hypothesis", "Capacity is the limit", "--metric", "unchanged", "--verdict", "no_gain")
            brief = run(root, "brief").stdout.splitlines()
            self.assertLessEqual(len(brief), 5)
            self.assertTrue(any(line.startswith("Negative:") for line in brief))

    def test_discovery_requires_a_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(root, "init", "--title", "Main", "--objective", "Finish task", "--observe", "Task works")
            result = run(root, "criterion", "add", "--text", "Find runtime", "--observe", "Compare runtimes", "--closer", "agent", "--kind", "discovery", check=False)
            self.assertNotEqual(result.returncode, 0)

    def test_continuous_plateau_ignores_old_failures_and_honors_noise_band(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(root, "init", "--title", "Main", "--objective", "Improve score", "--observe", "Score meets target", "--noise-band", "0.5", "--plateau-threshold", "3")
            for delta, verdict in [(0.0, "no_gain"), (0.0, "no_gain"), (2.0, "improved"), (0.2, "improved"), (0.1, "improved"), (0.3, "improved")]:
                run(root, "version", "log", "--change", "trial", "--hypothesis", "test", "--metric", "score", "--delta", str(delta), "--verdict", verdict)
            payload = json.loads(run(root, "review", "--decision", "explore").stdout)
            self.assertEqual(payload["consecutive_non_improving"], 3)
            self.assertTrue(payload["plateau_signal"])

if __name__ == "__main__":
    unittest.main()
