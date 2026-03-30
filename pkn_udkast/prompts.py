"""
Prompt-motor til generering af PKN-afgørelsesafsnit.

Genererer to separate afsnit per klagepunkt:
1. "Klagen" – referat af klagers anbringender i PKN-stil
2. "Planklagenævnets vurdering" – nævnets juridiske vurdering

Hver genereres i et separat API-kald for bedre præcision.
"""

import requests
import pandas as pd

from data import strip_html


def _call_claude(api_key: str, model: str, blocks: list, max_tokens: int = 2500) -> str:
    """Kald Claude API med prompt caching."""
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    # Prompt caching kræver beta-header
    use_cache = any(
        isinstance(b, dict) and "cache_control" in b for b in blocks
    )
    if use_cache:
        headers["anthropic-beta"] = "prompt-caching-2024-07-31"

    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers=headers,
        json={
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": blocks}],
        },
        timeout=120,
    )
    if not r.ok:
        # Vis brugbar fejlbesked
        try:
            err = r.json().get("error", {}).get("message", r.text)
        except Exception:
            err = r.text
        raise RuntimeError(f"API-fejl ({r.status_code}): {err}")
    return r.json()["content"][0]["text"]


def _udtræk_klagen_vurdering(tekst_raw: str) -> str:
    """Udtræk kun Klagen + Planklagenævnets vurdering sektionerne fra en afgørelse.

    Returnerer de relevante sektioner i stedet for begyndelsen af teksten
    (som typisk bare er 'Sagens oplysninger' og er ubrugelig som præcedens).
    """
    import re as _re
    import html as _html

    heading_pattern = r'<h[234][^>]*>(.*?)</h[234]>'
    matches = list(_re.finditer(heading_pattern, tekst_raw, _re.IGNORECASE))

    if not matches:
        # Fallback: ingen headings fundet, returner ren tekst
        return strip_html(tekst_raw)

    relevante_sektioner = []
    for i, m in enumerate(matches):
        title = _html.unescape(_re.sub(r'<[^>]+>', '', m.group())).strip().lower()

        # Udtræk sektioner der er Klagen eller Planklagenævnets vurdering
        # "Klagen" men IKKE "Planklagenævnets" (som også indeholder "klagen")
        is_klage = (
            _re.search(r'\bklagen\b', title) is not None
            and 'planklagenævnet' not in title
            and 'kompetence' not in title
        )
        is_vurdering = 'planklagenævnets vurdering' in title

        is_emne_sektion = False  # Kun Klagen + Vurdering - ikke generelle afsnit

        if is_klage or is_vurdering or is_emne_sektion:
            start = m.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(tekst_raw)
            section = tekst_raw[start:end]
            clean = _html.unescape(_re.sub(r'<[^>]+>', ' ', section))
            clean = _re.sub(r'\s+', ' ', clean).strip()
            if len(clean) > 30:
                relevante_sektioner.append(clean)

    if relevante_sektioner:
        samlet = "\n\n".join(relevante_sektioner)
        return samlet
    else:
        # Fallback: returner ren tekst
        return strip_html(tekst_raw)


def _byg_præcedens_blok(præcedens: list) -> str:
    """Byg præcedenstekst fra relevante afgørelser.

    Udtrækker kun Klagen + Planklagenævnets vurdering sektionerne
    i stedet for begyndelsen af teksten.
    """
    blok = ""
    for i, p in enumerate(præcedens):
        try:
            dato = pd.Timestamp(p["Dato"]).strftime("%d.%m.%Y")
        except Exception:
            dato = "–"
        tekst_raw = p.get("Tekst", "")
        relevante = _udtræk_klagen_vurdering(tekst_raw)
        # Op til 6000 tegn per præcedens (nu er det rent Klagen+Vurdering, ikke filler)
        blok += (
            f"\n[Præcedens {i+1}] {dato} – {p['Titel']}\n"
            f"{relevante[:6000]}\n"
            "---\n"
        )
    return blok


