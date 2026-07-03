"""Klassificér AKF-kendelser (udfald + mangeltyper) med Claude — batch-engangsjob.

Appen bruger i dag keyword-heuristik til Udfald/Mangeltype, hvilket gør
statistik-fanen "cirka". Dette script laver en autoritativ LLM-klassifikation
og skriver resultatet tilbage i CSV'ens kolonner, så både statistik og filtre
bliver troværdige. Kør det én gang (og igen efter nye scrapes).

Brug:
    export ANTHROPIC_API_KEY=sk-ant-...
    python3 klassificer_kendelser.py --dry-run          # se hvad der ville ske
    python3 klassificer_kendelser.py --limit 25         # lille testkørsel
    python3 klassificer_kendelser.py                    # fuld kørsel (kun uklassificerede)
    python3 klassificer_kendelser.py --alle             # omklassificér ALT

Derefter: commit den opdaterede CSV (zippes igen hvis den lå som .zip):
    cd ejnar && zip ejnar_ejerskifteforsikring.csv.zip ejnar_ejerskifteforsikring.csv
    git add ejnar_ejerskifteforsikring.csv.zip && git commit -m "Ejnar: LLM-klassificerede udfald"

Omkostning: ~0,1–0,3 øre pr. kendelse med Haiku (kun kerneafsnit sendes).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import zipfile

import requests

HER = os.path.dirname(os.path.abspath(__file__))
CSV_NAVN = "ejnar_ejerskifteforsikring.csv"
MODEL = "claude-haiku-4-5-20251001"
API_URL = "https://api.anthropic.com/v1/messages"

UDFALD_VALG = ["Medhold", "Delvis medhold", "Ikke medhold", "Afvist", "Ukendt"]
MANGELTYPE_VALG = [
    "Skimmel/fugt", "Tag/tagdækning", "Kloak/dræn", "Installationer",
    "Fundament", "Vinduer/døre", "Murværk/facade", "Råd/svamp/insekt",
    "Konstruktion/bærende", "Badeværelse/vådrum", "Gulv", "Andet",
]

PROMPT = """Du klassificerer en kendelse fra Ankenævnet for Forsikring om ejerskifteforsikring.

Svar KUN med gyldig JSON på formen:
{{"udfald": "...", "mangeltyper": ["...", "..."]}}

REGLER:
- "udfald" er set fra KLAGEREN (forbrugeren): vælg præcis én af {udfald}.
  · "Medhold" = klageren får fuldt/i det væsentlige medhold (selskabet skal dække/betale).
  · "Delvis medhold" = klageren får delvist medhold.
  · "Ikke medhold" = selskabet frifindes / klagerens påstand tages ikke til følge.
  · "Afvist" = klagen afvises/behandles ikke i realiteten.
  · "Ukendt" kun hvis teksten reelt ikke afslører udfaldet.
- "mangeltyper": 1-3 værdier fra {mangel}. Vælg dem sagen faktisk handler om.

KENDELSE (uddrag):
TITEL: {titel}
TEKST: {tekst}

