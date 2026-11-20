"""Runs every sample through the running demo (local guard + BRANE) and prints route, BRANE headers and draft start."""
import json, urllib.request
S = json.load(open("samples.json", encoding="utf-8"))
for s in S:
    body = json.dumps({"text": s["text"], "scenario": s["scenario"]}).encode(); h = {}; r = None; dec = ""; draft = ""
    for line in urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8765/api/analyse", data=body,
                                       headers={"Content-Type": "application/json"}), timeout=200):
        ev = json.loads(line)
        if ev["type"] == "step":
            h = ev["data"].get("headers", h)
            if ev["n"] == 4: dec = ev["detail"]
        else: r = ev["route"]; draft = (ev.get("draft") or "")[:90].replace("\n", " ")
    who = "local guard + BRANE" if "enforced by our local guard" in dec else "BRANE alone"
    print(f"{s['label'][:44]:44} route={r:8} redacted={h.get('x-brane-redacted','-'):5} "
          f"semantic={h.get('x-brane-semantic-matches','-')[:48]:48} local_cause={h.get('x-brane-local-cause','-')} model={h.get('x-brane-model-resolved','-')}")
    print(f"     draft: {draft or '-'}")
