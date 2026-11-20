# LarpAI Triage Assistant — compliance map

How every challenge requirement and team rule is met, where it lives in the code, and how it is verified.
Run `python verify_all.py` (with `python server.py` running) to re-check everything live: it prints PASS/FAIL with evidence.

## 1. What the agent does (end to end)

| Step | What happens | Code |
|---|---|---|
| 1 | Synthetic triage case enters (ER intake / patient message / protocol question) | `static/index.html`, `samples.json` |
| 2 | Local check before BRANE: quarantine embedded instructions; detect Art. 9 / Art. 10 / Art. 22 signals; find identifiers | `legal.py` → `local_scan()` |
| 3 | BRANE dry run `POST /api/v1/policy/test`: what BRANE detects and what the team policy would do | `server.py` → `analyse()` step 3 |
| 4 | Legal decision: strictest of BRANE team policy and our legal floor | `legal.py` → `LEGAL_FLOOR`, `server.py` step 4 |
| 5 | Identifiers minimised locally (names → `[FIRST_n] [LAST_n]`, DOB → age), then the real call `POST /api/v1/chat/completions` through BRANE (`model: auto`) | `server.py` step 5, `brane()` |
| 6 | Structured triage note shown as a SUGGESTION; nurse Approves / Edits / Rejects | `static/index.html`, `POST /api/decision` |
| 7 | Every decision logged with X-Brane headers, no raw personal data | `logs/audit.jsonl` |

## 2. Requirement → where → how verified

| # | Requirement | Source | Where it is met | Verified by |
|---|---|---|---|---|
| 1 | Every model call goes through BRANE; no direct provider call | AGENTS.md; brief "OpenAI via BRANE" | `server.brane()` is the only network path to a model | `verify_all.py` check 1 |
| 2 | Fail closed: BRANE unavailable → nothing sent, no fallback | PDF "Check failure"; AGENTS.md | `BraneDown` → stop in steps 3 and 5 | check 11, CSV row E5 |
| 3 | Synthetic data only | Brief; AGENTS.md | `samples.json` (example.org, +00, fictional names) | check 3 |
| 4 | No secrets in shared files | AGENTS.md; organiser mail | key only in `.env` (git-ignored) | check 2 |
| 5 | ≥ 3 cited protection rules, implemented | Brief minimum requirements | `evidence/MAIN_Policy_Matrix_LarpAI.csv` R1–R11; `policy/triage_policy.json`; `legal.py` | check 5 |
| 6 | T1 permitted control (cloud, redacted false) | Brief security gate | protocol question, no patient → cloud | check 6, CSV T1 |
| 7 | T2 protected data | Brief security gate | identifiers minimised + clinical content → local GPU | check 7, CSV T2 |
| 8 | T3 repeated details | Brief security gate | multi-pass name masking; consistent tokens | check 8, CSV T3 |
| 9 | T4 bypass attempt | Brief security gate; AGENTS.md | injection quarantined before BRANE; masking does not depend on detecting it | check 9, CSV T4, sample X1 |
| 10 | T5 special category → local / 422 | Brief security gate | `HEALTH_DATA`/Art. 9 → local; semantic `PATIENT_CLINICAL_CONTEXT` | check 10, CSV T5 |
| 11 | Agent never takes the final decision | AGENTS.md; GDPR Art. 22; AI Act Art. 14 | autonomous requests refused (local + BRANE 422); Approve/Edit/Reject UI | check 12, CSV E1 |
| 12 | Every decision logged and traceable | AGENTS.md; GDPR Art. 5(2) | `logs/audit.jsonl` (hashes, labels, headers only) | check 13 |
| 13 | Hand-in CSVs in template format | Starter kit README §4 | `make_evidence.py` → `evidence/*.csv` | check 14 |

## 3. Current status (20 Nov, ~22:45 UTC) — legal brain integrated

- Source of the rules: team legal brain (`the brain.docx`), four-column matrix. Implemented in `legal.py` (LEGAL_FLOOR,
  LOCAL_SIGNALS, system prompt), `policy/triage_policy.json` v2 (applied to BRANE 22:35 UTC: 21 local, 4 refuse,
  8 semantic categories; v1 kept as `triage_policy_v1.json`) and `evidence/MAIN_Policy_Matrix_LarpAI.csv` (R1–R20).
- Key changes from the brain: all identifiers LOCAL ONLY and always removed from prompts (no toggle any more);
  DOB → age; payment data removed from the prompt; religious / origin labels hidden while a specific treatment
  preference is kept; new refusals for capacity/consent decisions, emotion inference and trait-based prioritisation;
  every patient case stays on the internal GPU (only general questions without a patient use the cloud); 30-day log retention.
- `python verify_all.py`: **14/14 PASS**. `python make_evidence.py`: T1–T5 + E1–E5 **10/10 PASS**
  (E3 = trait-based prioritisation refused, E4 = capacity/consent decision refused).
- Risk: anyone clicking **Save Policy Live** in the workbench overwrites this. Check with
  `python policy_sync.py verify policy/triage_policy.json` before the demo and before handing in.

### Added 21 Nov
- Nurse-first blind assessment (initial / AI / final category logged, `changed_after_seeing_ai`), privacy receipt per case,
  time-saved counter (baseline = team estimate), multilingual patient messages (NL/DE/FR/ES, note in English, always local).
- Fixed: BRANE tagged the anticoagulant "Marcumar" as PERSON; known medication names are now never masked.

## 4. Known limits (documented as product gaps in the policy matrix)

- BRANE tags drug names as PERSON ("Marcumar", confidence 1.0): medication names are kept by an allow-list.
- BRANE alone missed name variants on cloud turns ("J. Beispiel", bare "Petra") → our local masking is mandatory on cloud turns.
- BRANE scans our own system prompt as data → prompts were reworded (e.g. 'Mark uncertain' read as a person, 'religion' in an instruction read as RELIGIOUS_BELIEF).
- Once identifiers are tokenised BRANE may route a patient case to the cloud; the agent re-checks the masked text and pins the internal model (`explicit_local_model`).
- This demo's BRANE is hosted by AI-Z and receives the raw text for inspection; in production BRANE would run on-premise.
- Built-in health detection varies between runs → semantic category is the stable safety net.
- Legal citations still to be verified against the official texts (legal document in preparation by the team).
