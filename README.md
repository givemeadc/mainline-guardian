# Mainline Guardian

Mainline Guardian keeps an AI task attached to the user's real outcome across side branches, decisions, requirement edits, long conversations, and repeated versions.

It addresses the failure mode where an agent stays busy, passes many checks, and still fails to deliver what the user asked for. It is a mainline-maintenance layer, not a todo app, test framework, or domain evaluator.

## Install

This is a directly usable Skill, not a hosted service and not a second AI model. Copy or clone this directory into the host's skill directory. The CLI needs Python 3.10+ only and writes per-project runtime state under `.mainline/` (which is intentionally not part of the Skill package).

## Quick Start

```powershell
python scripts/goal_guard.py init --title "Deploy app" --objective "App works in the target environment" --observe "A user completes the core flow in a clean target environment"
python scripts/goal_guard.py criterion add --text "Latency target is met" --observe "Production-like run remains below 100 ms" --closer agent
python scripts/goal_guard.py branch open --kind exploration --reason "Compare runtimes" --exit-criteria "Record a route decision" --return-to "Deploy app"
python scripts/goal_guard.py branch assess --id B1 --mainline-relation "May reduce deployment latency" --target-criteria C1 --ledger-refs "none: no comparable local attempt" --cost-risk "one day and reversible" --recommendation test
python scripts/goal_guard.py branch close --id B1 --result-type evidence --result "Runtime A is compatible" --remaining "benchmark" --next "run the benchmark"
python scripts/goal_guard.py criterion close --id C1 --observed "A clean target environment completed the core flow" --object "build/app-v1"
python scripts/goal_guard.py criterion attest --id C1 --note "User said: 'the core flow works for me'"
python scripts/goal_guard.py audit
```

`audit` exits nonzero until every active-goal criterion is proved and all user-owned criteria have the user's quoted attestation.

## Core Commands

- `intake --message [--record]`: compare the latest prompt with the active mainline. This is advisory; `--record` stores the signal but never opens a branch.
- `goal add --title --objective --observe`: create another mainline with its own user-observable checkout.
- `criterion add --text --observe --closer`: declare a result or time-bounded discovery criterion. Discovery criteria require `--budget`.
- `criterion close --id --observed --object`: submit a concrete observation bound to the artifact it observed. Generic labels such as `done` are rejected.
- `criterion attest --id --note`: record a user-owned close with a quoted user statement.
- `contract amend --reason --affects C1,C3` or `--all`: supersede only the criteria affected by a requirement change.
- `action declare --description --target --failure-action`: record a meaningful check or side effect. Failure must lead to a different next action; "increase confidence" or "record the result" is rejected.
- `decision record`: record an external proposal's relation to the mainline, its ledger evidence, cost/risk, and disposition before acting on it.
- `branch open|assess|close`: open a side branch, assess its value against the mainline, then close it with a return sentence. Exploration and unrelated branches cannot close without an assessment.
- `decision record`: save why an external paper, framework, or proposal fits this mainline before adopting it.
- `version log --route --change --hypothesis (--metric|--observation) --verdict`: retain assumptions and negative results. Add `--delta` when a noise band applies (required for an `improved` verdict) and `--artifact` when the artifact changed.
- `review --decision continue|explore|ask_user|infeasible`: inspect the continuous tail of one route, not all historical failures.
- `brief`: print exactly five low-cost recovery lines. `audit`: write the three-section checkout report.

Use `python scripts/goal_guard.py <command> --help` for flags and examples.

## Operating Model

Do not gate reading, searching, analysis, or ordinary discussion. Use the controller only at three boundaries: when a decision or consequential action is made, when a side branch returns or context resumes, and at version review or checkout.

Open a branch when a new request is not currently needed to prove an active criterion. Assess exploration branches before closing them; close with evidence, a decision candidate, an implementation result, a block, or a contract change. The generated return sentence restores the mainline to recent context.

For ambiguous requests, evaluate first. For conditional requests such as "if A helps, implement it", record the conclusion with `decision record` before implementation. Every evaluation should cite relevant ledger entries, including negative results.

