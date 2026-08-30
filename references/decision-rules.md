# Decision Rules

## Mainline

The active mainline is the user's outcome and its declared criteria. A recent topic, external recommendation, plan step, or latest artifact does not replace it.

## Branches

Branches are temporary. They must have a reason, exit condition, return target, and result type. Closing a branch emits a return-to-mainline sentence.

## Actions

Read-only work is free. Side-effecting actions record their target, criterion, contract-change flag, and failure action. The failure-action field is the useful gate: if failure would not change the next action, skip the check.

## Decisions

External advice and local obstacles are evidence until a recorded decision relates them to the mainline, project history, cost, risk, and compatibility. Conditional authorization records the evaluation conclusion before execution.

## Completion

Completion requires all required criteria proved, no active branches, no stale/superseded result criteria, and user attestation for the top-level result criterion. The tool cannot judge whether the criterion set is complete.

## Review

Metric plateau: repeated comparable runs remain within the user-declared noise band. Non-metric plateau: the same route fails to obtain the declared observation N times. Review must write a route decision: continue, explore, ask-user, or infeasible.
