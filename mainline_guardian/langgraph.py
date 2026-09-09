"""Optional LangGraph integration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .api import MainlineGuardian


class MainlineGuardianNode:
    """A LangGraph-compatible callable that emits an advisory signal."""

    def __init__(self, root: str | Path = ".") -> None:
        self.guardian = MainlineGuardian(root)

    def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        message = (
            state.get("latest_message")
            or state.get("message")
            or state.get("prompt")
            or ""
        )
        if not isinstance(message, str) or not message.strip():
            return {
                "mainline_signal": None,
                "execution_authorized": False,
                "active_goal_id": self.guardian.state().get("active_goal_id"),
            }
        signal = self.guardian.intake(message, record=True)
        return {
            "mainline_signal": signal,
            "execution_authorized": False,
            "active_goal_id": self.guardian.state().get("active_goal_id"),
        }


def build_mainline_guardian(root: str | Path = ".") -> Any:
    """Build a one-node LangGraph subgraph when the optional package is installed."""
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise RuntimeError(
            "LangGraph integration is optional; install it with "
            "pip install -e '.[langgraph]'"
        ) from exc
    graph = StateGraph(dict)
    graph.add_node("mainline_check", MainlineGuardianNode(root))
    graph.add_edge(START, "mainline_check")
    graph.add_edge("mainline_check", END)
    return graph.compile()