The intended paper/architecture workflow is deliberately bounded:

```text
latest prompt -> candidate signal -> assess relation to mainline
             -> bounded branch -> helped / not adopted / remaining
             -> return sentence -> next mainline action
```

The candidate signal is keyword-level recall, not an intent classifier. It is allowed to be wrong; it is not allowed to authorize a goal switch. The useful decision is made when the branch is assessed and closed.

## Host Adapter

[`adapters/claude-code-settings.example.json`](adapters/claude-code-settings.example.json) shows optional Claude Code hooks. Replace `C:/absolute/path/to/mainline-guardian` with the installed skill directory, then merge the hook entries into your Claude Code settings. The wrappers silently do nothing when `.mainline/state.json` does not exist. `brief_hook.py` restores the compact mainline after compaction; `prompt_hook.py` receives the latest prompt and emits only an advisory candidate signal. Neither hook runs a second model, opens a branch, switches goals, or authorizes execution.

The prompt adapter accepts JSON on stdin, for example:

```json
{"prompt":"我看到一篇新的缓存架构论文，可能降低部署延迟"}
```

## Boundaries

The tool protects declared criteria; it cannot know whether the initial criterion set is complete. The user-owned top-level criterion is the generic safeguard against that gap.

It preserves evidence and makes missing decisions visible. It does not decide architecture, risk tolerance, budget, or whether a user should accept a result.

Read [DESIGN.md](DESIGN.md) for the design rationale and [references/state-schema.md](references/state-schema.md) for state details.

## Test

```powershell
python -m unittest discover -s tests -v
python C:\Users\Administrator\.codex\skills\.system\skill-creator\scripts\quick_validate.py .
```

The suite includes a clean-copy product acceptance test. It creates an isolated workspace, runs the paper/architecture branch workflow, verifies continuous plateau detection, checks user-owned checkout, and confirms that runtime state and Python caches are not shipped in the package.

## License

MIT. See [LICENSE](LICENSE).

## Python API and optional LangGraph integration

The package can be used without replacing the host model or chat window. The API is a small control layer around the same CLI state machine:

```powershell
python -m pip install -e .
```

```python
from mainline_guardian import MainlineGuardian

g = MainlineGuardian(".")
g.init(
    title="Deploy the software",
    objective="Make the software usable in the target environment",
    observe="A real user completes the core workflow in a clean target environment",
)
signal = g.handle_event("prompt_received", {
    "message": "I found a new cache architecture paper that may reduce latency"
})
# signal is advisory; it never opens a branch or authorizes implementation.
```

For LangGraph users, install the optional extra and put the check before a research or execution node:

```powershell
python -m pip install -e ".[langgraph]"
```

```python
from mainline_guardian.langgraph import build_mainline_guardian

guard = build_mainline_guardian(".")
result = guard.invoke({"latest_message": "Read this new architecture paper"})
```

The LangGraph node only returns `mainline_signal`, `active_goal_id`, and
`execution_authorized=False`. It does not call another model, choose an
architecture, open a branch, or replace the host agent's workflow. The host
agent still performs the bounded assessment and explicit branch/decision
commands.

### Host-neutral event boundary

The reusable API accepts `prompt_received`, `proposal_read`, and
`context_recovered` events. Claude Code can use the included hooks; Codex,
Cursor, or another host can call the same API from its own prompt/tool event
adapter. Mainline Guardian does not claim to read arbitrary chat history as a
resident service: the host must provide the event.

## Project positioning

Mainline Guardian is an installable AI Skill and a lightweight task-control
layer. It is not a second LLM, not a replacement chat application, and not a
general multi-agent planner. Its job is to keep the user's outcome active while
research, debugging, experiments, and version changes happen around it:

- detect a possible side branch at a prompt boundary;
- compare it with the current mainline and project ledger;
- require an explicit assessment before adoption;
- return a closed branch to the mainline with a next action;
- preserve negative results and route decisions across versions;
- make user-owned acceptance visible at checkout.

The core runtime is zero-dependency Python. LangGraph is an optional adapter for
teams that already use graph-based agent workflows; it is not required for the
Skill or CLI.
