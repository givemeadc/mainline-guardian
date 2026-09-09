#!/usr/bin/env python3
"""Small, dependency-free controller for keeping an AI task on its mainline."""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCHEMA = 2
STATE_DIR = ".mainline"
BRANCH_RESULTS = {
    "evidence",
    "decision_candidate",
    "implementation",
    "blocked",
    "contract_change",
}
DECISIONS = {"adopt", "test", "defer", "reject", "ask_user"}
ROUTE_DECISIONS = {"continue", "explore", "ask_user", "infeasible"}
COMPLETION_LABELS = {
    "done",
    "complete",
    "completed",
    "ok",
    "pass",
    "passed",
    "finished",
    "success",
    "完成",
    "已完成",
    "可以",
    "通过",
    "成功",
}
GENERIC_FAILURES = {
    "increase confidence",
    "be more confident",
    "record the result",
    "check again",
    "see what happens",
    "nothing",
    "none",
    "增加信心",
    "记录结果",
    "再检查",
    "继续观察",
    "无",
}


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def die(message: str, code: int = 2) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(code)


def paths(root: Path) -> tuple[Path, Path, Path, Path]:
    d = root / STATE_DIR
    return d / "state.json", d / "checkpoint.md", d / "ledger.jsonl", d / "audit.json"


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as f:
        f.write(text)
        tmp = Path(f.name)
    tmp.replace(path)


def empty_state() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "active_goal_id": None,
        "goals": {},
        "branches": {},
        "events": [],
    }


def load(root: Path, allow_missing: bool = False) -> dict[str, Any]:
    path = paths(root)[0]
    if not path.exists():
        if allow_missing:
            return empty_state()
        die(f"no state found at {path}; run init first")
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        die(f"cannot read state: {exc}")
    if state.get("schema_version") != SCHEMA or not isinstance(
        state.get("goals"), dict
    ):
        die(f"unsupported or invalid state schema; expected v{SCHEMA}")
    state.setdefault("branches", {})
    state.setdefault("events", [])
    return state


def save(
    root: Path,
    state: dict[str, Any],
    operation: str,
    data: dict[str, Any] | None = None,
) -> None:
    state.setdefault("events", []).append(
        {"at": now(), "operation": operation, "data": data or {}}
    )
    active = state.get("active_goal_id")
    if active in state.get("goals", {}):
        state["goals"][active]["updated_at"] = now()
    atomic_write(paths(root)[0], json.dumps(state, ensure_ascii=False, indent=2) + "\n")


def append_ledger(root: Path, kind: str, data: dict[str, Any]) -> None:
    path = paths(root)[2]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(
            json.dumps({"at": now(), "kind": kind, **data}, ensure_ascii=False) + "\n"
        )


def read_ledger(root: Path) -> list[dict[str, Any]]:
    path = paths(root)[2]
    if not path.exists():
        return []
    result = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            result.append(json.loads(line))
        except json.JSONDecodeError as exc:
            die(f"invalid ledger JSON on line {number}: {exc}")
    return result


def text(value: str | None, flag: str, minimum: int = 1) -> str:
    value = (value or "").strip()
    if len(value) < minimum:
        die(f"{flag} must contain at least {minimum} characters")
    return value


def active_goal(state: dict[str, Any]) -> dict[str, Any]:
    goal_id = state.get("active_goal_id")
    if not goal_id or goal_id not in state["goals"]:
        die("no active goal; run init or goal switch first")
    return state["goals"][goal_id]


def next_id(items: dict[str, Any], prefix: str) -> str:
    nums = [int(re.sub(r"\D", "", key) or 0) for key in items]
    return f"{prefix}{max(nums, default=0) + 1}"


def artifact_key(root: Path, value: str) -> str:
    path = Path(text(value, "--object")).expanduser()
    if not path.is_absolute():
        path = root / path
    return str(path.resolve(strict=False)).replace("\\", "/").casefold()


def validate_observed(value: str) -> None:
    value = text(value, "--observed", 8)
    if value.casefold() in COMPLETION_LABELS:
        die("--observed must describe a concrete observation, not a completion label")


def validate_attestation(value: str) -> None:
    value = text(value, "--note", 8)
    if not any(
        mark in value for mark in ('"', "'", "\u201c", "\u201d", "\u2018", "\u2019")
    ):
        die("--note must quote the user's attestation verbatim")


