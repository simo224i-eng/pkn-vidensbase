"""Kontrol af pilotudtrækket: JSON-gyldighed, ordrette citater og udfald mod regel."""
import json, re, glob, os, collections
P = os.path.dirname(os.path.abspath(__file__))
src = {}
for f in sorted(glob.glob(f"{P}/batch_*.jsonl")):
    for line in open(f):
        r = json.loads(line); src[r["id"]] = r
norm = lambda s: re.sub(r"\s+", " ", s or "").strip().lower()
RX = re.compile(r"planklagenævnet\s+(stadfæster|ophæver|hjemviser|ændrer|afviser)")
rows, bad = [], []
for f in sorted(glob.glob(f"{P}/result_*.jsonl")):
    for i, line in enumerate(open(f)):
        try:
            rows.append(json.loads(line))
        except Exception as e:
            bad.append((os.path.basename(f), i + 1, str(e)[:60]))
print("rækker", len(rows), "ugyldige", len(bad), bad[:5])
ids = [r.get("id") for r in rows]
print("mangler", sorted(set(src) - set(ids))[:20], "dubletter", [k for k, v in collections.Counter(ids).items() if v > 1])
cit_ok = cit_bad = 0; uenig = []
for r in rows:
    s = src.get(r.get("id"))
    if not s: continue
    if norm(r.get("citat")) and norm(r.get("citat")) in norm(s["tekst"]): cit_ok += 1
    else: cit_bad += 1
    m = RX.search(norm(s["tekst"][:1600]))
    if m:
        regel = {"stadfæster": "stadfæstet", "afviser": "afvist"}.get(m.group(1), "medhold")
        agent = r.get("udfald")
        a = "stadfæstet" if agent == "stadfæstet" else "afvist" if agent == "afvist" else "medhold"
        if regel != a: uenig.append((r["id"], m.group(1), agent))
print("citater ordrette", cit_ok, "ikke fundet", cit_bad)
print("udfald uenig med regel", len(uenig), uenig[:10])
