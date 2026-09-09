---
name: mainline-guardian
description: Use when a task has multiple steps, side requests, decisions, requirement changes, long context, or repeated versions and the AI must retain the user's intended outcome as the active mainline.
---

# Mainline Guardian

Keep the user's outcome as the only mainline. Research, plans, tests, files, metrics, hashes, external advice, and the newest artifact are evidence or tools; none can silently replace the result the user asked for.

## Trigger Only At Boundaries

Do not classify every message or log ordinary reads, searches, analysis, discussion, or small edits.

Use the controller when:

1. A request changes the contract, adopts a proposal, invokes a side effect, or says "if A helps, implement A".
2. A request is not needed to prove an active criterion: open a branch. On branch close or context recovery, inject `brief` and use the return sentence.
3. A core evaluation/configuration change, version review, or checkout occurs.

At a host prompt boundary, `intake` may compare the latest message with the recorded mainline. Treat keyword overlap as recall only: it suggests a candidate branch but does not understand intent, open a branch, switch goals, or authorize work. For a new paper, architecture, framework, or other side request, explicitly open and assess a branch before adopting anything. Ask: "which part, if any, helps the active outcome?" Never assume: "the newest proposal is now the plan."

When a request is ambiguous between evaluation and execution, evaluate first and ask before acting. For conditional authorization, write `decision record` before execution.

## Start With One User-Owned Outcome

```text
python scripts/goal_guard.py init --title "..." --objective "..." --observe "..."
```

The initial observation must describe the user's real workflow. It creates the required top-level `closer=user` criterion. If it cannot be written, clarify the task instead of making a large plan.

## Maintain The Mainline

- Open a branch with a reason, exit condition, and return target; assess exploration/unrelated branches before closing them.
- Keep branch status `active` until assessment and close. Closing must state what helped the mainline, what was not adopted, what remains, and the next mainline action.
- Record external proposals with `decision record`, including relevant ledger entries and negative results.
- Use `contract amend --affects ...` for requirement changes. Never silently change a contract.
- Use `action declare` only for consequential checks or side effects. Its `--failure-action` must name a different next action; proxy-only wording is rejected.
- Close criteria with their declared observation and `--object`. A user-owned criterion remains `awaiting-attestation` until a quoted user statement is recorded with `criterion attest`.
- Log core versions with a route, hypothesis, comparable metric or observation, verdict, and artifact. When a noise band is configured, an `improved` version needs `--delta`.
- At review, inspect the continuous tail of the current route. Use the user's noise band for metric work, or repeated failure to obtain the declared observation for non-metric work. Record `continue`, `explore`, `ask_user`, or `infeasible`.
- When small local variations reach the plateau threshold, perform a route review before another micro-tune.

## Checkout

Run `python scripts/goal_guard.py audit` before claiming completion. Report `proved`, `awaiting attestation`, and `not proved` separately. Do not claim completion from plan completion, hash equality, file existence, or structural parsing alone.

The controller writes `.mainline/state.json`, a lazy `ledger.jsonl`, `checkpoint.md`, and `audit.json`. Optional host adapters persist recovery state through context compaction. The tool protects declared criteria but cannot prove that the user declared every necessary criterion.

## Optional programmatic integration

The Skill can be used from a host adapter without starting a second AI model:

```python
from mainline_guardian import MainlineGuardian

guardian = MainlineGuardian(".")
signal = guardian.handle_event("prompt_received", {"message": latest_user_message})
```

The returned signal is advisory. It can say `mainline_context` or
`candidate_branch`, include matched mainline terms and related ledger entries,
and always reports `execution_authorized: false`. The host agent must assess a
candidate against the mainline and explicitly open/close a branch if needed.

For an existing LangGraph workflow, use the optional integration:

```python
from mainline_guardian.langgraph import build_mainline_guardian
workflow = build_mainline_guardian(".")
```

Install the optional dependency with `pip install -e '.[langgraph]'`. Without
LangGraph, the standard-library CLI, Python API, and host hooks continue to
work. Do not present keyword recall as semantic understanding or automatic
branch creation.
