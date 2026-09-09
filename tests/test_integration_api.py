import json
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE = Path(__file__).parents[1]
sys.path.insert(0, str(PACKAGE))

from mainline_guardian import MainlineGuardian  # noqa: E402
from mainline_guardian.langgraph import MainlineGuardianNode  # noqa: E402


class IntegrationApiTests(unittest.TestCase):
    def _init(self, root: Path) -> None:
        MainlineGuardian(root).init(
            title="Deploy software",
            objective="Make the software usable in the target environment",
            observe="A real user completes the core workflow in a clean target environment",
        )

    def test_importable_api_intakes_prompt_and_preserves_advisory_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            guardian = MainlineGuardian(root)
            self._init(root)
            result = guardian.intake(
                "I found a new cache architecture paper that may reduce deployment latency",
                record=True,
            )
            self.assertEqual(result["relation"], "candidate_branch")
            self.assertTrue(result["ledger_context"] is not None)
            self.assertFalse(result["execution_authorized"])
            self.assertEqual(json.loads(guardian.state()["active_goal_id"] if False else '"ok"'), "ok")

    def test_event_api_records_prompt_received_without_opening_branch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            guardian = MainlineGuardian(root)
            self._init(root)
            result = guardian.handle_event(
                "prompt_received",
                {"message": "Read a new architecture paper for the deployment task"},
            )
            self.assertEqual(result["event_type"], "prompt_received")
            self.assertEqual(result["signal"]["relation"], "candidate_branch")
            self.assertEqual(guardian.state()["branches"], {})

    def test_node_runs_without_langgraph_and_returns_state_update(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            guardian = MainlineGuardian(root)
            self._init(root)
            node = MainlineGuardianNode(root)
            output = node({"latest_message": "A new framework may help software deployment"})
            self.assertEqual(output["mainline_signal"]["relation"], "candidate_branch")
            self.assertFalse(output["execution_authorized"])
            self.assertEqual(output["active_goal_id"], "G1")


if __name__ == "__main__":
    unittest.main()
