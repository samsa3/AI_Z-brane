"""Runs every sample in samples.json through the running server and checks the outbound text for leaks.
Usage: python check_samples.py   (server must be running on 127.0.0.1:8765)"""
import json, re, time, urllib.request
S = json.load(open("samples.json", encoding="utf-8"))
SECRETS = ["Anna", "Kowalczyk", "03.05.1958", "448812", "5550 1234", "Teststraat", "Lukas", "Brenner", "Maria", "7781",
           "4444 7777", "Tom", "Vermeulen", "993104", "1212 3434", "Samira", "El-Haddad", "Jonas", "Keller", "Petra",
           "Lindqvist", "551177", "Marco", "Rossi"]
time.sleep(1)
for s in S:
    body = json.dumps({"text": s["text"], "scenario": s["scenario"]}).encode(); o = r = None; dec = ""
    for line in urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8765/api/analyse", data=body,
                                       headers={"Content-Type": "application/json"}), timeout=200):
        ev = json.loads(line)
        if ev["type"] == "step":
            o = ev["data"].get("outbound_preview", o)
            if ev["n"] == 4: dec = ev["detail"][:110]
        else: r = ev["route"]
    leaks = [x for x in SECRETS if o and re.search(r"(?<![\w])" + re.escape(x) + r"(?![\w])", o, re.I)]
    print(f"{s['label'][:44]:44} route={r:8} sent={'yes' if o else 'NO':3} leaks={leaks or '-'}")
    print(f"     decision: {dec}")
    if o: print(f"     outbound: {o[:300].replace(chr(10), ' | ')}")
