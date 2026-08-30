# Mainline Guardian

Mainline Guardian keeps an AI task attached to the user's real outcome across side branches, decisions, requirement edits, long conversations, and repeated versions.

It addresses the failure mode where an agent stays busy, passes many checks, and still fails to deliver what the user asked for. It is a mainline-maintenance layer, not a todo app, test framework, or domain evaluator.

## Install

Copy this directory into a host's skill directory. The CLI needs Python 3.10+ only and writes workspace state under `.mainline/`.

## Quick Start

```powershell
python scripts/goal_guard.py init --title "Deploy app" --objective "App works in the target environment" --observe "A user completes the core flow in a clean target environment"
python scripts/goal_guard.py criterion add --text "Latency target is met" --observe "Production-like run remains below 100 ms" --closer agent
python scripts/goal_guard.py branch open --kind exploration --reason "Compare runtimes" --exit-criteria "Record a route decision" --return-to "Deploy app"
python scripts/goal_guard.py branch close --id B1 --result-type evidence --result "Runtime A is compatible" --remaining "benchmark" --next "run the benchmark"
python scripts/goal_guard.py criterion close --id C1 --observed "A clean target environment completed the core flow" --object "build/app-v1"
python scripts/goal_guard.py criterion attest --id C1 --note "User said: 'the core flow works for me'"
python scripts/goal_guard.py audit
```

`audit` exits nonzero until every active-goal criterion is proved and all user-owned criteria have the user's quoted attestation.

## Core Commands

- `criterion add --text --observe --closer`: declare a result or time-bounded discovery criterion. Discovery criteria require `--budget`.
- `criterion close --id --observed --object`: submit a concrete observation bound to the artifact it observed. Generic labels such as `done` are rejected.
- `criterion attest --id --note`: record a user-owned close with a quoted user statement.
- `contract amend --reason --affects C1,C3` or `--all`: supersede only the criteria affected by a requirement change.
- `action declare --description --target --failure-action`: record a meaningful check or side effect. Failure must lead to a different next action.
- `decision record`: record an external proposal's relation to the mainline, its ledger evidence, cost/risk, and disposition before acting on it.
- `version log --route --change --hypothesis --metric --verdict`: retain assumptions and negative results. Add `--delta` when a noise band applies and `--artifact` when the artifact changed.
- `review --decision continue|explore|ask_user|infeasible`: inspect the continuous tail of one route, not all historical failures.
- `brief`: print exactly five low-cost recovery lines. `audit`: write the three-section checkout report.

Use `python scripts/goal_guard.py <command> --help` for flags and examples.

## Operating Model

Do not gate reading, searching, analysis, or ordinary discussion. Use the controller only at three boundaries: when a decision or consequential action is made, when a side branch returns or context resumes, and at version review or checkout.

Open a branch when a new request is not currently needed to prove an active criterion. Close it with evidence, a decision candidate, an implementation result, a block, or a contract change; the generated return sentence restores the mainline to recent context.

For ambiguous requests, evaluate first. For conditional requests such as "if A helps, implement it", record the conclusion with `decision record` before implementation. Every evaluation should cite relevant ledger entries, including negative results.

## Host Adapter

[`adapters/claude-code-settings.example.json`](adapters/claude-code-settings.example.json) shows optional Claude Code hooks. Replace `C:/absolute/path/to/mainline-guardian` with the installed skill directory, then merge the hook entries into your Claude Code settings. The wrappers silently do nothing when `.mainline/state.json` does not exist.

## Boundaries

The tool protects declared criteria; it cannot know whether the initial criterion set is complete. The user-owned top-level criterion is the generic safeguard against that gap.

It preserves evidence and makes missing decisions visible. It does not decide architecture, risk tolerance, budget, or whether a user should accept a result.

Read [DESIGN.md](DESIGN.md) for the design rationale and [references/state-schema.md](references/state-schema.md) for state details.

## Test

```powershell
python -m unittest discover -s tests -v
```

## License

MIT. See [LICENSE](LICENSE).
