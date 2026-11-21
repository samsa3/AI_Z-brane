# Agent Planning Board

Shared plan for all AI assistants and humans. Read `AGENTS.md` first. Free-form discussion goes to `AGENT-CHAT.md`.
Format for claimed tasks: `- [ ] <task> (@agent: <human>-<tool> / <role>)`. Done: `- [x] <task> — completed by @<name> on YYYY-MM-DD`.

## 1. Current objective
- **Objective:** polish the nurse UI for the 3-minute live demo without changing legal behaviour; keep `verify_all.py` at 14/14.
- **Deadline:** Sat 21 Nov 2026, 10:30 CET (hand-in), 15:00 finals.

## 2. Plan
1. UI polish (teammates) on branches `ui/<name>` → PR → merge after `verify_all.py` 14/14.
2. Non-code: verify legal citations, business figures (`BASELINE_MINUTES`), demo script + backup video.
3. Before hand-in: `policy_sync.py verify`, `verify_all.py`, `make_evidence.py`, hand in `agent/evidence/*.csv`.

## 3. Task board

### 3.1 Backlog (UI — pick one, claim it)
- [ ] Better side-by-side comparison of nurse vs AI (highlight the AI's red flags that explain a difference)
- [ ] Printable / nicer privacy receipt view (still counts only, no patient data)
- [ ] Optional: a small "today" panel (cases, time saved, overrides) using `GET /api/stats`

### 3.2 Backlog (non-code)
- [ ] Verify legal citations against EUR-Lex / CURIA / HUDOC (AI Act Annex III 5(d), GDPR Art. 22, C-634/21, C-21/23, Pindo Mulla)
- [ ] Business case: sourced manual triage time per case → set `BASELINE_MINUTES`; value story
- [ ] Demo script (3 min) + 2 rehearsals + backup screen recording
- [ ] Ask the AI-Z desk what exactly T5 means (template vs PDF wording differ)

### 3.3 In progress
- (none)

### 3.4 Blocked
- (none)

### 3.5 Done
- [x] Agent + BRANE integration, fail-closed, local guard — completed by @rodrigo-claude on 2026-11-20
- [x] BRANE team policy v2 from the legal brain (21 local, 4 refuse, 8 semantic) — completed by @rodrigo-claude on 2026-11-20
- [x] Hand-in CSVs: T1–T5 + E1–E5 10/10 PASS, policy matrix R1–R20 — completed by @rodrigo-claude on 2026-11-21
- [x] Nurse-first blind assessment, privacy receipt, time-saved counter, multilingual messages — completed by @rodrigo-claude on 2026-11-21
- [x] `verify_all.py` 14/14 live compliance checks — completed by @rodrigo-claude on 2026-11-21
- [x] Hospital-style UI: two-column layout, 4-step progress bar, 3 key privacy steps, colour-coded triage tiles with target times, 1–5 shortcuts, mobile layout — completed by @rodrigo-claude on 2026-11-21

## 4. Decisions log
| Date | Decision | Why | Who |
|---|---|---|---|
| 2026-11-20 | Use case: hospital triage support | Rich legal ground (GDPR Art. 9, AI Act Annex III 5(d)), clear human decision | team |
| 2026-11-20 | The nurse decides, the AI only suggests | GDPR Art. 22, AI Act Art. 14, challenge brief | team |
| 2026-11-20 | BRANE is the main filter, local guard as defence in depth | BRANE missed name variants and mis-tags drugs | @rodrigo-claude, approved by Rodrigo |
| 2026-11-20 | Rules follow the team legal brain: identifiers LOCAL ONLY, patient cases on the internal GPU | legal brain document | team legal |
| 2026-11-21 | Nurse-first blind assessment | Reduce automation bias (AI Act Art. 14(4)(b)) | Rodrigo |
| 2026-11-21 | BRANE policy is changed only via `policy_sync.py` after a chat entry | Workbench saves overwrote the policy twice | team |
