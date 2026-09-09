# Mainline Guardian v2 Design

## 1. Product Definition

Mainline Guardian keeps an AI task aligned with the user's actual outcome across long conversations, side branches, requirement changes, and repeated versions. It is a lightweight control layer, not a planning, testing, or project-management system.

Its checkout rule is simple: auxiliary work may inform the mainline, but cannot silently replace it.

The system protects four failure modes:

| Hijack | What replaces the mainline | Discovery point |
|---|---|---|
| Branch drift | A side topic becomes the active task | branch close or context recovery |
| Decision drift | External advice or a local obstacle becomes the decision without project-fit analysis | decision/action boundary |
| Criterion drift | Tests, files, plans, hashes, or counts replace the user's result | completion audit |
| Experience drift | The latest artifact replaces the accumulated version history | periodic version review |

Plan completion is a candidate proxy under criterion drift, not a separate subsystem.

## 2. Why There Are Three Trigger Points

These failures cannot be found by one universal check. Decision drift is visible when a decision is made. Criterion drift may look reasonable at every intermediate step and is visible only when claiming completion. Experience drift is not visible in one version; it appears when several versions are compared and remain inside a noise band or fail to produce the declared observation. Branch drift appears when a branch should return or when compressed context is restored.

The runtime therefore speaks only at three points:

1. **Decision boundary**: before a contract change, external side effect, or conditional authorization.
2. **Return/recovery boundary**: when a branch closes or a host resumes after compaction.
3. **Review/checkout boundary**: at a declared version/​budget interval, before claiming completion, or when a plateau signal fires.

Read-only work (reading, searching, analysis, discussion, and evaluation) is not gated.

## 3. Minimal Contract at t=0

Do not begin with a questionnaire. Capture one line first:

```text
mainline outcome: what must exist or work
top-level observation: what would be seen in the user's real workflow
closer: user
```

Example:

```text
outcome: deploy the service
observation: a clean environment runs the core user flow and returns the expected result
closer: user
```

If this cannot be stated, the task is not understood. Clarify the task instead of creating a large plan. The tool cannot determine whether the criterion set is complete; the user-attested top-level criterion is the final safeguard.

## 4. Branches and Return-to-Mainline

Every non-mainline branch records:

```text
reason for opening
exit condition
return target
result type
```

Allowed result types are `evidence`, `decision_candidate`, `implementation`, `blocked`, and `contract_change`. A branch never changes the active mainline merely because it is recent or detailed.

On close, the skill emits a short return sentence:

```text
Closed: <what was resolved>.
Back to: <mainline outcome / criterion>.
Remaining: <what is still missing>.
Next: <the next mainline action>.
```

This sentence is an active recovery mechanism: it puts the mainline back into the most recent context.

## 5. Decisions and Conditional Authorization

Research and external recommendations are evidence, not decisions. Before adopting a proposal, record:

```text
proposal
relation to the mainline
relevant ledger entries, including negative results
compatibility or conflict with the current design
cost, risk, and budget impact
decision: adopt / test / reject / defer
```

For conditional requests such as “if A is useful, add it”, the evaluation conclusion is written first. Execution is allowed only after that conclusion exists in the ledger. This prevents the model from granting itself authorization using its own unrecorded conclusion.

Requirement changes are contract changes, even when the edit is small. They invalidate affected criteria, observations, and downstream assumptions until realigned.

## 6. Criteria, Observations, and Checkout

Each criterion is created with an observable requirement:

```text
criterion add --text <claim> --observe <required observation> --closer agent|user
```

Closing a criterion requires submitting the declared observation, not a generic completion flag. A top-level result criterion must use `closer=user`. Agent-submitted observations leave it in `awaiting-attestation` until the user confirms.

An observation records its object and version. If the contract or object changes, dependent observations become `stale`; contract replacement uses `superseded`. Old observations cannot close a new artifact.

The audit has three sections:

```text
proved: declared observation obtained; closer rules satisfied
awaiting attestation: observation submitted; user still owns closure
not proved: open, stale, or superseded
```