def generer_klage_afsnit(
    api_key: str,
    model: str,
    emne: str,
    klage_rå: str,
    sags_kontekst: str,
    plan_type: str,
    præcedens: list,
) -> str:
    """Generer 'Klagen'-afsnittet for et klagepunkt."""

    præcedens_blok = _byg_præcedens_blok(præcedens)

    blocks = [
        {
            "type": "text",
            "text": (
                "Du er juridisk sagsbehandler i Planklagenævnet (PKN).\n\n"
                "Din opgave er at skrive afsnittet 'Klagen' for ét specifikt klagepunkt "
                "i en afgørelse om miljøvurdering (miljøvurderingsloven).\n\n"
                "REGLER:\n"
                "- Skriv i tredje person om klager: 'Klageren har anført…', 'Det fremgår af klagen, at…'\n"
                "- Referer klagers anbringender loyalt og præcist – tilføj INTET der ikke fremgår af klagers tekst\n"
                "- KORTFATTET: Kondenserér klagers tekst – afsnittet skal være KORTERE end den rå klage, ikke længere. "
                "PKN gengiver kun essensen af klagepunkterne, ikke alle detaljer og citater\n"
                "- Brug PKN's sproglige stil og formuleringer som de fremgår af præcedensafgørelserne\n"
                "- Brug 'anfører' og 'har anført' (ikke 'mener' eller 'synes')\n"
                "- Henvis kun til lovbestemmelser som klager faktisk nævner\n"
                "- Brug [VERIFICER: beskrivelse] for faktuelle oplysninger du er usikker på\n"
                "- Skriv KUN 'Klagen'-afsnittet – IKKE vurderingen\n"
                "- Output kun selve afsnitsteksten, ingen overskrift\n\n"
                f"PLANTYPE: {plan_type}\n\n"
                "PRÆCEDENSAFGØRELSER (brug disse som stilistisk vejledning for sprogtone og formuleringer):"
            ),
        },
        {
            "type": "text",
            "text": præcedens_blok,
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": (
                f"SAGSKONTEKST:\n{sags_kontekst}\n\n"
                f"KLAGEPUNKTETS EMNE: {emne}\n\n"
                f"KLAGERS ANBRINGENDER (rå tekst der skal konverteres til PKN-stil):\n{klage_rå}\n\n"
                "Skriv nu 'Klagen'-afsnittet:"
            ),
        },
    ]
    return _call_claude(api_key, model, blocks, max_tokens=2500)


