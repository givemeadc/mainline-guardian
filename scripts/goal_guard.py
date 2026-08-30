#!/usr/bin/env python3
"""Dependency-free state controller for the Mainline Guardian skill."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATE_DIR = ".mainline"


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def die(message: str, code: int = 2) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(code)


def paths(root: Path) -> tuple[Path, Path, Path, Path]:
    directory = root / STATE_DIR
    return directory / "state.json", directory / "checkpoint.md", directory / "ledger.jsonl", directory / "audit.json"


def empty_state() -> dict[str, Any]:
    return {"schema_version": 2, "active_goal_id": None, "goals": {}, "branches": {}, "events": []}


def load(root: Path, allow_missing: bool = False) -> dict[str, Any]:
    state_path, _, _, _ = paths(root)
    if not state_path.exists():
        if allow_missing:
            return empty_state()
        die(f"no state found at {state_path}; run init first")
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        die(f"cannot read state: {exc}")
    if state.get("schema_version") != 2 or not isinstance(state.get("goals"), dict):
        die("unsupported or invalid state schema; v1 state is not auto-migrated")
    return state


def save(root: Path, state: dict[str, Any], operation: str, data: dict[str, Any] | None = None) -> None:
    state_path, _, _, _ = paths(root)
    state["events"].append({"at": now(), "operation": operation, "data": data or {}})
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_ledger(root: Path, kind: str, data: dict[str, Any]) -> None:
    _, _, ledger_path, _ = paths(root)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    record = {"at": now(), "kind": kind, **data}
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_ledger(root: Path) -> list[dict[str, Any]]:
    _, _, ledger_path, _ = paths(root)
    if not ledger_path.exists():
        return []
    records = []
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def active_goal(state: dict[str, Any]) -> dict[str, Any]:
    goal_id = state.get("active_goal_id")
    if not goal_id or goal_id not in state["goals"]:
        die("no active goal; run init or goal switch first")
    return state["goals"][goal_id]


def next_id(items: dict[str, Any], prefix: str) -> str:
    numeric = [int(re.sub(r"\D", "", key) or 0) for key in items]
    return f"{prefix}{max(numeric, default=0) + 1}"


def artifact_key(root: Path, value: str) -> str:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = root / path
    return str(path.resolve()).replace("\\", "/").lower()


def validate_observed(value: str) -> None:
    compact = value.strip().lower()
    if compact in {"done", "complete", "completed", "ok", "pass", "finished", "success"} or len(compact) < 8:
        die("--observed must describe a concrete observation, not a completion label")
    if len(compact) < 8 or compact in {"done", "complete", "completed", "ok", "pass", "完成", "已完成", "可以"}:
        die("--observed must describe a concrete observation, not a completion label")


def validate_attestation(value: str) -> None:
    if len(value.strip()) < 8 or not any(mark in value for mark in ('"', "'")):
        die("--note must quote the user's attestation verbatim")
    if len(value.strip()) < 8 or not any(mark in value for mark in ('"', "“", "”", "'")):
        die("--note must quote the user's attestation verbatim")


def add_goal(state: dict[str, Any], title: str, objective: str) -> str:
    goal_id = next_id(state["goals"], "G")
    stamp = now()
    state["goals"][goal_id] = {
        "id": goal_id,
        "title": title,
        "objective": objective,
        "deliverables": {},
        "criteria": {},
        "constraints": [],
        "non_goals": [],
        "contract_revision": 1,
        "noise_band": None,
        "plateau_threshold": 3,
        "status": "active",
        "created_at": stamp,
        "updated_at": stamp,
    }
    return goal_id


def add_criterion(goal: dict[str, Any], text: str, observe: str, closer: str, kind: str = "result", budget: str | None = None) -> str:
    criterion_id = next_id(goal["criteria"], "C")
    goal["criteria"][criterion_id] = {
        "id": criterion_id,
        "text": text,
        "observe": observe,
        "closer": closer,
        "kind": kind,
        "status": "open",
        "observations": [],
        "contract_revision": goal["contract_revision"],
    }
    if kind == "discovery":
        goal["criteria"][criterion_id]["budget"] = budget
    return criterion_id


def criterion_statuses(goal: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    groups = {"proved": [], "awaiting_attestation": [], "not_proved": []}
    for item in goal["criteria"].values():
        if item["status"] == "verified":
            groups["proved"].append(item)
        elif item["status"] == "awaiting-attestation":
            groups["awaiting_attestation"].append(item)
        else:
            groups["not_proved"].append(item)
    return groups


def write_checkpoint(root: Path, state: dict[str, Any], return_sentence: str = "") -> Path:
    _, checkpoint_path, _, _ = paths(root)
    lines = ["# Mainline Guardian Brief", "", f"Generated: {now()}", ""]
    if state.get("active_goal_id"):
        goal = active_goal(state)
        lines.extend([f"## Mainline: {goal['title']}", "", goal["objective"], "", "### Checkout"])
        for item in goal["criteria"].values():
            lines.append(f"- {item['id']} [{item['status']}]: {item['text']}")
        active = [b for b in state["branches"].values() if b["goal_id"] == goal["id"] and b["status"] == "active"]
        lines.extend(["", "### Active Branches"])
        lines.extend([f"- {b['id']}: {b['reason']} -> {b['return_to']}" for b in active] or ["- None"])
    if return_sentence:
        lines.extend(["", "### Return", "", return_sentence])
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return checkpoint_path


def audit_state(state: dict[str, Any]) -> dict[str, Any]:
    goal = active_goal(state)
    groups = criterion_statuses(goal)
    active_branches = [b["id"] for b in state["branches"].values() if b["goal_id"] == goal["id"] and b["status"] == "active"]
    issues = []
    if not goal["criteria"]:
        issues.append("no criteria declared")
    if groups["awaiting_attestation"]:
        issues.append("user attestation required")
    if groups["not_proved"]:
        issues.append("criteria remain unproved")
    if active_branches:
        issues.append("active branches remain")
    other_goals = []
    for other in state["goals"].values():
        if other["id"] == goal["id"]:
            continue
        other_groups = criterion_statuses(other)
        other_goals.append({"goal_id": other["id"], "title": other["title"], "status": other["status"], "unproved_count": len(other_groups["awaiting_attestation"]) + len(other_groups["not_proved"])})
    return {
        "goal_id": goal["id"],
        "status": "complete" if not issues else "incomplete",
        "proved": [{"id": c["id"], "text": c["text"], "observations": c["observations"]} for c in groups["proved"]],
        "awaiting_attestation": [{"id": c["id"], "text": c["text"], "observations": c["observations"]} for c in groups["awaiting_attestation"]],
        "not_proved": [{"id": c["id"], "text": c["text"], "status": c["status"]} for c in groups["not_proved"]],
        "active_branches": active_branches,
        "other_goals": other_goals,
        "blocking_findings": issues,
        "checked_at": now(),
    }


def command(args: argparse.Namespace, root: Path) -> None:
    if args.command == "init":
        state = load(root, allow_missing=True)
        if state["goals"] and not args.force:
            die("state already has goals; use --force only to start a new state")
        state = empty_state()
        goal_id = add_goal(state, args.title, args.objective)
        state["active_goal_id"] = goal_id
        state["goals"][goal_id]["noise_band"] = args.noise_band
        state["goals"][goal_id]["plateau_threshold"] = args.plateau_threshold
        criterion_id = add_criterion(state["goals"][goal_id], args.objective, args.observe, "user")
        save(root, state, "init_goal", {"goal_id": goal_id, "top_level_criterion": criterion_id})
        write_checkpoint(root, state)
        print(json.dumps({"goal_id": goal_id, "criterion_id": criterion_id, "state_dir": str(root / STATE_DIR)}, ensure_ascii=False))
        return

    state = load(root)
    goal = active_goal(state)
    if args.command == "status":
        print(json.dumps({"active_goal": goal, "active_branches": [b for b in state["branches"].values() if b["status"] == "active"]}, ensure_ascii=False, indent=2))
    elif args.command == "goal" and args.goal_action == "add":
        goal_id = add_goal(state, args.title, args.objective)
        save(root, state, "add_goal", {"goal_id": goal_id})
        print(goal_id)
    elif args.command == "goal" and args.goal_action == "switch":
        if args.goal_id not in state["goals"]:
            die(f"unknown goal {args.goal_id}")
        old = state["active_goal_id"]
        state["active_goal_id"] = args.goal_id
        save(root, state, "switch_goal", {"from": old, "to": args.goal_id, "reason": args.reason})
        write_checkpoint(root, state, f"Closed: switched goals. Back to: {args.goal_id}. Remaining: review its open criteria. Next: continue its mainline.")
        print(json.dumps({"from": old, "to": args.goal_id}, ensure_ascii=False))
    elif args.command == "criterion":
        if args.criterion_action == "add":
            if args.kind == "discovery" and not args.budget:
                die("discovery criterion requires --budget")
            criterion_id = add_criterion(goal, args.text, args.observe, args.closer, args.kind, args.budget)
            save(root, state, "add_criterion", {"criterion_id": criterion_id})
            print(criterion_id)
        elif args.criterion_action == "close":
            item = goal["criteria"].get(args.id)
            if not item:
                die(f"unknown criterion {args.id}")
            validate_observed(args.observed)
            if item["kind"] == "discovery" and not args.discovery_outcome:
                die("discovery criterion requires --discovery-outcome")
            observation = {"at": now(), "observed": args.observed, "object": artifact_key(root, args.object), "contract_revision": item["contract_revision"]}
            item["observations"].append(observation)
            if item["kind"] == "discovery":
                append_ledger(root, "discovery_exit", {"criterion_id": item["id"], "outcome": args.discovery_outcome, "observed": args.observed})
            item["status"] = "verified" if item["closer"] == "agent" else "awaiting-attestation"
            save(root, state, "close_criterion", {"criterion_id": item["id"], "status": item["status"]})
            print(json.dumps(item, ensure_ascii=False))
        elif args.criterion_action == "attest":
            item = goal["criteria"].get(args.id)
            if not item:
                die(f"unknown criterion {args.id}")
            if item["closer"] != "user" or item["status"] != "awaiting-attestation":
                die("criterion is not awaiting user attestation")
            validate_attestation(args.note)
            item["status"] = "verified"
            item["attestation"] = {"at": now(), "note": args.note}
            save(root, state, "attest_criterion", {"criterion_id": item["id"]})
            print(json.dumps(item, ensure_ascii=False))
        elif args.criterion_action == "stale":
            item = goal["criteria"].get(args.id)
            if not item:
                die(f"unknown criterion {args.id}")
            item["status"] = "stale"
            item["stale_reason"] = args.reason
            save(root, state, "stale_criterion", {"criterion_id": item["id"], "reason": args.reason})
            print(json.dumps(item, ensure_ascii=False))
    elif args.command == "branch":
        if args.branch_action == "open":
            branch_id = next_id(state["branches"], "B")
            state["branches"][branch_id] = {"id": branch_id, "goal_id": goal["id"], "kind": args.kind, "reason": args.reason, "exit_criteria": args.exit_criteria, "return_to": args.return_to, "status": "active", "created_at": now()}
            save(root, state, "open_branch", {"branch_id": branch_id})
            print(branch_id)
        else:
            branch = state["branches"].get(args.id)
            if not branch:
                die(f"unknown branch {args.id}")
            branch["status"] = "closed"
            branch["result_type"] = args.result_type
            branch["result"] = args.result
            sentence = f"Closed: {args.result}. Back to: {branch['return_to']}. Remaining: {args.remaining}. Next: {args.next}."
            branch["return_sentence"] = sentence
            append_ledger(root, "branch_return", {"branch_id": branch["id"], "result_type": args.result_type, "result": args.result, "next": args.next, "return_sentence": sentence})
            save(root, state, "close_branch", {"branch_id": branch["id"], "return_sentence": sentence})
            write_checkpoint(root, state, sentence)
            print(sentence)
    elif args.command == "decision":
        append_ledger(root, "decision", {"proposal": args.proposal, "mainline_relation": args.mainline_relation, "ledger_refs": args.ledger_refs, "cost_risk": args.cost_risk, "decision": args.decision})
        save(root, state, "record_decision", {"decision": args.decision})
        print("recorded")
    elif args.command == "contract":
        if args.affects and args.all:
            die("contract amend accepts either --affects or --all, not both")
        affects = [item.strip() for item in args.affects.split(",") if item.strip()] if args.affects else []
        if not affects and not args.all:
            die("contract amend requires --affects C1,C2 or --all")
        targets = goal["criteria"].values() if args.all else [goal["criteria"].get(item_id) for item_id in affects]
        if any(item is None for item in targets):
            die("contract amend references an unknown criterion")
        goal["contract_revision"] += 1
        for item in targets:
            item["contract_revision"] = goal["contract_revision"]
            if item["status"] in {"verified", "awaiting-attestation", "stale"}:
                item["status"] = "superseded"
                item["superseded_reason"] = args.reason
        target_ids = list(goal["criteria"]) if args.all else affects
        append_ledger(root, "contract_change", {"revision": goal["contract_revision"], "reason": args.reason, "affected_criteria": target_ids})
        save(root, state, "amend_contract", {"revision": goal["contract_revision"], "reason": args.reason, "affected_criteria": target_ids})
        write_checkpoint(root, state, f"Closed: contract amended. Back to: {goal['objective']}. Remaining: re-observe superseded criteria. Next: realign implementation.")
        print("recorded")
    elif args.command == "action":
        if not args.failure_action.strip():
            die("action declaration requires --failure-action; state what different action follows failure")
        record = {"description": args.description, "target": args.target, "criterion": args.criterion or "unspecified", "contract_change": args.contract_change, "failure_action": args.failure_action}
        append_ledger(root, "action_declaration", record)
        save(root, state, "action_declaration", record)
        print("recorded")
    elif args.command == "version":
        record = {"goal_id": goal["id"], "route": args.route, "change": args.change, "hypothesis": args.hypothesis, "metric": args.metric, "delta": args.delta, "verdict": args.verdict, "baseline": args.baseline or "unspecified", "artifact": artifact_key(root, args.artifact) if args.artifact else None}
        append_ledger(root, "version", record)
        if args.artifact:
            changed = artifact_key(root, args.artifact)
            for item in goal["criteria"].values():
                if item.get("status") in {"verified", "awaiting-attestation"} and any(artifact_key(root, obs.get("object", "")) == changed for obs in item.get("observations", [])):
                    item["status"] = "stale"
                    item["stale_reason"] = f"artifact changed: {args.artifact}"
        save(root, state, "version_log", record)
        print("recorded")
    elif args.command == "review":
        records = [r for r in read_ledger(root) if r.get("kind") == "version" and r.get("goal_id") == goal["id"]]
        threshold = args.threshold if args.threshold is not None else goal.get("plateau_threshold", 3)
        noise_band = args.noise_band if args.noise_band is not None else goal.get("noise_band")
        tail = []
        latest_route = records[-1].get("route") if records else None
        for record in reversed(records):
            if record.get("route") != latest_route:
                break
            delta = record.get("delta")
            within_noise = noise_band is not None and delta is not None and abs(float(delta)) <= noise_band
            if record.get("verdict") in {"no_gain", "regression", "inconclusive"} or within_noise:
                tail.append(record)
            else:
                break
        plateau = len(tail) >= threshold
        no_gain = tail
        if not args.decision:
            die("review requires --decision: continue, explore, ask_user, or infeasible")
        append_ledger(root, "route_decision", {"goal_id": goal["id"], "decision": args.decision, "reason": args.reason or "review decision"})
        stale = [item["id"] for item in goal["criteria"].values() if item["status"] == "stale"]
        result = {"versions_reviewed": len(records), "route": latest_route, "consecutive_non_improving": len(no_gain), "threshold": threshold, "noise_band": noise_band, "plateau_signal": plateau, "stale_criteria": stale, "route_decision": args.decision}
        save(root, state, "review", result)
        print(json.dumps(result, ensure_ascii=False))
    elif args.command == "brief":
        ledger = [record for record in read_ledger(root) if record.get("goal_id") in {None, goal["id"]}]
        versions = [record for record in ledger if record.get("kind") == "version"]
        branches = [record for record in ledger if record.get("kind") == "branch_return"]
        groups = criterion_statuses(goal)
        pending = groups["awaiting_attestation"] + groups["not_proved"]
        latest = versions[-1] if versions else None
        negative = next((record for record in reversed(versions) if record.get("verdict") in {"no_gain", "regression", "inconclusive"}), None)
        next_step = branches[-1].get("next") if branches else (f"obtain {pending[0]['observe']}" if pending else "wait for the next user request")
        lines = [
            f"Mainline: {goal['objective']}",
            f"Pending: {', '.join(item['id'] for item in pending) if pending else 'none'}",
            f"Hypothesis: {latest['hypothesis'] if latest else 'none logged'}",
            f"Negative: {negative['change'] if negative else 'none logged'}",
            f"Next: {next_step}",
        ]
        print("\n".join(lines))
    elif args.command == "audit":
        result = audit_state(state)
        audit_path = paths(root)[3]
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        audit_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result["status"] != "complete":
            raise SystemExit(1)
    elif args.command == "checkpoint":
        print(write_checkpoint(root, state, args.note))
    else:
        die("unknown command")


def parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Maintain a task mainline across branches, versions, and checkout.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init"); init.add_argument("--title", required=True); init.add_argument("--objective", required=True); init.add_argument("--observe", required=True); init.add_argument("--noise-band", type=float); init.add_argument("--plateau-threshold", type=int, default=3); init.add_argument("--force", action="store_true")
    sub.add_parser("status"); sub.add_parser("brief"); sub.add_parser("audit")
    goal = sub.add_parser("goal"); goal_sub = goal.add_subparsers(dest="goal_action", required=True)
    add_goal_parser = goal_sub.add_parser("add"); add_goal_parser.add_argument("--title", required=True); add_goal_parser.add_argument("--objective", required=True)
    switch = goal_sub.add_parser("switch"); switch.add_argument("--goal-id", required=True); switch.add_argument("--reason", required=True)
    criterion = sub.add_parser("criterion"); criterion_sub = criterion.add_subparsers(dest="criterion_action", required=True)
    add = criterion_sub.add_parser("add"); add.add_argument("--text", required=True); add.add_argument("--observe", required=True); add.add_argument("--closer", choices=["agent", "user"], required=True); add.add_argument("--kind", choices=["result", "discovery"], default="result"); add.add_argument("--budget", help="Budget for a discovery criterion, e.g. 3 experiments / 4 hours")
    close = criterion_sub.add_parser("close"); close.add_argument("--id", required=True); close.add_argument("--observed", required=True); close.add_argument("--object", required=True); close.add_argument("--discovery-outcome", choices=["result_criterion", "new_discovery", "ask_user", "infeasible"])
    attest = criterion_sub.add_parser("attest"); attest.add_argument("--id", required=True); attest.add_argument("--note", required=True)
    stale = criterion_sub.add_parser("stale"); stale.add_argument("--id", required=True); stale.add_argument("--reason", required=True)
    branch = sub.add_parser("branch"); branch_sub = branch.add_subparsers(dest="branch_action", required=True)
    open_branch = branch_sub.add_parser("open"); open_branch.add_argument("--kind", choices=["required", "exploration", "unrelated"], required=True); open_branch.add_argument("--reason", required=True); open_branch.add_argument("--exit-criteria", required=True); open_branch.add_argument("--return-to", required=True)
    close_branch = branch_sub.add_parser("close"); close_branch.add_argument("--id", required=True); close_branch.add_argument("--result-type", choices=["evidence", "decision_candidate", "implementation", "blocked", "contract_change"], required=True); close_branch.add_argument("--result", required=True); close_branch.add_argument("--remaining", required=True); close_branch.add_argument("--next", required=True)
    decision = sub.add_parser("decision"); decision_sub = decision.add_subparsers(dest="decision_action", required=True); record = decision_sub.add_parser("record"); record.add_argument("--proposal", required=True); record.add_argument("--mainline-relation", required=True); record.add_argument("--ledger-refs", default="none"); record.add_argument("--cost-risk", required=True); record.add_argument("--decision", choices=["adopt", "test", "reject", "defer"], required=True)
    contract = sub.add_parser("contract"); contract_sub = contract.add_subparsers(dest="contract_action", required=True); amend = contract_sub.add_parser("amend"); amend.add_argument("--reason", required=True); amend.add_argument("--affects"); amend.add_argument("--all", action="store_true")
    action = sub.add_parser("action"); action_sub = action.add_subparsers(dest="action_action", required=True); declare = action_sub.add_parser("declare"); declare.add_argument("--description", required=True); declare.add_argument("--target", required=True); declare.add_argument("--criterion"); declare.add_argument("--contract-change", choices=["yes", "no"], default="no"); declare.add_argument("--failure-action", required=True)
    version = sub.add_parser("version"); version_sub = version.add_subparsers(dest="version_action", required=True); log = version_sub.add_parser("log"); log.add_argument("--route", default="default"); log.add_argument("--change", required=True); log.add_argument("--hypothesis", required=True); log.add_argument("--metric", required=True); log.add_argument("--delta", type=float); log.add_argument("--verdict", choices=["improved", "no_gain", "regression", "inconclusive"], required=True); log.add_argument("--baseline"); log.add_argument("--artifact")
    review = sub.add_parser("review"); review.add_argument("--threshold", type=int); review.add_argument("--noise-band", type=float); review.add_argument("--decision", choices=["continue", "explore", "ask_user", "infeasible"], required=True); review.add_argument("--reason")
    checkpoint = sub.add_parser("checkpoint"); checkpoint.add_argument("--note", default="")
    return parser


if __name__ == "__main__":
    parsed = parser().parse_args()
    command(parsed, parsed.root.resolve())
