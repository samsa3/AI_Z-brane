# MAIN Summit 2026 · AI-Z Challenge Track Starter Kit

Zero external Python packages required (`python3 >= 3.9` standard library only — or use the standard `openai` SDK in Python / TypeScript against `https://brane.ai-z.io/api/v1`).

---

## 1. Open Your Team's Visual Policy Workbench (`/team-policy`)

Every team (`Team 01` … `Team 25`) gets its own isolated **Department** on our live `BRANE AIF` environment (`BRANE Mega` — frontier cloud + dedicated local GPU model).

Open **`https://brane.ai-z.io/team-policy`** in your browser and paste your team's `brn_live_...` key. You will immediately see everything BRANE AIF offers:

### A. Starting State = 100% OPEN Department (`25 / 25 = allow`)
Your department starts **100% open**:
- All **25 built-in categories** start at **`Send as Typed -> Cloud`** (`allow`) and **0 custom semantic categories** are active (a 1-click preset button in `/team-policy` lets you load the recommended 17-category floor anytime, or configure every category from scratch for your use case).
- Available models (`GET /api/v1/models`):
  - **Cloud (OpenRouter):** `auto` / `openrouter:anthropic/claude-haiku-5.5` (default), `openrouter:openai/gpt-6-luna`, `openrouter:mistralai/mistral-large-4-0`
  - **Local (Zero Cloud Egress):** `vllm:deepseek-v4.1-flash` (fast default local), `vllm:qwen3.8-27b-nvfp4` (on-box GPU)
- If you run `python3 brane_agent_starter.py` before configuring your policy, `T2`, `T3`, `T5` and `E1` will **fail** — proving why unchecked cloud AI breaks European law!

### B. Rule per Built-In Category (All 25 Categories across 6 Groups)
You can set an explicit rule for **each individual built-in category** (`GET /api/v1/policy/catalog`):
1. **Contact (`contact`):** `PERSON`, `EMAIL`, `PHONE`, `ADDRESS`, `IP_ADDRESS`
2. **Company (`company`):** `ORG`, `TRADE_REGISTER`, `VAT_ID` *(e.g. keep `ORG = allow` if your workflow needs public company lookups while `PERSON = placeholder`!)*
3. **Government & Civil IDs (`identifiers`):** `DATE_OF_BIRTH`, `SSN`, `PASSPORT`, `TAX_NUMBER`, `INSURANCE_NUMBER`
4. **Financial (`financial`):** `IBAN`, `CREDIT_CARD`, `ACCOUNT_NUMBER`
5. **Credentials (`credentials`):** `PASSWORD`, `SECRET_KEY`
6. **Special Categories · GDPR Art. 9 (`special`):** `HEALTH_DATA`, `ETHNIC_ORIGIN`, `POLITICAL_OPINION`, `RELIGIOUS_BELIEF`, `SEXUAL_ORIENTATION`, `TRADE_UNION`, `SENSITIVE_CONTEXT`

For **every category**, choose one of **4 actions** (when multiple categories appear in one prompt, the strictest action wins: `refuse` > `local` > `placeholder` > `allow`):
- **`allow` (`Send as Typed -> Cloud`):** Sent unchanged to the external cloud model .
- **`placeholder` (`Pseudonymise -> <TOKEN_1>`):** Replaced with `<PERSON_1>`, `<EMAIL_1>`, etc. before cloud send and rehydrated locally in the answer.
- **`local` (`Stays Local -> Internal GPU`):** Entire request stays inside the perimeter on `BRANE Mega`'s internal GPU model (`X-Brane-Routed-To: local`).
- **`refuse` (`Refuse / Block -> HTTP 422`):** Request is stopped cold (`HTTP 422 policy_violation`) before any model runs; your agent must halt or escalate to a human reviewer.

### C. Create Custom Semantic Categories (`semanticCategories`)
Structured detectors catch names, emails and IBANs — they cannot catch **domain meaning** (such as indirect oncology/burnout notes without a named disease, unpublished tender bid ceilings, salary bands, or requests for autonomous applicant rejection under GDPR Art. 22 / EU AI Act Art. 14).

In Step 3 of `/team-policy` (or via `PUT /api/v1/policy`), add up to **25 Custom Semantic Categories**, each with:
- `code` & `name` (e.g. `INDIRECT_HEALTH_CONTEXT`, `TENDER_PRICING`, `AUTONOMOUS_REJECTION`)
- `description` (plain-language definition evaluated by the internal GPU LLM)
- `keywords` (optional fast deterministic trigger phrases)
- `legalBasis` (e.g. `GDPR Art. 9(1)`, `GDPR Art. 22 + EU AI Act Art. 14`)
- `action`: **`local`** (route to internal GPU model) or **`refuse`** (hard HTTP 422 block)

### D. Live Policy Test Bench + 1-Click CSV Export
In Step 4 of `/team-policy`, paste any synthetic prompt and click **Run Live Policy Check** to see:
- Every detected built-in category & matched semantic category,
- The exact outgoing payload external cloud models receive (with `<PERSON_1>` placeholders — or `[ZERO EXTERNAL EGRESS]`),
- All `X-Brane-*` headers,
- Plus **`Export Policy Matrix CSV`** at the top to download your configured rules directly in the `MAIN_Policy_Matrix_Template.csv` format!

---

## 2. Run in 60 Seconds from Terminal

```bash
export BRANE_BASE_URL="https://brane.ai-z.io/api/v1"
export BRANE_API_KEY="brn_live_<YOUR_TEAM_KEY>"
export TEAM_BUILD="Team-07 / policy-v1"

python3 starter-kit/brane_agent_starter.py
```

---

## 3. Response Headers Returned on `/api/v1/chat/completions`

| Header | Values & Meaning |
|--------|------------------|
| `X-Brane-Routed-To` | `cloud`, `local` (internal GPU model), or `refused` (HTTP 422 block) |
| `X-Brane-Action` | `allow`, `placeholder`, `local`, or `refuse` |
| `X-Brane-Redacted` | `true` when `<CATEGORY_1>` placeholders replaced sensitive spans before cloud egress |
| `X-Brane-Pii-Detected` | `true` / `false` |
| `X-Brane-Pii-Types` | Detected built-in categories (e.g. `PERSON,EMAIL,ORG,HEALTH_DATA`) |
| `X-Brane-Placeholder-Types` | Categories swapped for `<TOKEN_1>` on a cloud turn |
| `X-Brane-Allowed-Types` | Categories intentionally sent as typed (`allow`) on a cloud turn |
| `X-Brane-Semantic-Matches` | Custom semantic category codes triggered (e.g. `INDIRECT_HEALTH_CONTEXT`) |
| `X-Brane-Local-Cause` | Why a turn stayed local (`data_category_local`, `semantic_category_local`, `prompt_injection_local`, ...) |
| `X-Brane-Refused-By` | Rule that triggered an HTTP 422 refusal (`category:PASSWORD->refuse`, `semantic:AUTONOMOUS_REJECTION->refuse`) |

---

## 4. Submission Checklist (Saturday 21 Nov, 10:30 CET)

1. **Working AI Agent + Explicit Human Decision Handoff** (live 3-minute demo).
2. **`MAIN_Policy_Matrix_Template.csv`** — cite exact GDPR / EU AI Act / sector articles, map each category & semantic rule, and document honestly any product gap (`Partial` / `Not Yet`, e.g. if the same category `ORG` needs different rules in two sub-steps).
3. **`MAIN_Five_Tests_Template.csv` (`test_evidence_run.csv`)** — `T1–T5` passing + 5 handwritten grey-zone edge cases `E1–E5` from your workflow.