def generer_vurdering_afsnit(
    api_key: str,
    model: str,
    emne: str,
    klage_udkast: str,
    kommunens_afgørelse: str,
    kommunens_bemærkninger: str,
    sags_kontekst: str,
    plan_type: str,
    præcedens: list,
    forventet_udfald: str = "Ikke fastlagt endnu",
    interne_noter: str = "",
) -> str:
    """Generer 'Planklagenævnets vurdering'-afsnittet for et klagepunkt."""

    præcedens_blok = _byg_præcedens_blok(præcedens)

    kommune_blok = ""
    if kommunens_afgørelse.strip():
        kommune_blok += f"\nKOMMUNENS AFGØRELSE / MILJØRAPPORTENS KONKLUSIONER:\n{kommunens_afgørelse}\n"
    if kommunens_bemærkninger.strip():
        kommune_blok += f"\nKOMMUNENS BEMÆRKNINGER TIL KLAGEPUNKTET:\n{kommunens_bemærkninger}\n"

    # Udfaldsinstruktion
    udfald_map = {
        "Ikke medhold": (
            "Vurderingen skal konkludere at Planklagenævnet IKKE kan give medhold i klagepunktet. "
            "Afslut med: 'Planklagenævnet kan på den baggrund ikke give medhold i klagepunktet.'"
        ),
        "Medhold": (
            "Vurderingen skal konkludere at Planklagenævnet giver medhold i klagepunktet. "
            "Afslut med: 'Planklagenævnet giver på den baggrund medhold i klagepunktet.'"
        ),
    }
    udfald_instruktion = udfald_map.get(forventet_udfald, udfald_map["Ikke medhold"])

    noter_blok = ""
    if interne_noter.strip():
        noter_blok = (
            f"\nSAGSBEHANDLERENS NOTER (interne instruktioner til vurderingen – følg disse):\n"
            f"{interne_noter}\n"
        )

    blocks = [
        {
            "type": "text",
            "text": (
                "Du er juridisk sagsbehandler i Planklagenævnet (PKN).\n\n"
                "Din opgave er at skrive afsnittet 'Planklagenævnets vurdering' for ét specifikt klagepunkt "
                "i en afgørelse om miljøvurdering (miljøvurderingsloven).\n\n"
                "VIGTIGT – HVAD DU IKKE SKAL SKRIVE:\n"
                "- Skriv IKKE 'Generelt om…'-afsnit (de generelle retsgrundlagsafsnit indsættes separat af sagsbehandleren)\n"
                "- Skriv IKKE en generel redegørelse for miljøvurderingsloven, dens formål eller systematik\n"
                "- Spring direkte til den KONKRETE vurdering af det specifikke klagepunkt\n\n"
                "STRUKTUR (følg denne nøje):\n"
                "1. Kort opsummering af klagers anbringende (1-2 sætninger, start med 'Klageren har anført, at…')\n"
                "2. Den konkrete vurdering – gå direkte til sagens fakta og nævnets stillingtagen\n"
                "3. Konklusion\n\n"
                "SPROGLIGE REGLER:\n"
                "- Brug ALTID 'Nævnet finder' eller 'Planklagenævnet finder' FØR 'lægger vægt på'. "
                "Korrekt: 'Planklagenævnet finder, at… Nævnet lægger i den forbindelse vægt på, at…'. "
                "FORKERT: 'Planklagenævnet lægger vægt på, at…' uden forudgående 'finder'\n"
                "- Brug 'Planklagenævnet bemærker' til indledende faktuelle konstateringer\n"
                "- Brug 'Nævnet finder' til juridiske vurderinger og konklusioner\n"
                "- Afslut med 'Planklagenævnet kan [ikke] give medhold i klagepunktet'\n"
                "- Brug [VERIFICER: beskrivelse] for faktuelle oplysninger du er usikker på\n"
                "- Skriv KUN vurderingsafsnittet – ingen overskrift\n\n"
                f"FORVENTET UDFALD: {udfald_instruktion}\n\n"
                f"PLANTYPE: {plan_type}\n\n"
                "PRÆCEDENSAFGØRELSER (brug disse som stilistisk vejledning for sprogtone – "
                "men skriv IKKE 'generelt om'-afsnit, kun den konkrete vurdering):"
            ),
        },
        {
            "type": "text",
            "text": præcedens_blok,
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": (
                f"SAGSKONTEKST:\n{sags_kontekst}\n\n"
                f"KLAGEPUNKTETS EMNE: {emne}\n\n"
                f"'KLAGEN'-AFSNITTET (allerede skrevet – brug dette som grundlag for vurderingen):\n{klage_udkast}\n\n"
                f"{kommune_blok}"
                f"{noter_blok}\n"
                "Skriv nu 'Planklagenævnets vurdering'-afsnittet.\n\n"
                "Når du er færdig med selve vurderingsafsnittet, skriv derefter:\n"
                "===NOTER===\n"
                "Og tilføj en kort intern note (3-8 punkter) med:\n"
                "- Hvilke præcedensafgørelser du primært har brugt og hvorfor\n"
                "- Hvilke konkrete formuleringer du har lånt fra præcedensafgørelserne\n"
                "- Kort ræsonnement for hvorfor du nåede det givne resultat\n"
                "- Eventuelle usikkerheder eller ting sagsbehandleren bør dobbelttjekke"
            ),
        },
    ]
    raw = _call_claude(api_key, model, blocks, max_tokens=3500)

    # Split vurdering og noter
    if "===NOTER===" in raw:
        vurdering, noter = raw.split("===NOTER===", 1)
        return vurdering.strip(), noter.strip()
    return raw.strip(), ""
