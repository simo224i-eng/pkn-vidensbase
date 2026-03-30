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


def _byg_præcedens_blok(præcedens: list) -> str:
    """Byg præcedenstekst fra relevante afgørelser."""
    blok = ""
    for i, p in enumerate(præcedens):
        try:
            dato = pd.Timestamp(p["Dato"]).strftime("%d.%m.%Y")
        except Exception:
            dato = "–"
        tekst = strip_html(p.get("Tekst", ""))
        # Brug op til 4000 tegn per præcedens for at give tilstrækkelig kontekst
        blok += (
            f"\n[Præcedens {i+1}] {dato} – {p['Titel']}\n"
            f"{tekst[:4000]}\n"
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
                "- Brug PKN's sproglige stil og formuleringer som de fremgår af præcedensafgørelserne\n"
                "- Brug 'anfører' og 'har anført' (ikke 'mener' eller 'synes')\n"
                "- Henvis til konkrete lovbestemmelser hvis klager gør det\n"
                "- Strukturer teksten i logiske afsnit\n"
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
                "REGLER:\n"
                "- Skriv som Planklagenævnet: 'Planklagenævnet bemærker…', 'Nævnet finder…', 'Planklagenævnet lægger vægt på…'\n"
                "- Start typisk med at opsummere hvad klageren har anført (1-2 sætninger)\n"
                "- Redegør derefter for det relevante retsgrundlag (brug standardformuleringer fra præcedensafgørelserne)\n"
                "- Foretag den konkrete vurdering baseret på sagens oplysninger\n"
                "- Afslut med en klar konklusion\n"
                "- Brug PKN's sproglige stil og juridiske formuleringer som de fremgår af præcedensafgørelserne\n"
                "- Henvis til konkrete lovbestemmelser (miljøvurderingsloven, planloven etc.)\n"
                "- Brug [VERIFICER: beskrivelse] for faktuelle oplysninger du er usikker på\n"
                "- Skriv KUN vurderingsafsnittet – ingen overskrift\n"
                "- Vær juridisk præcis – brug de EKSAKTE standardformuleringer fra præcedensafgørelserne\n\n"
                f"FORVENTET UDFALD: {udfald_instruktion}\n\n"
                f"PLANTYPE: {plan_type}\n\n"
                "PRÆCEDENSAFGØRELSER (brug disse som stilistisk og juridisk vejledning – "
                "kopier de standardformuleringer om retsgrundlaget som nævnet typisk anvender):"
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
                "Skriv nu 'Planklagenævnets vurdering'-afsnittet:"
            ),
        },
    ]
    return _call_claude(api_key, model, blocks, max_tokens=3000)
