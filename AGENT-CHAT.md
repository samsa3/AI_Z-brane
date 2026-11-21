# Agent Shared Chat Log

Append-only coordination log for all AI assistants and humans. Read `AGENTS.md` first.

## 0. Protocol
```text
[YYYY-MM-DD HH:MM UTC] @<human>-<tool> (<role>): one-line summary

Details, findings, files touched.
Questions: …
Handoff to @name: …
```
Name yourself `@<teammate>-<tool>` (e.g. `@charly-codex`). Timestamps in UTC (Maastricht = UTC+1).
Never delete or rewrite other entries; on merge conflicts keep both sides.

## 1. Active conversation

[2026-11-20 23:53 UTC] @rodrigo-claude (agent dev): backend, BRANE policy, legal rules and hand-in evidence are done — UI is open for teammates

What exists on `main`:
- `agent/`: triage agent (`server.py`), legal rules (`legal.py`), UI (`static/index.html`), BRANE policy v2 (`policy/triage_policy.json`), evidence CSVs, `verify_all.py`, `COMPLIANCE.md`.
- Features: nurse-first blind assessment, privacy receipt, time-saved counter, Dutch/German/French/Spanish messages.

Verified (live BRANE, 20 Nov ~23:30 UTC):
- `verify_all.py` 14/14 PASS; `make_evidence.py` T1–T5 + E1–E5 10/10 PASS (twice); organisers' starter script 6/6 PASS.

Not verified:
- Legal citations against official texts (they come from the team legal brain).
- `BASELINE_MINUTES = 8` is an estimate.

Rules for UI work: read `AGENTS.md` §7 (UI contract). Keep the blind flow, the 5 category buttons markup, the button texts "Confirm decision" / "Edit note" / "Reject AI note", the reason-on-override rule and the Details evidence area. Work on a `ui/<name>` branch, run `python verify_all.py` before the PR.

BRANE policy: currently v2 (0 allow · 0 placeholder · 21 local · 4 refuse · 8 semantic). Do NOT click "Save Policy Live" or presets in the workbench.

Handoff to the UI owners (@charly-*, @sam-*, @patricio-*): pick a task from `AGENT-PLAN.md` §3.1, claim it there, and post a start message here.

[2026-11-21 00:55 UTC] @rodrigo-claude (UI): taking the hospital-style UI polish (visual design + nurse-first stepper + mobile/accessibility)

- Files: `agent/static/index.html` only. No backend, legal or policy changes.
- Branch: `ui/hospital-polish`. Will keep all AGENTS.md §7 invariants and run `verify_all.py` before merging.
- Teammates: the remaining UI tasks in AGENT-PLAN §3.1 (comparison highlight, printable receipt, today panel) are still free; if you pick one, branch from `main` after my merge to avoid conflicts in `index.html`.

## 2. Parking lot / questions for humans
- [ ] Sourced figure for manual triage documentation time per case (sets `BASELINE_MINUTES`) — asked by @rodrigo-claude on 2026-11-21
- [ ] Who verifies the legal citations before the pitch? — asked by @rodrigo-claude on 2026-11-21
- [ ] Ask the AI-Z desk the exact meaning of T5 — asked by @rodrigo-claude on 2026-11-21

## 3. Notes
- Windows: clone with `git -c core.longpaths=true clone …` if paths are too long.
