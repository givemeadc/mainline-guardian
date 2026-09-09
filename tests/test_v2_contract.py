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


class V2ContractTests(unittest.TestCase):
    def test_init_uses_mainline_and_minimal_user_observation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = run(
                root,
                "init",
                "--title",
                "Deploy app",
                "--objective",
                "App works in target environment",
                "--observe",
                "Run the core user flow successfully",
            )
            state = json.loads(
                (root / ".mainline" / "state.json").read_text(encoding="utf-8")
            )
            criterion = state["goals"]["G1"]["criteria"]["C1"]
            self.assertEqual(criterion["closer"], "user")
            self.assertEqual(
                criterion["observe"], "Run the core user flow successfully"
            )

    def test_user_criterion_waits_for_attestation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(
                root,
                "init",
                "--title",
                "Deploy app",
                "--objective",
                "App works",
                "--observe",
                "Core flow succeeds",
            )
            result = run(
                root,
                "criterion",
                "close",
                "--id",
                "C1",
                "--observed",
                "Core flow succeeds in clean environment",
                "--object",
                "app-v1",
            )
            self.assertIn("awaiting-attestation", result.stdout)
            audit = run(root, "audit", check=False)
            self.assertIn("awaiting_attestation", audit.stdout)
            self.assertEqual(audit.returncode, 1)

    def test_version_log_and_brief_persist_negative_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(
                root,
                "init",
                "--title",
                "Optimize model",
                "--objective",
                "Reach target latency",
                "--observe",
                "Target latency is met in production-like run",
            )
            run(
                root,
                "version",
                "log",
                "--change",
                "Wider context window",
                "--hypothesis",
                "More context improves latency",
                "--metric",
                "latency unchanged",
                "--verdict",
                "no_gain",
            )
            ledger = (root / ".mainline" / "ledger.jsonl").read_text(encoding="utf-8")
            self.assertIn("no_gain", ledger)
            brief = run(root, "brief")
            self.assertIn("Reach target latency", brief.stdout)

    def test_version_change_stales_observation_for_changed_artifact(self):
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
                "Task works in clean flow",
                "--object",
                "app-v1",
            )
            run(
                root,
                "criterion",
                "attest",
                "--id",
                "C1",
                "--note",
                '用户说 "看起来可以"',
            )
            run(
                root,
                "version",
                "log",
                "--change",
                "v2",
                "--hypothesis",
                "fix bug",
                "--metric",
                "pass",
                "--verdict",
                "improved",
                "--artifact",
                "app-v1",
            )
            state = json.loads(
                (root / ".mainline" / "state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(state["goals"]["G1"]["criteria"]["C1"]["status"], "stale")

    def test_contract_amendment_supersedes_prior_attestation(self):
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
                "Task works in clean flow",
                "--object",
                "app-v1",
            )
            run(
                root,
                "criterion",
                "attest",
                "--id",
                "C1",
                "--note",
                '用户说 "看起来可以"',
            )
            run(
                root,
                "contract",
                "amend",
                "--reason",
                "Core flow requirement changed",
                "--affects",
                "C1",
            )
            state = json.loads(
                (root / ".mainline" / "state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                state["goals"]["G1"]["criteria"]["C1"]["status"], "superseded"
            )

    def test_discovery_requires_an_exit_outcome(self):
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
                "add",
                "--text",
                "Find viable runtime",
                "--observe",
                "Compare two runtimes",
                "--closer",
                "agent",
                "--kind",
                "discovery",
                "--budget",
                "2 experiments / 1 hour",
            )
            missing_exit = run(
                root,
                "criterion",
                "close",
                "--id",
                "C2",
                "--observed",
                "Runtime A is viable",
                "--object",
                "runtime-a",
                check=False,
            )
            self.assertNotEqual(missing_exit.returncode, 0)
            run(
                root,
                "criterion",
                "close",
                "--id",
                "C2",
                "--observed",
                "Runtime A is viable in benchmark",
                "--object",
                "runtime-a",
                "--discovery-outcome",
                "result_criterion",
            )

    def test_review_requires_route_decision(self):
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
            result = run(root, "review", check=False)
            self.assertNotEqual(result.returncode, 0)
            run(
                root,
                "review",
                "--decision",
                "explore",
                "--reason",
                "No gain after comparable runs",
            )

    def test_action_requires_failure_decision(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(
                root,
                "init",
                "--title",
                "Build app",
                "--objective",
                "App works",
                "--observe",
                "Core flow succeeds",
            )
            result = run(
                root,
                "action",
                "declare",
                "--description",
                "Compute hash",
                "--target",
                "app.zip",
                "--failure-action",
                "",
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)

    def test_action_rejects_proxy_only_failure_action(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(
                root,
                "init",
                "--title",
                "Build app",
                "--objective",
                "App works",
                "--observe",
                "Core flow succeeds",
            )
            result = run(
                root,
                "action",
                "declare",
                "--description",
                "Compute hash",
                "--target",
                "app.zip",
                "--failure-action",
                "increase confidence",
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("different next action", result.stderr)

    def test_noise_band_requires_delta_for_improved_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(
                root,
                "init",
                "--title",
                "Optimize",
                "--objective",
                "Improve score",
                "--observe",
                "Score meets target",
                "--noise-band",
                "0.5",
            )
            result = run(
                root,
                "version",
                "log",
                "--change",
                "trial",
                "--hypothesis",
                "test",
                "--metric",
                "score",
                "--verdict",
                "improved",
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--delta is required", result.stderr)

    def test_contract_amend_requires_scope_and_preserves_unaffected(self):
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
                "add",
                "--text",
                "Docs exist",
                "--observe",
                "README renders in viewer",
                "--closer",
                "agent",
            )
            result = run(
                root,
                "contract",
                "amend",
                "--reason",
                "Changed one requirement",
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            run(
                root,
                "criterion",
                "close",
                "--id",
                "C2",
                "--observed",
                "README renders in viewer",
                "--object",
                "docs-v1",
            )
            run(
                root,
                "contract",
                "amend",
                "--reason",
                "Changed one requirement",
                "--affects",
                "C1",
            )
            state = json.loads(
                (root / ".mainline" / "state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                state["goals"]["G1"]["criteria"]["C2"]["status"], "verified"
            )

    def test_observed_completion_label_is_rejected(self):
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
            result = run(
                root,
                "criterion",
                "close",
                "--id",
                "C1",
                "--observed",
                "done",
                "--object",
                "app-v1",
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)

    def test_attestation_requires_a_user_quote(self):
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
                "Task works in clean flow",
                "--object",
                "app-v1",
            )
            result = run(
                root,
                "criterion",
                "attest",
                "--id",
                "C1",
                "--note",
                "confirmed by agent",
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)

    def test_artifact_stale_matches_relative_and_absolute_paths(self):
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
                "Task works in clean flow",
                "--object",
                "output/app",
            )
            run(
                root,
                "version",
                "log",
                "--change",
                "v2",
                "--hypothesis",
                "fix",
                "--metric",
                "pass",
                "--verdict",
                "improved",
                "--artifact",
                str(root / "output" / "app"),
            )
            state = json.loads(
                (root / ".mainline" / "state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(state["goals"]["G1"]["criteria"]["C1"]["status"], "stale")

    def test_audit_lists_other_goal_work(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(
                root,
                "init",
                "--title",
                "One",
                "--objective",
                "Finish one",
                "--observe",
                "One works",
            )
            run(
                root,
                "goal",
                "add",
                "--title",
                "Two",
                "--objective",
                "Finish two",
                "--observe",
                "Two works",
            )
            run(
                root,
                "goal",
                "switch",
                "--goal-id",
                "G2",
                "--reason",
                "user requested parallel work",
            )
            audit = json.loads(run(root, "audit", check=False).stdout)
            self.assertEqual(audit["other_goals"][0]["goal_id"], "G1")
            self.assertEqual(audit["other_goals"][0]["unproved_count"], 1)

    def test_brief_is_compact_and_contains_ledger_knowledge(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(
                root,
                "init",
                "--title",
                "Optimize",
                "--objective",
                "Reach target",
                "--observe",
                "Target run works",
            )
            run(
                root,
                "version",
                "log",
                "--change",
                "Wider window",
                "--hypothesis",
                "Capacity is the limit",
                "--metric",
                "unchanged",
                "--verdict",
                "no_gain",
            )
            brief = run(root, "brief").stdout.splitlines()
            self.assertLessEqual(len(brief), 5)
            self.assertTrue(any(line.startswith("Negative:") for line in brief))

    def test_discovery_requires_a_budget(self):
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
            result = run(
                root,
                "criterion",
                "add",
                "--text",
                "Find runtime",
                "--observe",
                "Compare runtimes",
                "--closer",
                "agent",
                "--kind",
                "discovery",
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)

    def test_continuous_plateau_ignores_old_failures_and_honors_noise_band(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(
                root,
                "init",
                "--title",
                "Main",
                "--objective",
                "Improve score",
                "--observe",
                "Score meets target",
                "--noise-band",
                "0.5",
                "--plateau-threshold",
                "3",
            )
            for delta, verdict in [
                (0.0, "no_gain"),
                (0.0, "no_gain"),
                (2.0, "improved"),
                (0.2, "improved"),
                (0.1, "improved"),
                (0.3, "improved"),
            ]:
                run(
                    root,
                    "version",
                    "log",
                    "--change",
                    "trial",
                    "--hypothesis",
                    "test",
                    "--metric",
                    "score",
                    "--delta",
                    str(delta),
                    "--verdict",
                    verdict,
                )
            payload = json.loads(run(root, "review", "--decision", "explore").stdout)
            self.assertEqual(payload["consecutive_non_improving"], 3)
            self.assertTrue(payload["plateau_signal"])

    def test_branch_assessment_links_external_proposal_to_mainline_and_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(
                root,
                "init",
                "--title",
                "Deploy app",
                "--objective",
                "App works in target environment",
                "--observe",
                "Core user flow works",
            )
            run(
                root,
                "branch",
                "open",
                "--kind",
                "exploration",
                "--reason",
                "Read a new cache architecture",
                "--exit-criteria",
                "Decide whether a bounded experiment is justified",
                "--return-to",
                "deploy app",
                "--trigger",
                "user shared paper",
                "--relation",
                "may reduce deployment latency",
                "--target-criteria",
                "C1",
            )
            result = run(
                root,
                "branch",
                "assess",
                "--id",
                "B1",
                "--mainline-relation",
                "May reduce deployment latency",
                "--target-criteria",
                "C1",
                "--ledger-refs",
                "none: no comparable prior attempt",
                "--cost-risk",
                "low",
                "--recommendation",
                "test",
            )
            payload = json.loads(result.stdout)
            self.assertEqual(payload["branch"]["assessment"]["recommendation"], "test")
            self.assertEqual(payload["branch"]["target_criteria"], ["C1"])
            ledger = (root / ".mainline" / "ledger.jsonl").read_text(encoding="utf-8")
            self.assertIn('"kind": "branch_assessment"', ledger)

    def test_branch_close_integrates_result_and_sets_next_mainline_action(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(
                root,
                "init",
                "--title",
                "Deploy app",
                "--objective",
                "App works",
                "--observe",
                "Core flow works",
            )
            run(
                root,
                "branch",
                "open",
                "--kind",
                "exploration",
                "--reason",
                "Evaluate framework",
                "--exit-criteria",
                "Record fit",
                "--return-to",
                "deploy app",
            )
            run(
                root,
                "branch",
                "assess",
                "--id",
                "B1",
                "--mainline-relation",
                "May reduce latency",
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
                "decision_candidate",
                "--result",
                "Cache layer is compatible",
                "--helped",
                "May reduce latency",
                "--not-adopted",
                "Do not migrate the whole framework",
                "--remaining",
                "No production-like benchmark yet",
                "--next",
                "Run one bounded cache benchmark",
                "--decision",
                "test",
            )
            self.assertIn("Back to: deploy app", result.stdout)
            state = json.loads(
                (root / ".mainline" / "state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                state["goals"]["G1"]["next_action"], "Run one bounded cache benchmark"
            )
            branch = state["branches"]["B1"]
            self.assertEqual(branch["integrated_result"], "May reduce latency")
            self.assertEqual(branch["decision"], "test")

    def test_exploration_branch_cannot_close_without_mainline_assessment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(
                root,
                "init",
                "--title",
                "Deploy app",
                "--objective",
                "App works",
                "--observe",
                "Core flow works",
            )
            run(
                root,
                "branch",
                "open",
                "--kind",
                "exploration",
                "--reason",
                "Read a new architecture",
                "--exit-criteria",
                "Decide fit",
                "--return-to",
                "Deploy app",
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
                "The paper identifies one possible optimization",
                "--remaining",
                "benchmark",
                "--next",
                "return to implementation",
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("assessment", result.stderr)

    def test_intake_is_advisory_and_does_not_open_or_switch_branch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(
                root,
                "init",
                "--title",
                "Deploy app",
                "--objective",
                "Deploy the software and make the core flow usable",
                "--observe",
                "A clean environment completes the core flow",
            )
            result = run(
                root,
                "intake",
                "--message",
                "这篇论文提出了新的缓存架构，可能降低部署延迟",
            )
            payload = json.loads(result.stdout)
            self.assertEqual(payload["relation"], "candidate_branch")
            self.assertTrue(payload["matched_mainline_terms"])
            self.assertEqual(payload["recommended_action"], "evaluate_before_adopting")
            state = json.loads(
                (root / ".mainline" / "state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(state["branches"], {})

    def test_intake_handles_real_chinese_external_proposal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(
                root,
                "init",
                "--title",
                "软件部署",
                "--objective",
                "完成软件部署并让核心流程可用",
                "--observe",
                "用户在目标环境完成核心流程",
            )
            result = run(
                root,
                "intake",
                "--message",
                "我看到一篇新的缓存架构论文，可能降低部署延迟",
            )
            payload = json.loads(result.stdout)
            self.assertEqual(payload["relation"], "candidate_branch")
            self.assertIn("external_proposal", payload["signals"])
            self.assertIn("部署", payload["matched_mainline_terms"])

    def test_recorded_intake_is_a_signal_not_a_branch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(
                root,
                "init",
                "--title",
                "软件部署",
                "--objective",
                "完成软件部署",
                "--observe",
                "用户完成核心流程",
            )
            run(root, "intake", "--message", "这篇论文提出新的缓存架构", "--record")
            state = json.loads(
                (root / ".mainline" / "state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(state["branches"], {})
            self.assertTrue(
                any(event["operation"] == "record_intake" for event in state["events"])
            )
            ledger = (root / ".mainline" / "ledger.jsonl").read_text(encoding="utf-8")
            self.assertIn('"kind": "intake_signal"', ledger)

    def test_prompt_hook_injects_only_a_candidate_signal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(
                root,
                "init",
                "--title",
                "软件部署",
                "--objective",
                "完成软件部署",
                "--observe",
                "用户完成核心流程",
            )
            adapter = Path(__file__).parents[1] / "adapters" / "prompt_hook.py"
            result = subprocess.run(
                [sys.executable, str(adapter)],
                input=json.dumps(
                    {"prompt": "我看到一篇新的缓存架构论文，可能降低部署延迟"},
                    ensure_ascii=False,
                ),
                cwd=root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self.assertEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            context = payload["hookSpecificOutput"]["additionalContext"]
            self.assertIn("candidate_branch", context)
            self.assertIn("This is advisory only", context)
            self.assertIn("will not automatically open a branch", context)
            state = json.loads(
                (root / ".mainline" / "state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(state["branches"], {})

    def test_end_to_end_paper_branch_returns_to_software_mainline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(
                root,
                "init",
                "--title",
                "Deploy the software",
                "--objective",
                "Make the software usable in the target environment",
                "--observe",
                "A real user completes the core workflow in a clean target environment",
            )
            run(
                root,
                "branch",
                "open",
                "--kind",
                "exploration",
                "--reason",
                "Read a new architecture paper",
                "--exit-criteria",
                "Decide whether a bounded experiment helps deployment",
                "--return-to",
                "Deploy the software",
                "--trigger",
                "user shared paper",
                "--relation",
                "may reduce deployment risk",
                "--target-criteria",
                "C1",
            )
            assessment = run(
                root,
                "branch",
                "assess",
                "--id",
                "B1",
                "--mainline-relation",
                "May reduce deployment risk for the target workflow",
                "--target-criteria",
                "C1",
                "--ledger-refs",
                "none: no comparable local attempt",
                "--cost-risk",
                "one day and reversible",
                "--recommendation",
                "test",
            )
            self.assertIn('"recommendation": "test"', assessment.stdout)
            result = run(
                root,
                "branch",
                "close",
                "--id",
                "B1",
                "--result-type",
                "decision_candidate",
                "--result",
                "The paper suggests a bounded cache experiment, not a framework migration",
                "--helped",
                "It identifies one low-risk deployment experiment",
                "--not-adopted",
                "Do not replace the current architecture",
                "--remaining",
                "The experiment still needs to run",
                "--next",
                "Return to the deployment implementation and run one bounded experiment",
                "--decision",
                "test",
            )
            self.assertIn("Back to: Deploy the software", result.stdout)
            self.assertIn(
                "Next: Return to the deployment implementation", result.stdout
            )
            state = json.loads(
                (root / ".mainline" / "state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(state["active_goal_id"], "G1")
            self.assertEqual(
                state["goals"]["G1"]["next_action"],
                "Return to the deployment implementation and run one bounded experiment",
            )
            audit = run(root, "audit", check=False)
            self.assertEqual(audit.returncode, 1)
            payload = json.loads(audit.stdout)
            self.assertEqual(payload["status"], "incomplete")
            self.assertEqual(payload["not_proved"][0]["id"], "C1")


if __name__ == "__main__":
    unittest.main()