Proxy facts (tests passed, file exists, XML parses, hash matches, plan is checked) remain useful evidence, but cannot silently close a user result criterion.

## 7. Version Ledger and Plateau Review

The ledger preserves knowledge outside the conversation transcript. A core change or evaluation writes:

```text
version or run id
change
hypothesis
baseline and comparable conditions
metric or observation
positive result
negative result
route decision
```

Negative results are first-class knowledge. “Wider window produced no gain” must be searchable so later versions do not repeat it. New proposal evaluations must cite relevant ledger entries; the ledger therefore has two consumers: review and decision-making.

Review supports two plateau forms:

- **Metric task**: improvement stays within the user-declared noise band for the declared number of comparable runs.
- **Non-metric task**: the same route is attempted N times without obtaining the declared observation.

Every review writes one route decision:

```text
continue current route
explore a new route
pause and ask the user
declare infeasible
```

The user declares budget, review interval, plateau threshold, and risk preference (stable progress versus variance for upside). The skill does not choose these values for the user.

## 8. Action Boundary and Cost Discipline

Before a side-effecting action, record a compact declaration:

```text
action and target
mainline criterion served
contract_change: yes/no
failure action: what would be done differently if it fails
```

The failure-action field is the hard filter. “It may increase confidence”, “record the result”, or “check again” is not enough. A hash or repeated scan is skipped when its result would not change the next action. Debugging is allowed when different outcomes lead to different next steps. For metric goals with a declared noise band, an `improved` version must provide a numeric delta; a verdict label alone is not evidence.

Logging is tiered:

- Mandatory and immediate: contract changes, criterion closure, branch closure, route decisions, evaluations, and core configuration changes.
- Batched: ordinary file edits and small implementation steps; reconcile them at audit or an existing evaluation event.

The skill must be silent in ordinary read-only turns and produce only a compact brief at recovery or trigger points.

## 9. State and Commands

Use a host-agnostic Python standard-library CLI and a single `.mainline/` directory:

```text
.mainline/
  state.json       goals, contract, branches, criteria, statuses
  ledger.jsonl     decisions, versions, assumptions, negative results
  checkpoint.md    compact recovery and return-to-mainline text
  audit.json       latest three-section audit
```

The v2 command surface stays compact while covering the high-consequence boundaries:

```text
init --title --objective --observe
criterion add|close|attest|stale
branch open|assess|close
decision record
contract amend --affects ...|--all
action declare --failure-action ...
version log --route --change --hypothesis --metric --verdict
review --decision ...
audit
brief
```

Branch and decision records may be subcommands or structured events, but they must not expand into a per-turn checklist.

An exploration or unrelated branch cannot be closed without an assessment. The assessment records its relation to the mainline, relevant ledger evidence, cost/risk, and recommendation. Required implementation branches may close directly when the work itself is the requested task.

## 10. Host Adapters

The core CLI is portable. Optional host adapters provide deterministic:

```text
pre-compaction save
post-prompt brief injection
pre-action declaration capture
pre-checkout audit
```

Without an adapter, state can still be written manually or by a wrapper, but long-context recovery is not guaranteed. The bundled Claude Code example is under `adapters/`; its wrappers exit 0 without `.mainline/state.json`.

## 11. Product Boundaries

Mainline Guardian guarantees consistency of declared state; it cannot infer whether the user's criterion set is complete. A user-attested top-level result criterion is the generic defense against that silent failure.

It also does not choose architecture, risk tolerance, budget, or route changes. It records the decision, preserves the evidence, and makes missing decisions visible.

It is not a todo manager, test runner, hash verifier, or domain-specific evaluator. Those tools may supply observations, but they do not own the checkout.

## 12. Evaluation

Evaluate observable traces, not model self-explanations:

- branch return rate and mainline retention;
- declared-versus-observed action mismatches;
- criteria closed without their declared observation;
- top-level criteria closed without user attestation;
- stale observations incorrectly reused;
- negative ledger entries preserved and cited;
- plateau reviews producing route decisions;
- ordinary turns with no unnecessary tool output.

The first regression scenarios are the real paper-editing/branch drift trace and the Visio/proxy-checkout trace.
