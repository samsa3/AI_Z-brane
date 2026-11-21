"""Dry-runs every RAW sample (no local guard) against BRANE's /policy/test: shows what BRANE alone would do.
Usage: python brane_only_check.py"""
import json, re
import server
server.load_env()
S = json.load(open("samples.json", encoding="utf-8"))
SECRETS = ["Anna", "Kowalczyk", "03.05.1958", "448812", "5550 1234", "Teststraat", "Lukas", "Brenner", "Maria", "7781",
           "4444 7777", "Tom", "Vermeulen", "993104", "1212 3434", "Samira", "El-Haddad", "Jonas", "Keller", "Petra",
           "Lindqvist", "551177", "Marco", "Rossi"]
for s in S:
    _, _, r = server.brane("POST", "/policy/test", {"prompt": s["text"], "executeCompletion": False}, timeout=60)
    h = r.get("simulatedHeaders", {}); dec = r.get("decision", {})
    route = h.get("X-Brane-Routed-To", dec.get("route"))
    payload = r.get("outgoingCloudPayloadPreview", "") or ""
    cloud_leaks = [x for x in SECRETS if route == "cloud" and re.search(r"(?<![\w])" + re.escape(x) + r"(?![\w])", payload, re.I)]
    print(f"{s['label'][:44]:44} route={route:8} action={dec.get('winningAction'):11} http={dec.get('httpStatus')}"
          f" redacted={h.get('X-Brane-Redacted')} cloud_leaks={cloud_leaks or '-'}")
    print(f"     pii={h.get('X-Brane-Pii-Types', '-')} | semantic={h.get('X-Brane-Semantic-Matches', '-')}"
          f" | cause={h.get('X-Brane-Local-Cause', h.get('X-Brane-Refused-By', '-'))} | injection={r.get('promptInjection', {}).get('detected')}")
    if route == "cloud": print(f"     cloud payload: {payload[:220]}")