def validate_failure(value: str) -> None:
    value = text(value, "--failure-action", 8)
    if value.casefold() in GENERIC_FAILURES:
        die(
            "--failure-action must name a different next action, not a confidence or logging statement"
        )


def ids(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def extract_terms(value: str) -> list[str]:
    terms: list[str] = []
    for match in re.findall(r"[A-Za-z0-9_]{2,}|[\u4e00-\u9fff]{2,}", value.casefold()):
        terms.append(match)
        if re.fullmatch(r"[\u4e00-\u9fff]+", match) and len(match) > 2:
            terms.extend(match[i : i + 2] for i in range(len(match) - 1))
    return list(dict.fromkeys(terms))


def mainline_terms(goal: dict[str, Any]) -> list[str]:
    values = [goal.get("title", ""), goal.get("objective", "")]
    for criterion in goal.get("criteria", {}).values():
        values.extend([criterion.get("text", ""), criterion.get("observe", "")])
    return extract_terms(" ".join(values))


def intake_result(
    goal: dict[str, Any], message: str, ledger: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    message = text(message, "--message")
    lowered = message.casefold()
    terms = mainline_terms(goal)
    matched = [term for term in terms if term in lowered]
    synonyms = {
        "deploy": ("部署", "上线", "落地"),
        "deployment": ("部署", "上线", "落地"),
        "software": ("软件", "系统"),
        "app": ("应用", "软件", "系统"),
        "architecture": ("架构",),
        "framework": ("框架",),
    }
    for term in terms:
        if term in synonyms and any(alias in lowered for alias in synonyms[term]):
            matched.append(term)
    matched = list(dict.fromkeys(matched))
    markers = (
        "论文",
        "架构",
        "框架",
        "方案",
        "新方向",
        "paper",
        "architecture",
        "framework",
        "proposal",
        "research",
    )
    signals = (
        ["external_proposal"] if any(marker in lowered for marker in markers) else []
    )
    if matched:
        signals.append("mainline_term_match")
    relation = "candidate_branch" if signals else "mainline_context"
    related_ledger_entries: list[dict[str, Any]] = []
    for entry in ledger or []:
        searchable = json.dumps(entry, ensure_ascii=False).casefold()
        if any(term.casefold() in searchable for term in matched):
            related_ledger_entries.append(
                {
                    "kind": entry.get("kind", "unknown"),
                    "at": entry.get("at"),
                    "summary": entry.get("result")
                    or entry.get("change")
                    or entry.get("proposal")
                    or entry.get("message")
                    or entry.get("verdict"),
                }
            )
    related_ledger_entries = related_ledger_entries[-8:]
    return {
        "goal_id": goal["id"],
        "relation": relation,
        "matched_mainline_terms": matched[:12],
        "signals": signals,
        "recommended_action": (
            "evaluate_before_adopting"
            if relation == "candidate_branch"
            else "continue_mainline_analysis"
        ),
        "confidence": "low",
        "related_ledger_entries": related_ledger_entries,
        "ledger_context": related_ledger_entries,
        "execution_authorized": False,
        "branch_opened": False,
        "warning": "Advisory only: this result does not open a branch, switch goals, or authorize execution.",
    }


def add_goal(state: dict[str, Any], title: str, objective: str) -> str:
    goal_id = next_id(state["goals"], "G")
    stamp = now()
    state["goals"][goal_id] = {
        "id": goal_id,
        "title": text(title, "--title"),
        "objective": text(objective, "--objective"),
        "deliverables": {},
        "criteria": {},
        "constraints": [],
        "non_goals": [],
        "contract_revision": 1,
        "noise_band": None,
        "plateau_threshold": 3,
        "status": "active",
        "next_action": "",
        "mainline_updates": [],
        "created_at": stamp,
        "updated_at": stamp,
    }
    return goal_id


def add_criterion(
    goal: dict[str, Any],
    claim: str,
    observe: str,
    closer: str,
    kind: str = "result",
    budget: str | None = None,
) -> str:
    if closer not in {"agent", "user"}:
        die("--closer must be agent or user")
    if kind == "discovery" and not budget:
        die("discovery criterion requires --budget")
    criterion_id = next_id(goal["criteria"], "C")
    goal["criteria"][criterion_id] = {
        "id": criterion_id,
        "text": text(claim, "--text"),
        "observe": text(observe, "--observe"),
        "closer": closer,
        "kind": kind,
        "status": "open",
        "observations": [],
        "contract_revision": goal["contract_revision"],
    }
    if kind == "discovery":
        goal["criteria"][criterion_id]["budget"] = budget
    return criterion_id


def criterion_groups(goal: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    groups = {"proved": [], "awaiting_attestation": [], "not_proved": []}
    for item in goal.get("criteria", {}).values():
        if item.get("status") == "verified":
            groups["proved"].append(item)
        elif item.get("status") == "awaiting-attestation":
            groups["awaiting_attestation"].append(item)
        else:
            groups["not_proved"].append(item)
    return groups


def checkpoint(root: Path, state: dict[str, Any], return_sentence: str = "") -> Path:
    lines = ["# Mainline Guardian Brief", "", f"Generated: {now()}", ""]
    if state.get("active_goal_id"):
        goal = active_goal(state)
        lines += [
            f"## Mainline: {goal['title']}",
            "",
            goal["objective"],
            "",
            "### Checkout",
            f"- Next mainline action: {goal.get('next_action') or 'continue the declared mainline'}",
        ]
        lines += [
            f"- {c['id']} [{c['status']}]: {c['text']}"
            for c in goal.get("criteria", {}).values()
        ]
        active = [
            b
            for b in state.get("branches", {}).values()
            if b.get("goal_id") == goal["id"] and b.get("status") == "active"
        ]
        lines += ["", "### Active Branches"] + (
            [f"- {b['id']}: {b['reason']} -> {b['return_to']}" for b in active]
            or ["- None"]
        )
    if return_sentence:
        lines += ["", "### Return", "", return_sentence]
    atomic_write(paths(root)[1], "\n".join(lines) + "\n")
    return paths(root)[1]


def audit_state(state: dict[str, Any]) -> dict[str, Any]:
    goal = active_goal(state)
    groups = criterion_groups(goal)
    active = [
        b["id"]
        for b in state.get("branches", {}).values()
        if b.get("goal_id") == goal["id"] and b.get("status") == "active"
    ]
    issues: list[str] = []
    if not goal.get("criteria"):
        issues.append("no criteria declared")
    if groups["awaiting_attestation"]:
        issues.append("user attestation required")
    if groups["not_proved"]:
        issues.append("criteria remain unproved")
    if active:
        issues.append("active branches remain")
    other = []
    for candidate in state.get("goals", {}).values():
        if candidate["id"] == goal["id"]:
            continue
        g = criterion_groups(candidate)
        other.append(
            {
                "goal_id": candidate["id"],
                "title": candidate["title"],
                "status": candidate.get("status", "active"),
                "unproved_count": len(g["awaiting_attestation"]) + len(g["not_proved"]),
            }
        )
    return {
        "goal_id": goal["id"],
        "status": "complete" if not issues else "incomplete",
        "proved": [
            {"id": c["id"], "text": c["text"], "observations": c["observations"]}
            for c in groups["proved"]
        ],
        "awaiting_attestation": [
            {"id": c["id"], "text": c["text"], "observations": c["observations"]}
            for c in groups["awaiting_attestation"]
        ],
        "not_proved": [
            {"id": c["id"], "text": c["text"], "status": c["status"]}
            for c in groups["not_proved"]
        ],
        "active_branches": active,
        "other_goals": other,
        "blocking_findings": issues,
        "checked_at": now(),
    }


def criterion(goal: dict[str, Any], criterion_id: str) -> dict[str, Any]:
    item = goal.get("criteria", {}).get(criterion_id)
    if item is None:
        die(f"unknown criterion {criterion_id}")
    return item


def stale_artifact(
    root: Path, goal: dict[str, Any], changed: str, reason: str
) -> list[str]:
    result = []
    for item in goal.get("criteria", {}).values():
        if item.get("status") not in {"verified", "awaiting-attestation"}:
            continue
        observed = {
            observation.get("object") for observation in item.get("observations", [])
        }
        if changed in observed:
            item["status"] = "stale"
            item["stale_reason"] = reason
            result.append(item["id"])
    return result


def command(args: argparse.Namespace, root: Path) -> None:
    if args.command == "init":
        previous = load(root, allow_missing=True)
        if previous["goals"] and not args.force:
            die("state already has goals; use --force only to start a new state")
        state = empty_state()
        goal_id = add_goal(state, args.title, args.objective)
        goal = state["goals"][goal_id]
        goal["noise_band"], goal["plateau_threshold"] = (
            args.noise_band,
            args.plateau_threshold,
        )
        criterion_id = add_criterion(goal, args.objective, args.observe, "user")
        state["active_goal_id"] = goal_id
        save(
            root,
            state,
            "init_goal",
            {"goal_id": goal_id, "top_level_criterion": criterion_id},
        )
        checkpoint(root, state)
        print(
            json.dumps(
                {
                    "goal_id": goal_id,
                    "criterion_id": criterion_id,
                    "state_dir": str(root / STATE_DIR),
                },
                ensure_ascii=False,
            )
        )
        return
    state, goal = load(root), None
    goal = active_goal(state)
    if args.command == "status":
        print(
            json.dumps(
                {
                    "active_goal": goal,
                    "active_branches": [
                        b
                        for b in state["branches"].values()
                        if b.get("status") == "active"
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    if args.command == "intake":
        result = intake_result(goal, args.message, read_ledger(root))
        if args.record:
            record = {"goal_id": goal["id"], **result, "message": args.message}
            append_ledger(root, "intake_signal", record)
            save(
                root,
                state,
                "record_intake",
                {k: v for k, v in record.items() if k != "message"},
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.command == "event":
        try:
            payload = json.loads(args.payload)
        except json.JSONDecodeError as exc:
            die(f"--payload must be valid JSON: {exc}")
        if not isinstance(payload, dict):
            die("--payload must be a JSON object")
        record = {"goal_id": goal["id"], "event_type": args.type, "payload": payload}
        append_ledger(root, "host_event", record)
        save(root, state, "record_host_event", record)
        response = {"event_type": args.type, "recorded": True, "execution_authorized": False}
        if args.type in {"prompt_received", "proposal_read"}:
            message = payload.get("message") or payload.get("prompt") or ""
            if not isinstance(message, str) or not message.strip():
                die("prompt_received/proposal_read payload requires message")
            response["signal"] = intake_result(goal, message, read_ledger(root))
        elif args.type == "context_recovered":
            checkpoint(root, state)
            response["brief"] = paths(root)[1].read_text(encoding="utf-8")
        print(json.dumps(response, ensure_ascii=False, indent=2))
        return
    if args.command == "goal":
        if args.goal_action == "add":
            value = add_goal(state, args.title, args.objective)
            add_criterion(state["goals"][value], args.objective, args.observe, "user")
            save(root, state, "add_goal", {"goal_id": value})
            print(value)
            return
        if args.goal_id not in state["goals"]:
            die(f"unknown goal {args.goal_id}")
        old = state["active_goal_id"]
        state["active_goal_id"] = args.goal_id
        save(
            root,
            state,
            "switch_goal",
            {"from": old, "to": args.goal_id, "reason": args.reason},
        )
        checkpoint(
            root,
            state,
            f"Closed: switched goals. Back to: {args.goal_id}. Remaining: review its open criteria. Next: continue its mainline.",
        )
        print(json.dumps({"from": old, "to": args.goal_id}, ensure_ascii=False))
        return
    if args.command == "criterion":
        if args.criterion_action == "add":
            value = add_criterion(
                goal, args.text, args.observe, args.closer, args.kind, args.budget
            )
            save(root, state, "add_criterion", {"criterion_id": value})
            print(value)
            return
        item = criterion(goal, args.id)
        if args.criterion_action == "close":
            if item.get("status") not in {"open", "stale"}:
                die(
                    f"criterion {args.id} is {item.get('status')}; create or realign it before closing again"
                )
            validate_observed(args.observed)
            if item.get("kind") == "discovery" and not args.discovery_outcome:
                die("discovery criterion requires --discovery-outcome")
            observation = {
                "at": now(),
                "observed": args.observed.strip(),
                "object": artifact_key(root, args.object),
                "contract_revision": item["contract_revision"],
            }
            item.setdefault("observations", []).append(observation)
            item.pop("attestation", None)
            item["status"] = (
                "verified" if item["closer"] == "agent" else "awaiting-attestation"
            )
            if item.get("kind") == "discovery":
                append_ledger(
                    root,
                    "discovery_exit",
                    {
                        "goal_id": goal["id"],
                        "criterion_id": item["id"],
                        "outcome": args.discovery_outcome,
                        "observed": args.observed,
                    },
                )
            save(
                root,
                state,
                "close_criterion",
                {"criterion_id": item["id"], "status": item["status"]},
            )
            print(json.dumps(item, ensure_ascii=False))
            return
        if args.criterion_action == "attest":
            if (
                item.get("closer") != "user"
                or item.get("status") != "awaiting-attestation"
            ):
                die("criterion is not awaiting user attestation")
            validate_attestation(args.note)
            item["status"] = "verified"
            item["attestation"] = {"at": now(), "note": args.note.strip()}
            save(root, state, "attest_criterion", {"criterion_id": item["id"]})
            print(json.dumps(item, ensure_ascii=False))
            return
        item["status"], item["stale_reason"] = "stale", args.reason
        save(
            root,
            state,
            "stale_criterion",
            {"criterion_id": item["id"], "reason": args.reason},
        )
        print(json.dumps(item, ensure_ascii=False))
        return
    if args.command == "branch":
        if args.branch_action == "open":
            target = ids(args.target_criteria)
            unknown = [x for x in target if x not in goal["criteria"]]
            if unknown:
                die(f"branch references unknown criteria: {', '.join(unknown)}")
            branch_id = next_id(state["branches"], "B")
            state["branches"][branch_id] = {
                "id": branch_id,
                "goal_id": goal["id"],
                "kind": args.kind,
                "trigger": args.trigger or "",
                "reason": text(args.reason, "--reason"),
                "relation_to_mainline": args.relation or "",
                "target_criteria": target,
                "exit_criteria": text(args.exit_criteria, "--exit-criteria"),
                "return_to": text(args.return_to, "--return-to"),
                "status": "active",
                "created_at": now(),
            }
            save(root, state, "open_branch", {"branch_id": branch_id})
            print(branch_id)
            return
        branch = state["branches"].get(args.id)
        if not branch:
            die(f"unknown branch {args.id}")
        if args.branch_action == "assess":
            if branch.get("status") != "active":
                die("only an active branch can be assessed")
            target = ids(args.target_criteria)
            unknown = [x for x in target if x not in goal["criteria"]]
            if unknown:
                die(
                    f"branch assessment references unknown criteria: {', '.join(unknown)}"
                )
            assessment = {
                "at": now(),
                "mainline_relation": text(
                    args.mainline_relation, "--mainline-relation"
                ),
                "target_criteria": target,
                "ledger_refs": text(args.ledger_refs, "--ledger-refs"),
                "cost_risk": text(args.cost_risk, "--cost-risk"),
                "recommendation": args.recommendation,
            }
            branch["assessment"] = assessment
            branch["relation_to_mainline"], branch["target_criteria"] = (
                assessment["mainline_relation"],
                target,
            )
            append_ledger(
                root,
                "branch_assessment",
                {"goal_id": goal["id"], "branch_id": branch["id"], **assessment},
            )
            save(
                root,
                state,
                "assess_branch",
                {"branch_id": branch["id"], "recommendation": args.recommendation},
            )
            print(
                json.dumps(
                    {
                        "branch": branch,
                        "mainline": {
                            "goal_id": goal["id"],
                            "objective": goal["objective"],
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return
        if branch.get("status") != "active":
            die(f"branch {args.id} is already {branch.get('status')}")
        if (
            branch.get("kind") in {"exploration", "unrelated"}
            and "assessment" not in branch
        ):
            die(
                "exploration branches require an assessment before close; record relation, ledger evidence, cost, and recommendation first"
            )
        result, remaining, next_action = (
            text(args.result, "--result"),
            text(args.remaining, "--remaining"),
            text(args.next, "--next"),
        )
        branch.update(
            {
                "status": "closed",
                "result_type": args.result_type,
                "result": result,
                "integrated_result": args.helped or result,
                "not_adopted": args.not_adopted or "not recorded",
                "decision": args.decision or "not recorded",
                "remaining": remaining,
                "next_mainline_action": next_action,
                "closed_at": now(),
            }
        )
        goal["next_action"] = next_action
        sentence = f"Closed: {result}. Back to: {branch['return_to']}. Helped mainline: {branch['integrated_result']}. Not adopted: {branch['not_adopted']}. Remaining: {remaining}. Next: {next_action}."
        branch["return_sentence"] = sentence
        goal.setdefault("mainline_updates", []).append(
            {
                "at": now(),
                "branch_id": branch["id"],
                "result": branch["integrated_result"],
                "not_adopted": branch["not_adopted"],
                "decision": branch["decision"],
                "remaining": remaining,
                "next": next_action,
            }
        )
        append_ledger(
            root,
            "branch_return",
            {
                "goal_id": goal["id"],
                "branch_id": branch["id"],
                "result_type": args.result_type,
                "result": result,
                "helped": branch["integrated_result"],
                "not_adopted": branch["not_adopted"],
                "decision": branch["decision"],
                "remaining": remaining,
                "next": next_action,
                "return_sentence": sentence,
            },
        )
        save(
            root,
            state,
            "close_branch",
            {"branch_id": branch["id"], "return_sentence": sentence},
        )
        checkpoint(root, state, sentence)
        print(sentence)
        return
    if args.command == "decision":
        record = {
            "goal_id": goal["id"],
            "proposal": text(args.proposal, "--proposal"),
            "mainline_relation": text(args.mainline_relation, "--mainline-relation"),
            "ledger_refs": text(args.ledger_refs, "--ledger-refs"),
            "cost_risk": text(args.cost_risk, "--cost-risk"),
            "decision": args.decision,
        }
        append_ledger(root, "decision", record)
        save(root, state, "record_decision", {"decision": args.decision})
        print("recorded")
        return
    if args.command == "contract":
        if args.affects and args.all:
            die("contract amend accepts either --affects or --all, not both")
        target_ids = list(goal["criteria"]) if args.all else ids(args.affects)
        if not target_ids:
            die("contract amend requires --affects C1,C2 or --all")
        targets = [criterion(goal, x) for x in target_ids]
        goal["contract_revision"] += 1
        for item in targets:
            item["contract_revision"] = goal["contract_revision"]
            if item.get("status") in {"verified", "awaiting-attestation", "stale"}:
                item["status"], item["superseded_reason"] = "superseded", args.reason
        record = {
            "goal_id": goal["id"],
            "revision": goal["contract_revision"],
            "reason": args.reason,
            "affected_criteria": target_ids,
        }
        append_ledger(root, "contract_change", record)
        save(root, state, "amend_contract", record)
        checkpoint(
            root,
            state,
            f"Closed: contract amended. Back to: {goal['objective']}. Remaining: re-observe affected criteria. Next: realign implementation.",
        )
        print("recorded")
        return
    if args.command == "action":
        if args.criterion:
            criterion(goal, args.criterion)
        validate_failure(args.failure_action)
        record = {
            "goal_id": goal["id"],
            "description": text(args.description, "--description"),
            "target": text(args.target, "--target"),
            "criterion": args.criterion or "unspecified",
            "contract_change": args.contract_change,
            "failure_action": args.failure_action.strip(),
            "decision_ref": args.decision_ref or None,
        }
        append_ledger(root, "action_declaration", record)
        save(root, state, "action_declaration", record)
        print("recorded")
        return
    if args.command == "version":
        measure = args.metric or args.observation
        if not measure:
            die("version log requires --metric or --observation")
        if args.metric and args.observation:
            die("version log accepts either --metric or --observation, not both")
        if (
            goal.get("noise_band") is not None
            and args.verdict == "improved"
            and args.delta is None
        ):
            die(
                "--delta is required for an improved version when the goal has a noise band"
            )
        artifact = artifact_key(root, args.artifact) if args.artifact else None
        record = {
            "goal_id": goal["id"],
            "route": text(args.route, "--route"),
            "change": text(args.change, "--change"),
            "hypothesis": text(args.hypothesis, "--hypothesis"),
            "metric": args.metric,
            "observation": args.observation,
            "measure": measure,
            "delta": args.delta,
            "verdict": args.verdict,
            "baseline": args.baseline or "unspecified",
            "artifact": artifact,
        }
        append_ledger(root, "version", record)
        stale = (
            stale_artifact(root, goal, artifact, f"artifact changed: {args.artifact}")
            if artifact
            else []
        )
        record["staled_criteria"] = stale
        save(root, state, "version_log", record)
        print("recorded")
        return
    if args.command == "review":
        records = [
            r
            for r in read_ledger(root)
            if r.get("kind") == "version" and r.get("goal_id") == goal["id"]
        ]
        threshold = (
            args.threshold
            if args.threshold is not None
            else goal.get("plateau_threshold", 3)
        )
        noise = (
            args.noise_band if args.noise_band is not None else goal.get("noise_band")
        )
        route = records[-1].get("route") if records else None
        tail = []
        for record in reversed(records):
            if record.get("route") != route:
                break
            delta, verdict = record.get("delta"), record.get("verdict")
            within = (
                noise is not None and delta is not None and abs(float(delta)) <= noise
            )
            if verdict not in {"no_gain", "regression", "inconclusive"} and not (
                verdict == "improved" and within
            ):
                break
            tail.append(record)
        if args.decision not in ROUTE_DECISIONS:
            die(
                "review requires --decision: continue, explore, ask_user, or infeasible"
            )
        result = {
            "versions_reviewed": len(records),
            "route": route,
            "consecutive_non_improving": len(tail),
            "threshold": threshold,
            "noise_band": noise,
            "plateau_signal": len(tail) >= threshold,
            "stale_criteria": [
                c["id"] for c in goal["criteria"].values() if c.get("status") == "stale"
            ],
            "route_decision": args.decision,
        }
        append_ledger(
            root,
            "route_decision",
            {
                "goal_id": goal["id"],
                "decision": args.decision,
                "reason": args.reason or "review decision",
                "plateau_signal": result["plateau_signal"],
                "tail_length": len(tail),
            },
        )
        save(root, state, "review", result)
        print(json.dumps(result, ensure_ascii=False))
        return
    if args.command == "brief":
        goal_records = [
            r for r in read_ledger(root) if r.get("goal_id") in {None, goal["id"]}
        ]
        versions = [r for r in goal_records if r.get("kind") == "version"]
        returns = [r for r in goal_records if r.get("kind") == "branch_return"]
        groups = criterion_groups(goal)
        pending = groups["awaiting_attestation"] + groups["not_proved"]
        latest = versions[-1] if versions else None
        negative = next(
            (
                r
                for r in reversed(versions)
                if r.get("verdict") in {"no_gain", "regression", "inconclusive"}
            ),
            None,
        )
        next_step = (
            returns[-1].get("next")
            if returns
            else (
                f"obtain {pending[0]['observe']}"
                if pending
                else "continue the declared mainline"
            )
        )
        print(
            "\n".join(
                [
                    f"Mainline: {goal['objective']}",
                    f"Pending: {', '.join(c['id'] for c in pending) if pending else 'none'}",
                    f"Hypothesis: {latest['hypothesis'] if latest else 'none logged'}",
                    f"Negative: {negative['change'] if negative else 'none logged'}",
                    f"Next: {next_step}",
                ]
            )
        )
        return
    if args.command == "audit":
        result = audit_state(state)
        atomic_write(
            paths(root)[3], json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result["status"] != "complete":
            raise SystemExit(1)
        return
    if args.command == "checkpoint":
        print(checkpoint(root, state, args.note))
        return
    die("unknown command")


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(
        description="Maintain a task mainline across branches, versions, and checkout."
    )
    cli.add_argument("--root", type=Path, default=Path.cwd())
    sub = cli.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--title", required=True)
    init.add_argument("--objective", required=True)
    init.add_argument("--observe", required=True)
    init.add_argument("--noise-band", type=float)
    init.add_argument("--plateau-threshold", type=int, default=3)
    init.add_argument("--force", action="store_true")
    sub.add_parser("status")
    sub.add_parser("brief")
    sub.add_parser("audit")
    intake = sub.add_parser("intake")
    intake.add_argument("--message", required=True)
    intake.add_argument("--record", action="store_true")
    event = sub.add_parser("event")
    event.add_argument("--type", required=True, choices=[
        "prompt_received", "proposal_read", "tool_result", "branch_started",
        "branch_closed", "version_changed", "context_recovered", "checkout_requested",
    ])
    event.add_argument("--payload", required=True)
    goal = sub.add_parser("goal")
    goal_sub = goal.add_subparsers(dest="goal_action", required=True)
    goal_add = goal_sub.add_parser("add")
    goal_add.add_argument("--title", required=True)
    goal_add.add_argument("--objective", required=True)
    goal_add.add_argument("--observe", required=True)
    goal_switch = goal_sub.add_parser("switch")
    goal_switch.add_argument("--goal-id", required=True)
    goal_switch.add_argument("--reason", required=True)
    criterion_parser = sub.add_parser("criterion")
    criterion_sub = criterion_parser.add_subparsers(
        dest="criterion_action", required=True
    )
    add = criterion_sub.add_parser("add")
    add.add_argument("--text", required=True)
    add.add_argument("--observe", required=True)
    add.add_argument("--closer", choices=["agent", "user"], required=True)
    add.add_argument("--kind", choices=["result", "discovery"], default="result")
    add.add_argument("--budget")
    close = criterion_sub.add_parser("close")
    close.add_argument("--id", required=True)
    close.add_argument("--observed", required=True)
    close.add_argument("--object", required=True)
    close.add_argument(
        "--discovery-outcome",
        choices=["result_criterion", "new_discovery", "ask_user", "infeasible"],
    )
    attest = criterion_sub.add_parser("attest")
    attest.add_argument("--id", required=True)
    attest.add_argument("--note", required=True)
    stale = criterion_sub.add_parser("stale")
    stale.add_argument("--id", required=True)
    stale.add_argument("--reason", required=True)
    branch = sub.add_parser("branch")
    branch_sub = branch.add_subparsers(dest="branch_action", required=True)
    op = branch_sub.add_parser("open")
    op.add_argument(
        "--kind", choices=["required", "exploration", "unrelated"], required=True
    )
    op.add_argument("--reason", required=True)
    op.add_argument("--exit-criteria", required=True)
    op.add_argument("--return-to", required=True)
    op.add_argument("--trigger")
    op.add_argument("--relation")
    op.add_argument("--target-criteria")
    assess = branch_sub.add_parser("assess")
    assess.add_argument("--id", required=True)
    assess.add_argument("--mainline-relation", required=True)
    assess.add_argument("--target-criteria", default="")
    assess.add_argument("--ledger-refs", required=True)
    assess.add_argument("--cost-risk", required=True)
    assess.add_argument("--recommendation", choices=sorted(DECISIONS), required=True)
    bc = branch_sub.add_parser("close")
    bc.add_argument("--id", required=True)
    bc.add_argument("--result-type", choices=sorted(BRANCH_RESULTS), required=True)
    bc.add_argument("--result", required=True)
    bc.add_argument("--helped")
    bc.add_argument("--not-adopted")
    bc.add_argument("--remaining", required=True)
    bc.add_argument("--next", required=True)
    bc.add_argument("--decision", choices=sorted(DECISIONS))
    decision = sub.add_parser("decision")
    decision_sub = decision.add_subparsers(dest="decision_action", required=True)
    dr = decision_sub.add_parser("record")
    dr.add_argument("--proposal", required=True)
    dr.add_argument("--mainline-relation", required=True)
    dr.add_argument("--ledger-refs", default="none")
    dr.add_argument("--cost-risk", required=True)
    dr.add_argument("--decision", choices=sorted(DECISIONS), required=True)
    contract = sub.add_parser("contract")
    cs = contract.add_subparsers(dest="contract_action", required=True)
    amend = cs.add_parser("amend")
    amend.add_argument("--reason", required=True)
    amend.add_argument("--affects")
    amend.add_argument("--all", action="store_true")
    action = sub.add_parser("action")
    ac = action.add_subparsers(dest="action_action", required=True)
    dec = ac.add_parser("declare")
    dec.add_argument("--description", required=True)
    dec.add_argument("--target", required=True)
    dec.add_argument("--criterion")
    dec.add_argument("--contract-change", choices=["yes", "no"], default="no")
    dec.add_argument("--failure-action", required=True)
    dec.add_argument("--decision-ref")
    version = sub.add_parser("version")
    vs = version.add_subparsers(dest="version_action", required=True)
    vl = vs.add_parser("log")
    vl.add_argument("--route", default="default")
    vl.add_argument("--change", required=True)
    vl.add_argument("--hypothesis", required=True)
    mg = vl.add_mutually_exclusive_group()
    mg.add_argument("--metric")
    mg.add_argument("--observation")
    vl.add_argument("--delta", type=float)
    vl.add_argument(
        "--verdict",
        choices=["improved", "no_gain", "regression", "inconclusive"],
        required=True,
    )
    vl.add_argument("--baseline")
    vl.add_argument("--artifact")
    review = sub.add_parser("review")
    review.add_argument("--threshold", type=int)
    review.add_argument("--noise-band", type=float)
    review.add_argument("--decision", choices=sorted(ROUTE_DECISIONS), required=True)
    review.add_argument("--reason")
    cp = sub.add_parser("checkpoint")
    cp.add_argument("--note", default="")
    return cli


if __name__ == "__main__":
    parsed = parser().parse_args()
    command(parsed, parsed.root.resolve())

