"""Apply / verify / restore the BRANE team policy from a JSON file (policy as code).

    python policy_sync.py apply   policy/triage_policy.json
    python policy_sync.py verify  policy/triage_policy.json
    python policy_sync.py restore policy/backup_before_triage_policy.json
"""
import json
import sys

import server

server.load_env()


def payload(path: str) -> dict:
    p = json.load(open(path, encoding="utf-8"))
    return {k: p[k] for k in ("routingMode", "piiSensitivity", "categories", "semanticCategories") if k in p}


def verify(path: str) -> bool:
    want = payload(path)
    _, _, have = server.brane("GET", "/policy")
    ok = True
    for k in ("routingMode", "piiSensitivity"):
        if want.get(k) != have.get(k):
            print(f"  MISMATCH {k}: want {want.get(k)} have {have.get(k)}"); ok = False
    for cat, act in want.get("categories", {}).items():
        if have.get("categories", {}).get(cat) != act:
            print(f"  MISMATCH {cat}: want {act} have {have['categories'].get(cat)}"); ok = False
    want_sem = {s["code"]: s["action"] for s in want.get("semanticCategories", [])}
    have_sem = {s.get("code"): s.get("action") for s in have.get("semanticCategories", [])}
    if want_sem != have_sem:
        print(f"  MISMATCH semantic: want {want_sem} have {have_sem}"); ok = False
    print(f"{'OK' if ok else 'DIFFERENT'} · {have.get('team')} · updated {have.get('updatedAt')} · {have.get('summary')}")
    return ok


if __name__ == "__main__":
    cmd, path = sys.argv[1], sys.argv[2]
    if cmd in ("apply", "restore"):
        status, _, resp = server.brane("PUT", "/policy", payload(path))
        print(f"PUT /policy -> HTTP {status} · summary {resp.get('summary')}")
    sys.exit(0 if verify(path) else 1)
