# State Schema v2

State lives in `.mainline/state.json` and uses schema version `2`.

```json
{
  "schema_version": 2,
  "active_goal_id": "G1",
  "goals": {
    "G1": {
      "id": "G1",
      "title": "Deploy service",
      "objective": "Service works in the target environment",
      "contract_revision": 1,
      "criteria": {
        "C1": {
          "id": "C1",
          "text": "Core user flow works",
          "observe": "Run the flow in a clean target environment",
          "closer": "user",
          "kind": "result",
          "status": "open",
          "observations": [],
          "contract_revision": 1
        }
      },
      "deliverables": {},
      "status": "active"
    }
  },
  "branches": {},
  "events": []
}
```

Criterion statuses are `open`, `verified`, `awaiting-attestation`, `stale`, and `superseded`. Each observation stores a normalized artifact object and contract revision. A user-owned criterion can only become `verified` through `criterion attest`, whose note must quote the user's words. A changed artifact stales observations that depend on it; an amended contract supersedes affected criteria. Every state mutation appends an event. Version and decision records are append-only JSON Lines in `ledger.jsonl`; the ledger is created lazily on first record.
