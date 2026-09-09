# Mainline Guardian v0.3: Integration-ready package

**Date:** 2026-09-08

## What changed
- Added `mainline_guardian` Python package with `MainlineGuardian` API and a host-neutral `handle_event()` interface.
- Added a LangGraph-compatible `MainlineGuardianNode` and optional `build_mainline_guardian()` graph factory. LangGraph remains an extra, not a core dependency.
- Added `event --type --payload` to the CLI. Prompt/proposal events are recorded and return the same advisory candidate signal as `intake`; no event opens branches or authorizes execution.
- Enriched intake output with matched mainline terms, related ledger context, and explicit `execution_authorized=false` / `branch_opened=false` fields.
- Added Python packaging through `pyproject.toml`, including console entry point and packaged controller resource for wheel installs.
- Added API integration tests and extended clean-release validation.

## Validation
- `python -m unittest discover -s tests -q`: 35 tests passed.
- `python -m compileall -q scripts mainline_guardian adapters`: passed.
- Skill quick validation: passed.
- Fresh archive test suite: 35 tests passed.
- Fresh archive Skill validation: passed.
- Fresh archive wheel build: passed; wheel contains `mainline_guardian/goal_guard.py`.

## Product boundary
The project is an installable Skill and task-control layer. It does not create a second LLM or replace Codex/Claude/LangGraph's main agent. Host hooks or graph nodes pass events to it. It returns advisory signals and retains task state; the host agent explicitly assesses branches and performs work.