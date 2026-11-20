"""LarpAI demo server — local only (127.0.0.1), Python standard library.

    python server.py            ->  open http://127.0.0.1:8765

Flow per case (streamed to the browser step by step):
  1. receive document
  2. LOCAL guard, before BRANE: quarantine embedded instructions, detect Art. 9 / Art. 10 /
     Art. 22 signals and identifiers
  3. BRANE dry-run (POST /policy/test): what BRANE detects and what the TEAM policy would do
  4. legal floor: strictest of (team policy, our legal minimum) per finding;
     if the team policy is weaker, the local guard enforces the floor itself
  5. send through BRANE (POST /chat/completions) — never directly to any model provider
  6. draft + advice -> human approves / edits / rejects (POST /api/decision)
Any BRANE failure => stop, nothing is sent (fail-closed). The API key never reaches the browser.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from legal import ART9_LABELS, LEGAL_FLOOR, RANK, SCENARIOS, SIZE_NOTES, SYSTEM_PROMPT, age_from_dob, local_scan, name_variants

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
LOG = ROOT / "logs" / "audit.jsonl"
CLOUD_MODEL = "auto"
LOCAL_MODEL = "vllm:deepseek-v4.1-flash"
UA = "larpai-demo/0.2 (MAIN Summit 2026)"
# Brain: identifiers are LOCAL ONLY *and* excluded from any prompt -> always replaced before BRANE.
# Art. 9 labels (religion, origin, ...) are hidden too: they may never act as a triage feature; a specific
# treatment preference stays readable in the sentence ("... and does not accept blood transfusions").
IDENTIFIER_LABELS = {"PERSON", "EMAIL", "PHONE", "ADDRESS", "IP_ADDRESS", "DATE_OF_BIRTH", "SSN", "PASSPORT",
                     "TAX_NUMBER", "INSURANCE_NUMBER", "PATIENT_ID", "ACCOUNT_NUMBER",
                     "RELIGIOUS_BELIEF", "ETHNIC_ORIGIN", "POLITICAL_OPINION", "SEXUAL_ORIENTATION", "TRADE_UNION"}
ART9_HIDDEN = {"RELIGIOUS_BELIEF", "ETHNIC_ORIGIN", "POLITICAL_OPINION", "SEXUAL_ORIENTATION", "TRADE_UNION"}
LOG_RETENTION_DAYS = 30  # brain: logs local, minimised, with a documented retention period
PERSON_MIN_CONF = 0.9  # tuned on synthetic samples; see ignored-detections note in step 4
CASES: dict[str, dict] = {}  # in-memory, local only: case_id -> mapping for rehydration


def load_env() -> None:
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def audit(entry: dict) -> None:
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


class BraneDown(Exception):
    pass


def brane(method: str, path: str, body: dict | None = None, timeout: float = 30, simulate_down: bool = False):
    """Only network path to any model. Returns (status, headers, json). Raises BraneDown on failure."""
    base = os.environ.get("BRANE_BASE_URL", "").rstrip("/")
    if simulate_down:
        base = "http://127.0.0.1:9"  # nothing listens here -> connection refused
    if not base.startswith("http"):
        raise BraneDown("BRANE_BASE_URL not configured")
    req = urllib.request.Request(
        base + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {os.environ.get('BRANE_API_KEY', '')}",
                 "Content-Type": "application/json", "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            hdr = {k.lower(): v for k, v in r.headers.items() if k.lower().startswith("x-brane")}
            return r.status, hdr, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        hdr = {k.lower(): v for k, v in (e.headers or {}).items() if k.lower().startswith("x-brane")}
        raw = e.read()
        if e.code == 422:
            try:
                return 422, hdr, json.loads(raw)
            except Exception:
                return 422, hdr, {"error": raw[:300].decode(errors="replace")}
        raise BraneDown(f"BRANE answered HTTP {e.code}") from e
    except Exception as e:
        raise BraneDown(f"{type(e).__name__}: {e}") from e


def find_all(text: str, needle: str) -> list[tuple[int, int]]:
    out = []
    if not needle or len(needle) < 2:
        return out
    for m in re.finditer(r"(?<![\w])" + re.escape(needle) + r"(?![\w])", text, re.I):
        out.append((m.start(), m.end()))
    return out


NAME_WORD = r"[A-Z][a-zà-ÿ'\-]+"
NOT_NAMES = {"My", "Our", "The", "Dear", "Please", "Call", "Mr", "Ms", "Mrs", "Mx", "Dr", "Patient", "Doctor",
             "Nurse", "Hello", "Hi", "Thank", "Thanks", "Name", "His", "Her", "Regards", "Kind", "Contact", "Wife",
             "Husband", "Son", "Daughter", "Mother", "Father", "Resident", "Caller"}


def expand_person(text: str, sample: str) -> str:
    """BRANE sometimes flags only a first name ("Jonas"). Grow it to the full name found in the
    text ("Jonas Beispiel") so every variant (surname, "J. Beispiel", "Mr Beispiel") is protected."""
    sample = sample.strip()
    # [ \t]+ (not \s+): a name never continues on the next line ("Mira Fictus\nEmail: …")
    m = re.search(r"(?<![\w])(?:" + NAME_WORD + r"[ \t]+)?" + re.escape(sample) + r"(?:[ \t]+" + NAME_WORD + r"){0,2}", text)
    if not m:
        return sample
    words = [w for w in m.group().split() if w not in NOT_NAMES]
    return " ".join(words) or sample


def analyse(payload: dict, emit) -> None:
    text = payload.get("text", "")[:20000]
    scenario = SCENARIOS.get(payload.get("scenario"), SCENARIOS["er"])
    size = payload.get("size", "regional")
    down = bool(payload.get("simulateDown"))
    premask = True  # brain: identifiers never go into any prompt, so minimisation before BRANE is not optional
    case_id = "C-" + uuid.uuid4().hex[:6].upper()
    log = {"ts": now(), "case_id": case_id, "scenario": scenario["title"], "company_size": size,
           "input_sha256": hashlib.sha256(text.encode()).hexdigest(), "simulated_outage": down}

    def step(n, title, detail, status="done", data=None):
        emit({"type": "step", "n": n, "title": title, "detail": detail, "status": status, "data": data or {}})

    # 1 ── receive
    step(1, "Document received", f"Case {case_id}. {len(text)} characters, scenario: {scenario['title']}.")
    if not text.strip():
        step(1, "Nothing to analyse", "The document is empty.", "error")
        return

    # 2 ── local guard BEFORE BRANE
    scan = local_scan(text, staff_author=(scenario is SCENARIOS["protocol"]))
    spans = []  # for the masked view, positions in the ORIGINAL text
    for inj in scan["injections"]:
        spans.append({"start": inj["start"], "end": inj["end"], "label": "INSTRUCTION", "action": "quarantine",
                      "legal": "GDPR Art. 5(1)(f), 32", "source": "local"})
    parts = []
    if scan["injections"]:
        parts.append(f"{len(scan['injections'])} hidden instruction(s) quarantined; they will reach no model")
    for s in scan["signals"]:
        parts.append(f"{s['code'].replace('_', ' ').lower()} → {s['action']} ({s['legal']})")
        for h in s["hits"]:
            for a, b in find_all(text, h["text"]):
                spans.append({"start": a, "end": b, "label": s["code"], "action": s["action"],
                              "legal": s["legal"], "source": "local"})
    if scan["identifiers"]:
        parts.append(f"{len(scan['identifiers'])} direct identifier(s) found locally")
    step(2, "Local check before BRANE",
         ("; ".join(parts) + ".") if parts else "No hidden instructions or sensitive signals found locally.",
         "warn" if parts else "done")

    # 3 ── BRANE dry run
    step(3, "Asking BRANE what it sees", "Dry run against our team policy (no model call yet)…", "running")
    try:
        _, _, dry = brane("POST", "/policy/test", {"prompt": scan["clean_text"], "executeCompletion": False},
                          timeout=30, simulate_down=down)
    except BraneDown as e:
        step(3, "BRANE unreachable — stopped", f"{e}. Nothing was sent to any AI model (fail-closed). "
             "Please process this case manually.", "error")
        log |= {"route": "blocked", "reason": f"fail-closed: {e}", "sent_to_model": False}
        audit(log)
        emit({"type": "result", "case_id": case_id, "route": "blocked", "spans": spans, "text": text,
              "draft": None, "advice": [], "headers": {},
              "headline": "Stopped: protection check unavailable, nothing was sent."})
        return

    detected = dry.get("detectedCategories", [])
    labels = sorted({d["label"] for d in detected})
    step(3, "BRANE inspection", (f"BRANE detected {', '.join(labels)}." if labels else "BRANE detected no sensitive categories.")
         + f" Team policy decision: {dry.get('decision', {}).get('winningAction', '?')}"
         + f" → {dry.get('decision', {}).get('route', '?')}. Prompt-injection score "
         f"{dry.get('promptInjection', {}).get('score', 0):.2f}.", "done",
         {"detected": detected, "simulatedHeaders": dry.get("simulatedHeaders", {})})

    # 4 ── legal floor vs team policy
    person_context = scan["person_context"] or any(d["label"] == "PERSON" for d in detected)
    findings = []  # each: label, text, team, floor, final, legal, reason, enforced_by
    ignored = []
    for d in detected:
        # Over-masking guard: low-confidence PERSON hits (e.g. "Introduced Scrum", "Bachelor's") would
        # destroy task-relevant content. Shown to the reviewer instead of silently dropped.
        if d["label"] == "PERSON" and d.get("confidence", 1) < PERSON_MIN_CONF:
            ignored.append(f"{d.get('sampleText', '').strip()} ({d.get('confidence', 0):.2f})")
            continue
        floor, legal, reason = LEGAL_FLOOR.get(d["label"], ("placeholder", "GDPR Art. 5(1)(c)", "Not needed for the task."))
        if d["label"] in ART9_LABELS and not person_context:
            floor, legal, reason = ("allow", "GDPR Art. 4(1), Recital 26",
                                    "No identifiable patient: general clinical knowledge is not personal data.")
        team = d.get("action", "allow")
        final = floor if RANK[floor] >= RANK.get(team, 0) else team  # ties -> our legal floor wins
        if floor == "remove":
            final = "remove"  # deleted locally before the model call; BRANE's "refuse" stays as the safety net
        sample = d.get("sampleText", "").strip()
        if d["label"] == "PERSON":
            sample = expand_person(scan["clean_text"], sample)
        findings.append({"label": d["label"], "text": sample, "team": team, "floor": floor,
                         "final": final, "legal": legal, "reason": reason,
                         "enforced_by": "BRANE" if RANK[team] >= RANK[floor] else "local guard"})
    seen = {(f["label"], f["text"].lower()) for f in findings}
    for idf in scan["identifiers"]:  # false negatives of BRANE caught locally
        if (idf["label"], idf["text"].lower()) not in seen:
            floor, legal, reason = LEGAL_FLOOR[idf["label"]]
            findings.append({"label": idf["label"], "text": idf["text"], "team": "not detected", "floor": floor,
                             "final": floor, "legal": legal, "reason": reason, "enforced_by": "local guard"})
    for s in scan["signals"]:
        findings.append({"label": s["code"], "text": s["hits"][0]["match"], "team": "not configured", "floor": s["action"],
                         "final": s["action"], "legal": s["legal"], "reason": s["reason"], "enforced_by": "local guard"})

    for f in findings:
        if f["label"] in LEGAL_FLOOR or f["label"] in ("EMAIL", "PHONE", "IBAN"):
            variants = name_variants(f["text"]) if f["label"] == "PERSON" else [f["text"]]
            for v in variants:
                for a, b in find_all(text, v):
                    spans.append({"start": a, "end": b, "label": f["label"], "action": f["final"],
                                  "legal": f["legal"], "source": f["enforced_by"]})

    overall = max([f["final"] for f in findings] + ["allow"], key=lambda a: RANK[a])
    gaps = [f for f in findings if f["enforced_by"] == "local guard"]
    route_txt = {"allow": "cloud model, data as typed", "placeholder": "cloud model with placeholders",
                 "remove": "cloud model, irrelevant payment data removed",
                 "local": "internal GPU model only (no cloud egress)", "refuse": "no model — escalate to a human"}[overall]
    step(4, "Legal decision", f"Strictest rule wins → {route_txt}. "
         + (f"{len(gaps)} rule(s) enforced by our local guard because the BRANE team policy is weaker than our legal minimum."
            if gaps else "BRANE team policy already meets our legal minimum.")
         + (f" Ignored low-confidence name detections: {', '.join(ignored)}." if ignored else ""),
         "warn" if gaps else "done",
         {"findings": findings})

    advice = [{"label": f["label"], "action": f["final"], "legal": f["legal"], "reason": f["reason"],
               "enforced_by": f["enforced_by"]} for f in findings]
    advice_unique = list({(a["label"], a["action"]): a for a in advice}.values())
    notes = [scenario["note"], SIZE_NOTES.get(size, "")]

    log |= {"brane_detected": labels, "findings": [{k: f[k] for k in ("label", "team", "floor", "final", "enforced_by")}
                                                  for f in findings],
            "injections_quarantined": len(scan["injections"]), "decision": overall}

    if overall == "refuse":
        step(5, "Stopped before any model", "A rule requires a human decision (e.g. a request for an automated "
             "decision about a person, or credentials). No AI model was called.", "error")
        log |= {"route": "refused-local-guard", "sent_to_model": False}
        audit(log)
        emit({"type": "result", "case_id": case_id, "route": "refused", "spans": spans, "text": text, "draft": None,
              "advice": advice_unique, "notes": notes, "headers": {},
              "headline": "Escalated to a human: this request may not be automated."})
        return

    # 5 ── build outbound text: local masking only where BRANE policy is weaker than the floor
    outbound, mapping, counter, must_be_gone = scan["clean_text"], {}, {}, set()

    def sub(txt: str, needle: str, token: str) -> str:
        return re.sub(r"(?<![\w])" + re.escape(needle) + r"(?![\w])", token, txt, flags=re.I)

    # Verified 20 Nov: on CLOUD turns BRANE alone missed "J. Beispiel", "Mr Beispiel" and a bare first name.
    # So local minimisation is mandatory whenever the case goes to the cloud, whatever the toggle says.
    if overall in ("placeholder", "remove", "local"):
        # premask=True: minimise BEFORE BRANE (BRANE is itself an external service here). premask=False: only close
        # gaps where the BRANE team policy is weaker than our legal floor, and let BRANE produce the evidence.
        # Identifiers are minimised even when their category is routed LOCAL (e.g. a team policy that sets
        # DATE_OF_BIRTH=local): local routing protects against cloud egress, masking also protects inside BRANE.
        todo = [f for f in findings if f["text"] and (
                    (f["final"] in ("placeholder", "remove") and (premask or f["enforced_by"] == "local guard"))
                    or (premask and f["final"] == "local" and f["label"] in IDENTIFIER_LABELS))]
        # (a) non-name identifiers FIRST, so e-mails like anna.k@… are removed whole before names are touched
        for f in sorted(todo, key=lambda f: -len(f["text"])):
            if f["label"] == "PERSON":
                continue
            counter[f["label"]] = counter.get(f["label"], 0) + 1
            token = f"[{f['label']}_{counter[f['label']]}]"
            if f["final"] == "remove":
                token = "[removed: not needed for triage]"  # BLOCK from the prompt, case continues
            if f["label"] in ART9_HIDDEN:  # brain: do not record a religious / origin label, not even as a token name
                counter["REDACTED"] = counter.get("REDACTED", 0) + 1
                token = f"[REDACTED_{counter['REDACTED']}]"
            if f["label"] == "DATE_OF_BIRTH" and age_from_dob(f["text"]) is not None:
                token = f"[AGE_{counter[f['label']]}: {age_from_dob(f['text'])} years]"  # minimisation, not just masking
            mapping[token] = f["text"]
            must_be_gone.add(f["text"])
            outbound = sub(outbound, f["text"], token)
        # (b) names in passes, so relatives sharing a surname ("Lukas"/"Maria Brenner") are all covered:
        #     full name -> initial + surname -> title + surname -> bare surname -> bare first name
        names = sorted({f["text"] for f in todo if f["label"] == "PERSON"}, key=len, reverse=True)
        full: list[str] = []
        for n in names:
            if len(n.split()) >= 2 and n.lower() not in (x.lower() for x in full):
                full.append(n)
        singles = [n for n in names if len(n.split()) < 2
                   and not any(n.lower() in x.lower().split() for x in full)]
        # Given names and surnames get SEPARATE tokens. Relatives share the surname token, titles (Mr/Mrs) stay:
        # "Lukas Brenner" -> [FIRST_1] [LAST_1], "Maria Brenner" -> [FIRST_2] [LAST_1], "Mr Brenner" -> Mr [LAST_1].
        # So the model can still tell WHO takes the blood thinners, without seeing any name (clinical safety).
        last_tok: dict[str, str] = {}
        first_tok: dict[str, str] = {}
        known_last = {n.split()[-1].lower() for n in full}
        people = []  # (first_token or None, last_token or None, parts)
        for n in full + singles:
            parts = [p for p in n.split() if len(p.rstrip(".")) > 1]
            if not parts:
                continue
            if len(parts) == 1 and parts[0].lower() in known_last:
                continue  # bare surname already covered by a full name
            ln = parts[-1] if len(parts) >= 2 else None
            lt = None
            if ln:
                if ln.lower() not in last_tok:
                    counter["LAST"] = counter.get("LAST", 0) + 1
                    last_tok[ln.lower()] = f"[LAST_{counter['LAST']}]"
                    mapping[last_tok[ln.lower()]] = ln
                lt = last_tok[ln.lower()]
            given = parts[:-1] if ln else parts
            ft = None
            if given:
                key = " ".join(given).lower()
                if key not in first_tok:
                    counter["FIRST"] = counter.get("FIRST", 0) + 1
                    first_tok[key] = f"[FIRST_{counter['FIRST']}]"
                    mapping[first_tok[key]] = " ".join(given)
                ft = first_tok[key]
            people.append((ft, lt, given, ln))
            must_be_gone |= {p for p in parts if len(p) > 2}
        for ft, lt, given, ln in people:  # 1. full names, "Last, First"
            if ft and lt:
                outbound = sub(outbound, " ".join(given + [ln]), f"{ft} {lt}")
                outbound = sub(outbound, f"{ln}, {' '.join(given)}", f"{ft} {lt}")
        for ft, lt, given, ln in people:  # 2. "L. Brenner" -> only if the initial is unambiguous in that family
            if ft and lt:
                same = [g for _, l2, g, _ in people if l2 == lt and g and g[0][0] == given[0][0]]
                rep = f"{ft} {lt}" if len(same) == 1 else lt
                outbound = re.sub(r"(?<![\w])" + re.escape(given[0][0]) + r"\.\s?" + re.escape(ln) + r"(?![\w])", rep, outbound)
        for ft, lt, given, ln in people:  # 3. bare surname (titles like "Mr" stay in front)
            if lt:
                outbound = sub(outbound, ln, lt)
        for ft, lt, given, ln in people:  # 4. every given / middle name on its own
            for part in given:
                if len(part.rstrip(".")) > 1:
                    outbound = sub(outbound, part, ft)
    # egress self-check: every protected value AND every part of every protected name must be gone
    leftovers = [t for t in must_be_gone if re.search(r"(?<![\w])" + re.escape(t) + r"(?![\w])", outbound, re.I)]
    if leftovers:
        step(5, "Egress check failed — stopped", "Protected text was still present. Nothing was sent.", "error")
        log |= {"route": "blocked-egress-check", "sent_to_model": False}
        audit(log)
        emit({"type": "result", "case_id": case_id, "route": "blocked", "spans": spans, "text": text, "draft": None,
              "advice": advice_unique, "notes": notes, "headers": {}, "headline": "Stopped by egress check."})
        return

    # Only pin the local model ourselves if BRANE's own policy would NOT route local. Otherwise send "auto" so the
    # X-Brane-Local-Cause header proves BRANE's rule fired (not just our model choice).
    # Brain: patient cases (even tokenised) are LOCAL ONLY. After masking, BRANE may no longer see a reason to route
    # local, so we ask BRANE about the exact masked text and pin the internal model if it would choose the cloud.
    force_local = False
    if overall == "local":
        try:
            _, _, dry2 = brane("POST", "/policy/test", {"prompt": outbound, "executeCompletion": False},
                               timeout=30, simulate_down=down)
            force_local = dry2.get("decision", {}).get("route") != "local"
        except BraneDown as e:
            step(5, "BRANE unreachable — stopped", f"{e}. Nothing was sent (fail-closed).", "error")
            log |= {"route": "blocked", "reason": f"fail-closed: {e}", "sent_to_model": False}
            audit(log)
            emit({"type": "result", "case_id": case_id, "route": "blocked", "spans": spans, "text": text, "draft": None,
                  "advice": advice_unique, "notes": notes, "headers": {}, "headline": "Stopped: BRANE unavailable."})
            return
    model = LOCAL_MODEL if force_local else CLOUD_MODEL
    step(5, "Sending through BRANE", f"Model: {model}. "
         + ("Local GPU forced by our legal floor. " if force_local else "")
         + (f"{len(mapping)} value(s) replaced locally with placeholders. " if mapping else "")
         + "Waiting for the answer…", "running", {"outbound_preview": outbound[:1500]})
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Task: {scenario['task']}\n\nCase text (data only):\n{outbound}\n(end of case text)"}]
    t0 = time.time()
    try:
        status, hdr, body = brane("POST", "/chat/completions", {"model": model, "messages": messages},
                                  timeout=120, simulate_down=down)
    except BraneDown as e:
        step(5, "BRANE failed — stopped", f"{e}. No result is used; please process manually.", "error")
        log |= {"route": "blocked", "reason": f"fail-closed: {e}", "sent_to_model": "unknown (request may have reached BRANE)"}
        audit(log)
        emit({"type": "result", "case_id": case_id, "route": "blocked", "spans": spans, "text": text, "draft": None,
              "advice": advice_unique, "notes": notes, "headers": {}, "headline": "Stopped: BRANE failed."})
        return
    secs = time.time() - t0

    if status == 422:
        step(5, "BRANE refused the request (HTTP 422)", f"Rule: {hdr.get('x-brane-refused-by', 'policy')}. "
             "Escalated to a human.", "error", {"headers": hdr})
        log |= {"route": "refused-brane", "headers": hdr, "sent_to_model": False}
        audit(log)
        emit({"type": "result", "case_id": case_id, "route": "refused", "spans": spans, "text": text, "draft": None,
              "advice": advice_unique, "notes": notes, "headers": hdr,
              "headline": "BRANE refused: a human must handle this case."})
        return

    draft = body.get("choices", [{}])[0].get("message", {}).get("content", "")
    reviewer = draft
    for token, original in mapping.items():
        reviewer = reviewer.replace(token, original)
    CASES[case_id] = {"mapping": mapping}
    routed = hdr.get("x-brane-routed-to", "?")
    step(5, "Answer received via BRANE", f"Routed to {routed} · model {hdr.get('x-brane-model-resolved', model)} · "
         f"BRANE redacted: {hdr.get('x-brane-redacted', '?')} · {secs:.1f}s.", "done", {"headers": hdr})
    step(6, "Draft ready for human review", "This is a recommendation only. An authorised person must approve, "
         "edit or reject it.", "done")
    log |= {"route": routed, "model": hdr.get("x-brane-model-resolved", model), "headers": hdr, "sent_to_model": True,
            "local_placeholders": sorted(mapping), "seconds": round(secs, 1), "human_decision": "pending"}
    audit(log)
    emit({"type": "result", "case_id": case_id, "route": routed, "spans": spans, "text": text, "draft": reviewer,
          "advice": advice_unique, "notes": notes, "headers": hdr,
          "headline": f"Draft ready · processed on {'the internal GPU' if routed == 'local' else 'the cloud model'} · "
                      f"{sum(1 for a in advice_unique if a['action'] != 'allow')} protection rule(s) applied."})


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, code: int, obj) -> None:
        out = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            out = (STATIC / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)
        elif self.path == "/api/samples":
            self._json(200, json.loads((ROOT / "samples.json").read_text(encoding="utf-8")))
        elif self.path == "/api/policy":
            try:
                _, _, p = brane("GET", "/policy", timeout=15)
                self._json(200, {"ok": True, "summary": p.get("summary", {}), "sensitivity": p.get("piiSensitivity"),
                                 "mode": p.get("routingMode")})
            except BraneDown as e:
                self._json(200, {"ok": False, "error": str(e)})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if self.path == "/api/analyse":
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()

            def emit(ev):
                self.wfile.write((json.dumps(ev, ensure_ascii=False) + "\n").encode())
                self.wfile.flush()
            try:
                analyse(body, emit)
            except Exception as e:  # never leak details, never continue
                emit({"type": "step", "n": 9, "title": "Unexpected error — stopped", "detail": type(e).__name__,
                      "status": "error"})
        elif self.path == "/api/decision":
            entry = {"ts": now(), "case_id": body.get("case_id"), "human_decision": body.get("decision"),
                     "reviewer": body.get("reviewer", "demo reviewer"), "edited": bool(body.get("edited")),
                     # meaningful human review (GDPR Art. 22, CJEU C-634/21 SCHUFA): the nurse picks the category
                     # herself; we log the AI suggestion next to it so overrides are auditable
                     "final_category": body.get("final_category"), "ai_suggested": body.get("ai_suggested"),
                     "overrode_ai": (body.get("final_category") is not None and body.get("ai_suggested") is not None
                                     and body.get("final_category") != body.get("ai_suggested")),
                     "comment_len": len(body.get("comment", ""))}
            audit(entry)
            CASES.pop(body.get("case_id"), None)  # drop the re-identification key once decided
            self._json(200, {"ok": True})
        else:
            self._json(404, {"error": "not found"})


def prune_log(days: int = LOG_RETENTION_DAYS) -> None:
    """Drop audit lines older than the retention period (brain: logs minimised, documented retention)."""
    if not LOG.exists():
        return
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
    keep = []
    for line in LOG.read_text(encoding="utf-8").splitlines():
        try:
            if datetime.fromisoformat(json.loads(line)["ts"]).timestamp() >= cutoff:
                keep.append(line)
        except Exception:
            keep.append(line)
    LOG.write_text("".join(line + "\n" for line in keep), encoding="utf-8")


if __name__ == "__main__":
    load_env()
    prune_log()
    srv = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    print("LarpAI demo running on http://127.0.0.1:8765  (Ctrl+C to stop)")
    srv.serve_forever()