JSON:"""


def find_csv() -> str:
    """Returnér sti til CSV — udpak fra .zip hvis nødvendigt."""
    sti = os.path.join(HER, CSV_NAVN)
    if os.path.exists(sti):
        return sti
    zsti = sti + ".zip"
    if os.path.exists(zsti):
        with zipfile.ZipFile(zsti) as z:
            for m in z.namelist():
                if m.endswith(".csv"):
                    print(f"Udpakker {m} fra {os.path.basename(zsti)} …")
                    z.extract(m, HER)
                    udpakket = os.path.join(HER, m)
                    if udpakket != sti:
                        os.replace(udpakket, sti)
                    return sti
    sys.exit(f"FEJL: hverken {CSV_NAVN} eller {CSV_NAVN}.zip fundet i {HER}")


def kerneuddrag(tekst: str, max_tegn: int = 5500) -> str:
    """Send kun det afgørende: start (klagen) + slutning (nævnets afgørelse)."""
    tekst = re.sub(r"<[^>]+>", " ", tekst or "")
    tekst = re.sub(r"\s+", " ", tekst).strip()
    if len(tekst) <= max_tegn:
        return tekst
    hoved = tekst[: max_tegn // 3]
    hale = tekst[-(max_tegn - len(hoved)):]
    return hoved + " […] " + hale


def klassificer(api_key: str, titel: str, tekst: str) -> dict | None:
    body = {
        "model": MODEL,
        "max_tokens": 200,
        "messages": [{"role": "user", "content": PROMPT.format(
            udfald=UDFALD_VALG, mangel=MANGELTYPE_VALG,
            titel=(titel or "")[:200], tekst=kerneuddrag(tekst),
        )}],
    }
    headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01",
               "Content-Type": "application/json"}
    for forsøg in range(4):
        try:
            r = requests.post(API_URL, headers=headers, json=body, timeout=60)
            if r.status_code in (429, 529) or r.status_code >= 500:
                time.sleep(2 ** forsøg * 2)
                continue
            r.raise_for_status()
            svar = r.json()["content"][0]["text"]
            m = re.search(r"\{.*\}", svar, re.S)
            if not m:
                return None
            data = json.loads(m.group(0))
            udfald = data.get("udfald", "")
            mt = [x for x in (data.get("mangeltyper") or []) if x in MANGELTYPE_VALG]
            if udfald not in UDFALD_VALG:
                return None
            return {"udfald": udfald, "mangeltyper": mt[:3] or ["Andet"]}
        except (requests.RequestException, json.JSONDecodeError, KeyError):
            time.sleep(2 ** forsøg)
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--limit", type=int, default=0, help="max antal rækker (0 = alle)")
    ap.add_argument("--alle", action="store_true",
                    help="omklassificér også rækker der allerede har udfald")
    ap.add_argument("--dry-run", action="store_true",
                    help="vis kun hvad der ville blive klassificeret")
    args = ap.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key and not args.dry_run:
        sys.exit("FEJL: sæt ANTHROPIC_API_KEY i miljøet (eller kør --dry-run).")

    sti = find_csv()
    csv.field_size_limit(10_000_000)
    with open(sti, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        felter = list(reader.fieldnames or [])
        rækker = list(reader)
    for kol in ("Udfald", "Mangeltype"):
        if kol not in felter:
            felter.append(kol)

    mangler = [r for r in rækker
               if args.alle or (r.get("Udfald") or "").strip() in ("", "Ukendt")]
    if args.limit:
        mangler = mangler[: args.limit]

    print(f"{len(rækker)} kendelser i alt · {len(mangler)} skal klassificeres "
          f"({'alle' if args.alle else 'kun tomme/Ukendt'})")
    if args.dry_run:
        for r in mangler[:10]:
            print("  ·", (r.get("Titel") or "")[:90])
        if len(mangler) > 10:
            print(f"  … og {len(mangler) - 10} flere")
        return
    if not mangler:
        print("Intet at gøre — alle rækker er klassificeret. Brug --alle for at omklassificere.")
        return

    ok = fejl = 0
    t0 = time.time()
    for i, r in enumerate(mangler, 1):
        res = klassificer(api_key, r.get("Titel", ""), r.get("Tekst", ""))
        if res:
            r["Udfald"] = res["udfald"]
            r["Mangeltype"] = ", ".join(res["mangeltyper"])
            ok += 1
        else:
            fejl += 1
        if i % 10 == 0 or i == len(mangler):
            fart = i / max(time.time() - t0, 1)
            eta = (len(mangler) - i) / max(fart, 0.01)
            print(f"  {i}/{len(mangler)} · ok={ok} fejl={fejl} · ~{eta/60:.0f} min tilbage")
            # gem løbende, så en afbrudt kørsel ikke mister arbejde
            with open(sti, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=felter)
                w.writeheader()
                w.writerows(rækker)

    print(f"\nFærdig: {ok} klassificeret, {fejl} fejlede. Skrevet til {sti}")
    print("Husk at zippe og committe CSV'en (se docstring øverst).")


if __name__ == "__main__":
    main()
