# LarpAI — Triage Assistant (AI-Z Challenge, MAIN Summit 2026)

A hospital **triage support agent** that finds every piece of sensitive patient data, protects it, prepares a
structured triage note, and **stops for the nurse's decision**. Every model call goes through **BRANE**.

> The AI suggests, the nurse decides. Patient data never reaches an external AI model.

## What it does

1. A nurse pastes an intake note or patient message (synthetic data only).
2. **Local guard, before BRANE:** names, contact details, IDs replaced by case tokens; date of birth → age; payment
   data removed; religious / origin labels hidden; hidden instructions quarantined.
3. **BRANE** inspects the case with our team policy and routes it: patient cases → **internal GPU model**,
   general questions without a patient → cloud model, forbidden requests → **refused (HTTP 422)**.
4. The AI prepares a triage note with a **suggested** urgency level (1–5).
5. **The nurse picks the category herself** (nothing preselected). If she differs from the AI, a reason is required.
   Every decision is logged (`final_category`, `ai_suggested`, `overrode_ai`).
6. If BRANE is unavailable, **nothing is sent** (fail-closed).

## Features

- **Nurse-first (blind) assessment:** the nurse picks her own category before the AI suggestion is shown; then both
  appear side by side. Her first choice, the AI's and the final one are logged (`changed_after_seeing_ai` measures anchoring).
- **Privacy receipt per case:** counts only (identifiers replaced, values removed, route, model, who decided), downloadable as JSON.
- **Time-saved counter:** measured AI + review time vs a manual baseline per case (`BASELINE_MINUTES`, default 8,
  a team estimate to be replaced with a sourced figure).
- **Multilingual patient messages:** Dutch, German, French, Spanish detected; the note is always written in English and
  every patient case stays on the internal model.

## Run it

Requirements: Python 3.10+ (standard library only), internet access to BRANE.

```bash
cd agent
cp .env.example .env        # then put the team key in BRANE_API_KEY (never commit .env)
python server.py            # open http://127.0.0.1:8765
```

## Repository map

| Path | What |
|---|---|
| `agent/server.py` | The agent: pipeline, BRANE client (only network path to a model), fail-closed, audit log |
| `agent/legal.py` | The legal "brain": per-category legal floor, situations, model instructions |
| `agent/static/index.html` | Nurse interface |
| `agent/policy/triage_policy.json` | BRANE team policy (25 categories + 8 semantic categories), policy as code |
| `agent/evidence/MAIN_Five_Tests_LarpAI.csv` | **Hand-in:** T1–T5 + E1–E5 with live X-Brane headers |
| `agent/evidence/MAIN_Policy_Matrix_LarpAI.csv` | **Hand-in:** rules R1–R20 with legal sources and product-gap notes |
| `agent/COMPLIANCE.md` | Requirement → where it is met → how it is verified |
| `agent/samples.json` | Synthetic test cases |
| `starter-kit/`, `MAIN_*` | Organisers' starter kit and templates (unchanged) |

## Commands (run inside `agent/`, with `server.py` running)

| Command | Purpose |
|---|---|
| `python policy_sync.py verify policy/triage_policy.json` | Check BRANE still has our policy (must say **OK**) |
| `python policy_sync.py apply policy/triage_policy.json` | Re-apply our policy if someone changed it |
| `python verify_all.py` | 14 compliance checks against live BRANE (PASS/FAIL with evidence) |
| `python make_evidence.py` | Regenerate the two hand-in CSVs from live runs |
| `python brane_only_check.py` | What BRANE alone does with each raw sample |

## Team rules

- **Synthetic data only.** No real patient data anywhere.
- **Never commit `.env`** or the API key.
- **Do not click "Save Policy Live" or a preset in the BRANE workbench.** It overwrites the team policy for everyone.
  Use `policy_sync.py` instead, after agreeing in the team.
- Before the demo and before handing in: `verify` the policy, run `verify_all.py`, then `make_evidence.py`.

## Status (21 Nov)

- `verify_all.py` 14/14 · hand-in CSVs T1–T5 + E1–E5 10/10 PASS · organisers' starter script 6/6 PASS against our policy.
- Open: verify legal citations against official texts; business figures (time saved); demo script and rehearsal.
