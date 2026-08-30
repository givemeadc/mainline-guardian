---
name: mainline-guardian
description: Use when a task has multiple steps, side requests, decisions, requirement changes, long context, or repeated versions and the AI must retain the user's intended outcome as the active mainline.
---

# Mainline Guardian

Keep the user's outcome as the only mainline. Research, plans, tests, files, metrics, hashes, external advice, and the newest artifact are evidence or tools; none can silently replace the result the user asked for.

## Trigger Only At Boundaries

Do not classify every message or log ordinary reads, searches, analysis, discussion, or small edits.

Use the controller when:

1. A request changes the contract, adopts a proposal, invokes a side effect, or says "if A helps, implement A."
2. A new request is not needed to prove an active criterion: open a branch. On branch close or context recovery, inject `brief` and use the return sentence.
3. A core evaluation/configuration change, version review, or checkout occurs.

When a request is ambiguous between evaluation and execution, evaluate first and ask before acting. For conditional authorization, write `decision record` before execution.

## Start With One User-Owned Outcome

```text
python scripts/goal_guard.py init --title "..." --objective "..." --observe "..."
```

The initial observation must describe the user's real workflow. It creates the required top-level `closer=user` criterion. If it cannot be written, clarify the task instead of making a large plan.

## Maintain The Mainline

- Open a branch with a reason, exit condition, and return target; close it with remaining work and the next mainline action.
- Record external proposals with `decision record`, including relevant ledger entries and negative results.
- Use `contract amend --affects ...` for requirement changes. Never silently change a contract; do not use `--all` unless every criterion really changed.
- Use `action declare` only for consequential checks or side effects. Its `--failure-action` must state what failure changes; otherwise skip the action.
- Close a criterion with its declared observation and `--object`. A user-owned criterion remains `awaiting-attestation` until a quoted user statement is recorded with `criterion attest`.
- Log core versions with a route, hypothesis, comparable metric or observation, verdict, and artifact. This preserves both positive and negative knowledge.
- At review, inspect the continuous tail of the current route. Use the user-declared noise band for metric work, or repeated failure to obtain an observation for non-metric work. Record `continue`, `explore`, `ask_user`, or `infeasible`.

## Checkout

Run `python scripts/goal_guard.py audit` before claiming completion. Report `proved`, `awaiting attestation`, and `not proved` separately. Do not claim completion from plan completion, hash equality, file existence, or structural parsing alone.

The controller writes `.mainline/state.json`, a lazy `ledger.jsonl`, `checkpoint.md`, and `audit.json`. Use the optional host adapter to persist recovery state through context compaction. It protects declared criteria but cannot prove that the user declared every necessary criterion.
