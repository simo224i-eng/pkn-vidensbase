"""Tekstbehandling: HTML-oprensning, markdown→HTML, lækker læsevisning med
indholdsfortegnelse, citat-udtræk/-validering, notat-eksport.

1:1 porteret fra ejnar/shared.py — ren tekstlogik uden Streamlit-afhængighed,
så den kører identisk her og i Streamlit-appen. Hold de to i sync ved ændringer."""
from __future__ import annotations

import re

import pandas as pd

def strip_html(text: str, preserve_headings: bool = False) -> str:
    entities = {
        "&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">",
        "&oslash;": "ø", "&aelig;": "æ", "&aring;": "å",
        "&Oslash;": "Ø", "&AElig;": "Æ", "&Aring;": "Å",
        "&ndash;": "–", "&mdash;": "—", "&ldquo;": '"', "&rdquo;": '"',
        "&laquo;": "«", "&raquo;": "»", "&bull;": "•", "&hellip;": "…",
        "&sect;": "§", "&para;": "¶", "&copy;": "©", "&reg;": "®",
        "&#167;": "§",
    }
    if preserve_headings:
        # Preserve h2/h3 as structural markers before stripping all other tags
        text = re.sub(r'<h2[^>]*>(.*?)</h2>', lambda m: f'\n## {m.group(1).strip()}\n', text, flags=re.I | re.S)
        text = re.sub(r'<h3[^>]*>(.*?)</h3>', lambda m: f'\n### {m.group(1).strip()}\n', text, flags=re.I | re.S)
        text = re.sub(r'<h[456][^>]*>(.*?)</h[456]>', lambda m: f'\n#### {m.group(1).strip()}\n', text, flags=re.I | re.S)
        # Bold/strong standalone paragraph → treat as sub-heading
        text = re.sub(r'<p[^>]*>\s*<(?:strong|b)[^>]*>(.*?)</(?:strong|b)>\s*</p>',
                      lambda m: f'\n#### {m.group(1).strip()}\n', text, flags=re.I | re.S)
        # Preserve paragraph/line breaks as newlines
        text = re.sub(r'</p>|<br\s*/?>|</div>', '\n', text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    for ent, rep in entities.items():
        text = text.replace(ent, rep)
    text = re.sub(r"&#\d+;", " ", text)
    if preserve_headings:
        # Collapse spaces within lines but keep newlines
        lines = [re.sub(r'[ \t]+', ' ', ln).strip() for ln in text.splitlines()]
        # Remove consecutive blank lines
        out_lines: list[str] = []
        prev_blank = False
        for ln in lines:
            is_blank = ln == ""
            if is_blank and prev_blank:
                continue
            out_lines.append(ln)
            prev_blank = is_blank
        return '\n'.join(out_lines).strip()
    return re.sub(r"\s+", " ", text).strip()


def md_til_html(md: str) -> str:
    """Konvertér den markdown-undermængde Claude bruger (## overskrifter, **fed**,
    *kursiv*, lister, --- linjer) til HTML.

    Streamlit renderer IKKE markdown inde i rå HTML (fx <div class="chat-assistant">),
    så uden denne konvertering vises ##/**/--- råt. `[Kilde X]`-tokens bevares så
    erstat_kilde_refs() kan markere dem bagefter."""
    import html as _html
    if not md:
        return ""

    def _inline(t: str) -> str:
        t = _html.escape(t, quote=False)
        t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
        t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
        t = re.sub(r"__([^_]+)__", r"<strong>\1</strong>", t)
        t = re.sub(r"(?<![\*\w])\*([^*\n]+)\*(?![\*\w])", r"<em>\1</em>", t)
        return t

    lines = md.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    para: list[str] = []
    list_mode = None  # "ul" | "ol" | None

    def flush_para():
        if para:
            out.append(f"<p>{' '.join(para).strip()}</p>")
            para.clear()

    def close_list():
        nonlocal list_mode
        if list_mode:
            out.append(f"</{list_mode}>")
            list_mode = None

    for raw in lines:
        s = raw.strip()
        if not s:
            flush_para(); close_list(); continue
        if re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", s):
            flush_para(); close_list(); out.append("<hr>"); continue
        m = re.match(r"(#{1,4})\s+(.*)", s)
        if m:
            flush_para(); close_list()
            tag = {1: "h2", 2: "h2", 3: "h3", 4: "h4"}[len(m.group(1))]
            out.append(f"<{tag}>{_inline(m.group(2).strip())}</{tag}>")
            continue
        mb = re.match(r"[-*]\s+(.*)", s)
        if mb:
            flush_para()
            if list_mode != "ul":
                close_list(); out.append("<ul>"); list_mode = "ul"
            out.append(f"<li>{_inline(mb.group(1).strip())}</li>")
            continue
        mo = re.match(r"\d+[.)]\s+(.*)", s)
        if mo:
            flush_para()
            if list_mode != "ol":
                close_list(); out.append("<ol>"); list_mode = "ol"
            out.append(f"<li>{_inline(mo.group(1).strip())}</li>")
            continue
        if list_mode:
            close_list()
        para.append(_inline(s))
    flush_para(); close_list()
    return "".join(out)


def byg_notat_html(spørgsmål: str, svar_md: str, kilder: list) -> str:
    """Byg et selvstændigt, printvenligt HTML-notat af et AI-svar med kildeliste.

    Dependency-frit alternativ til PDF-generering: filen åbnes i browseren og
    skrives ud som PDF (Ctrl+P) med korrekt A4-opsætning. Al styling er inline
    i dokumentet, så filen kan deles som den er."""
    import html as _html
    import datetime as _d

    svar_html = md_til_html(svar_md)

    # [Kilde N] → [Sagsnr År] med diskret accent
    def _ref(m):
        dele = []
        for n in re.findall(r"\d+", m.group(1)):
            i = int(n) - 1
            if 0 <= i < len(kilder):
                k = kilder[i]
                sag = k.get("Sagsnummer") or f"Kilde {n}"
                try:
                    år = str(pd.Timestamp(k["Dato"]).year)
                except Exception:
                    år = ""
                dele.append(f'<span class="ref">[{sag} {år}]</span>'.replace(" ]", "]"))
        return " ".join(dele) if dele else m.group(0)

    svar_html = re.sub(r"\[Kilde\s+([\d,\s]+)\]", _ref, svar_html)

    kilde_rows = ""
    for i, k in enumerate(kilder):
        try:
            ds = pd.Timestamp(k["Dato"]).strftime("%d.%m.%Y")
        except Exception:
            ds = "–"
        kilde_rows += (
            f'<tr><td class="knum">{i+1}</td>'
            f'<td><div class="ktitel">{_html.escape(k.get("Titel") or "")}</div>'
            f'<div class="kmeta">{ds} &nbsp;·&nbsp; {_html.escape(k.get("Udfald") or "–")}'
            f' &nbsp;·&nbsp; {_html.escape(k.get("Selskab") or "–")}'
            f' &nbsp;·&nbsp; sag {_html.escape(k.get("Sagsnummer") or "–")}</div>'
            f'<div class="klink">{_html.escape(k.get("Link") or "")}</div></td></tr>'
        )

    dato = _d.date.today().strftime("%d.%m.%Y")
    return f"""<!DOCTYPE html>
<html lang="da"><head><meta charset="utf-8">
<title>Ejnar-notat · {dato}</title>
<style>
  @page {{ size: A4; margin: 22mm 20mm; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: Georgia, 'Times New Roman', serif; color: #1a2332; margin: 0;
          -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  .sheet {{ max-width: 720px; margin: 0 auto; padding: 40px 34px 60px; }}
  .head {{ display: flex; justify-content: space-between; align-items: baseline;
           border-bottom: 2.5px solid #1a2332; padding-bottom: 10px; margin-bottom: 6px; }}
  .brand {{ font-family: Inter, system-ui, sans-serif; font-weight: 800; font-size: 17px;
            letter-spacing: 3px; }}
  .brand span {{ color: #2563eb; }}
  .doctype {{ font-family: Inter, system-ui, sans-serif; font-size: 10.5px; color: #64748b;
              text-transform: uppercase; letter-spacing: 1.6px; }}
  .meta {{ font-family: Inter, system-ui, sans-serif; font-size: 11px; color: #64748b;
           margin-bottom: 26px; }}
  .sp-label {{ font-family: Inter, system-ui, sans-serif; font-size: 10px; font-weight: 700;
               text-transform: uppercase; letter-spacing: 1.4px; color: #2563eb; margin: 22px 0 6px; }}
  .spørgsmål {{ font-size: 15.5px; font-weight: 700; line-height: 1.5; margin: 0 0 4px; }}
  .svar {{ font-size: 13.5px; line-height: 1.75; }}
  .svar h2 {{ font-family: Inter, system-ui, sans-serif; font-size: 13px; margin: 1.5em 0 .5em;
              border-bottom: 1px solid #e2e8f0; padding-bottom: 4px; }}
  .svar h3 {{ font-family: Inter, system-ui, sans-serif; font-size: 12px; margin: 1.2em 0 .4em; }}
  .svar p {{ margin: 0 0 .8em; }}
  .svar ul, .svar ol {{ margin: .4em 0 .9em 1.4em; padding: 0; }}
  .svar li {{ margin-bottom: .25em; }}
  .svar hr {{ border: none; border-top: 1px solid #e2e8f0; margin: 1.2em 0; }}
  .ref {{ font-family: Inter, system-ui, sans-serif; font-size: 11px; font-weight: 600;
          color: #2563eb; white-space: nowrap; }}
  .kilder-h {{ font-family: Inter, system-ui, sans-serif; font-size: 10px; font-weight: 700;
               text-transform: uppercase; letter-spacing: 1.4px; color: #64748b;
               border-top: 1.5px solid #1a2332; padding-top: 12px; margin-top: 34px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
  td {{ vertical-align: top; padding: 7px 0; border-bottom: 1px solid #eef1f6; }}
  .knum {{ font-family: Inter, system-ui, sans-serif; font-weight: 700; font-size: 11px;
           color: #2563eb; width: 26px; }}
  .ktitel {{ font-size: 12px; font-weight: 700; line-height: 1.45; }}
  .kmeta {{ font-family: Inter, system-ui, sans-serif; font-size: 10.5px; color: #64748b; margin-top: 2px; }}
  .klink {{ font-family: Inter, system-ui, sans-serif; font-size: 9.5px; color: #94a3b8;
            word-break: break-all; margin-top: 2px; }}
  .foot {{ font-family: Inter, system-ui, sans-serif; font-size: 9.5px; color: #94a3b8;
           margin-top: 30px; border-top: 1px solid #eef1f6; padding-top: 10px; line-height: 1.6; }}
  .printhint {{ font-family: Inter, system-ui, sans-serif; background: #eff6ff; border: 1px solid #bfdbfe;
                color: #1d4ed8; font-size: 12px; border-radius: 8px; padding: 10px 14px; margin-bottom: 22px; }}
  @media print {{ .printhint {{ display: none; }} .sheet {{ padding: 0; max-width: none; }} }}
</style></head><body><div class="sheet">
  <div class="printhint">💡 Gem som PDF: tryk <b>Ctrl+P</b> (Mac: ⌘P) og vælg "Gem som PDF". Denne boks kommer ikke med i udskriften.</div>
  <div class="head"><div class="brand">EJNAR<span>.</span></div><div class="doctype">Praksisnotat</div></div>
  <div class="meta">Genereret {dato} · Ankenævnet for Forsikring — ejerskifteforsikring · {len(kilder)} kilder</div>
  <div class="sp-label">Spørgsmål</div>
  <div class="spørgsmål">{_html.escape(spørgsmål or "")}</div>
  <div class="sp-label">Vurdering på baggrund af praksis</div>
  <div class="svar">{svar_html}</div>
  <div class="kilder-h">Kilder ({len(kilder)})</div>
  <table>{kilde_rows}</table>
  <div class="foot">Notatet er genereret med AI på baggrund af de anførte kendelser og er ikke juridisk rådgivning.
  Citater bør efterprøves mod originalkendelserne før brug.</div>
</div></body></html>"""


def _flex_pattern(quote: str):
    """Byg et fleksibelt regex-mønster af et citat: matcher på tværs af
    tegnsætning/whitespace, så et parafraseret citat stadig kan findes i råteksten."""
    if not quote:
        return None
    words = re.findall(r"\w+", quote, re.UNICODE)
    if len(words) < 3:
        return None
    pat = r"[\W_]+".join(re.escape(w) for w in words[:60])
    try:
        return re.compile(pat, re.IGNORECASE)
    except re.error:
        return None


def citater_i_svar(svar: str, min_len: int = 20) -> list:
    """Returnér alle "..."-citater (inkl. » « og " ") i et AI-svar."""
    if not svar:
        return []
    out, seen = [], set()
    moenstre = [
        r'"([^"]{%d,})"' % min_len,
        r'»([^«]{%d,})«' % min_len,
        r'"([^"]{%d,})"' % min_len,
        r'„([^“]{%d,})“' % min_len,
    ]
    for mnstr in moenstre:
        for m in re.finditer(mnstr, svar):
            c = m.group(1).strip()
            if c and c not in seen:
                seen.add(c)
                out.append(c)
    return out


def citater_for_kilde(svar: str, doc: dict, min_len: int = 20) -> list:
    """Returnér de citater fra svaret der stammer fra netop denne kilde."""
    korpus = _normaliser_citat(doc.get("Tekst") or "")
    if not korpus:
        return []
    hits = []
    for c in citater_i_svar(svar, min_len):
        norm = _normaliser_citat(c)
        if not norm:
            continue
        head = norm[: max(30, int(len(norm) * 0.6))]
        if norm in korpus or head in korpus:
            hits.append(c)
    return hits


def _toc_label(t: str) -> str:
    t = (t or "").strip()
    return t if len(t) <= 46 else t[:44].rstrip() + "…"


_RD_P = ("margin:0 0 1.15em;font-size:15.5px;line-height:1.85;color:#1e293b;"
         "font-family:'Inter',system-ui,sans-serif;")


def byg_lækker_afgørelse(tekst: str, highlight_quotes=None, anchor_prefix: str = "sek"):
    """Returnér (toc_html, body_html) for en afgørelse.

    body_html har <div id="{prefix}-N"> ankre før hver overskrift, og TOC'en linker
    dertil (klik = hop til sektion). highlight_quotes markeres med <mark> i teksten."""
    HL_O, HL_C = "\x01", "\x02"
    raw = tekst or ""

    if highlight_quotes:
        spans = []
        for q in highlight_quotes:
            pat = _flex_pattern(q)
            if pat:
                m = pat.search(raw)
                if m:
                    spans.append((m.start(), m.end()))
        spans.sort(reverse=True)
        last_start = len(raw) + 1
        for s, e in spans:
            if e > last_start:          # spring overlappende spans over
                continue
            raw = raw[:s] + HL_O + raw[s:e] + HL_C + raw[e:]
            last_start = s

    has_markers = ('\n## ' in raw or '\n### ' in raw
                   or raw.startswith('## ') or raw.startswith('### '))
    toc: list = []
    body: list = []
    carry = {"open": False}
    counter = {"n": 0}

    def emit_para(text_block: str):
        text_block = text_block.strip()
        if not text_block:
            return
        text_block = re.sub(
            r'\[(\d{1,2})\]',
            r'<sup style="font-size:9px;font-weight:700;color:#2563eb;'
            r'vertical-align:super;">[\1]</sup>',
            text_block)
        sentences = re.split(r'(?<=[.!?]) +(?=[A-ZÆØÅ0-9])', text_block)
        buf, chunks = "", []
        for s in sentences:
            if not buf:
                buf = s
            elif len(buf) < 320:
                buf += " " + s
            else:
                chunks.append(buf); buf = s
        if buf:
            chunks.append(buf)
        for c in chunks:
            if carry["open"]:
                c = HL_O + c
            opens, closes = c.count(HL_O), c.count(HL_C)
            if opens > closes:
                c += HL_C; carry["open"] = True
            elif closes >= opens and carry["open"] and closes > 0:
                carry["open"] = False
            body.append(f'<p style="{_RD_P}">{c}</p>')

    if has_markers:
        para_lines: list = []

        def flush():
            if para_lines:
                emit_para(' '.join(para_lines)); para_lines.clear()

        for line in raw.splitlines():
            st_ = line.strip()
            if st_.startswith('## '):
                flush()
                counter["n"] += 1
                aid = f"{anchor_prefix}-{counter['n']}"
                title = st_[3:].strip().replace(HL_O, "").replace(HL_C, "")
                toc.append((2, title, aid))
                body.append(f'<div id="{aid}" class="rd-h2">{title}</div>')
            elif st_.startswith('### '):
                flush()
                counter["n"] += 1
                aid = f"{anchor_prefix}-{counter['n']}"
                title = st_[4:].strip().replace(HL_O, "").replace(HL_C, "")
                toc.append((3, title, aid))
                body.append(f'<div id="{aid}" class="rd-h3">{title}</div>')
            elif st_.startswith('#### '):
                flush()
                title = st_[5:].strip().replace(HL_O, "").replace(HL_C, "")
                body.append(f'<div class="rd-h4">{title}</div>')
            elif st_ == '':
                flush()
            else:
                para_lines.append(st_)
        flush()
    else:
        emit_para(raw)

    body_html = ''.join(body)
    body_html = (body_html.replace(HL_O, '<mark class="rd-cite">')
                          .replace(HL_C, '</mark>'))

    if toc:
        items = ''.join(
            f'<a href="#{aid}" class="rd-toc-link rd-toc-l{lvl}">{_toc_label(title)}</a>'
            for lvl, title, aid in toc
        )
        toc_html = f'<div class="rd-toc"><div class="rd-toc-h">Indhold</div>{items}</div>'
    else:
        toc_html = ""
    return toc_html, body_html


def udtræk_kerneafsnit(tekst: str, max_tegn: int = 8000) -> str:
    """Udtræk de vigtigste sektioner fra en afgørelse (klagen + vurdering/afgørelse).
    Springer 'Sagens oplysninger' og andre faktuelle sektioner over."""
    sektioner = re.split(r'\n(#{2,3} .+)', tekst)

    dele = []
    for i, del_ in enumerate(sektioner):
        if del_.startswith('## ') or del_.startswith('### '):
            indhold = sektioner[i + 1] if i + 1 < len(sektioner) else ""
            dele.append((del_.lstrip('#').strip().lower(), indhold.strip()))

    prioritet = [
        "klagen",
        "klagen vedrører",
        "planklagenævnets bemærkninger og afgørelse",
        "miljø- og fødevareklagenævnets afgørelse",
        "nævnets bemærkninger og afgørelse",
        "nævnets vurdering",
        "retlig vurdering",
        "begrundelse for afgørelsen",
        "begrundelse",
        "afgørelse",
        "nævnets bemærkninger",
        "afsluttende bemærkninger",
        "konklusion",
    ]

    udtræk = []
    brugt = 0
    for prio in prioritet:
        for heading, indhold in dele:
            if prio in heading and indhold:
                tekst_del = f"[{heading.upper()}]\n{indhold}"
                if brugt + len(tekst_del) <= max_tegn:
                    udtræk.append(tekst_del)
                    brugt += len(tekst_del)

    if udtræk:
        return "\n\n".join(udtræk)
    return tekst[-max_tegn:]


def byg_indeks_tekst(titel: str, tekst: str, max_tegn: int = 6000) -> str:
    """Byg søgetekst til TF-IDF-indekset:
    titel gentages 3x (boost), efterfulgt af kerneafsnit.
    Dette fokuserer scoring på det juridisk relevante – ikke 'sagens oplysninger'."""
    t = titel or ""
    kerne = udtræk_kerneafsnit(tekst or "", max_tegn=max_tegn)
    return f"{t} {t} {t} {kerne}"


def chunk_tekst(tekst: str, titel: str = "", chunk_size: int = 500, overlap: int = 80) -> list:
    """Del en afgørelsestekst i overlappende chunks à ~chunk_size tokens.
    Hvert chunk bærer titel-kontekst for bedre retrieval.
    Returnerer liste af chunk-strenge."""
    if not tekst:
        return [titel] if titel else []
    ord_liste = tekst.split()
    if len(ord_liste) <= chunk_size:
        return [f"{titel}\n{tekst}" if titel else tekst]
    chunks = []
    start = 0
    while start < len(ord_liste):
        end = min(start + chunk_size, len(ord_liste))
        chunk = " ".join(ord_liste[start:end])
        if titel:
            chunk = f"{titel}\n{chunk}"
        chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def _normaliser_citat(s: str) -> str:
    """Normaliser tekst til fuzzy citat-matching: lowercase, collapse whitespace,
    strip interpunktion i kanterne. Bevarer internal punctuation til substring-match."""
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"\s+", " ", s).strip()
    s = s.strip(".,;:!? \"'»«–—-")
    return s


def valider_citationer(svar: str, docs: list, min_laengde: int = 25) -> list:
    """Find citater i "..." i svaret og verificér at de findes i kildedokumenterne.
    Returnerer liste af suspekte citater (ikke fundet i nogen kilde).
    Kun citater på mindst min_laengde tegn valideres (korte strenge er ofte almindelige frasemer)."""
    if not svar or not docs:
        return []
    # Normalisér alle kildetekster én gang
    kilde_tekster = []
    for d in docs:
        tx = d.get("Tekst") or ""
        kilde_tekster.append(_normaliser_citat(tx))
    samlet_korpus = " ||| ".join(kilde_tekster)

    # Find alle "..." citater (inkl. danske citationstegn » « og " ")
    moenstre = [
        r'"([^"]{%d,})"' % min_laengde,
        r'»([^«]{%d,})«' % min_laengde,
        r'"([^"]{%d,})"' % min_laengde,
    ]
    suspekte = []
    sete = set()
    for mnstr in moenstre:
        for m in re.finditer(mnstr, svar):
            citat = m.group(1).strip()
            if len(citat) < min_laengde or citat in sete:
                continue
            sete.add(citat)
            norm = _normaliser_citat(citat)
            if not norm:
                continue
            # Fuzzy: substring-match på normaliseret kilde
            if norm in samlet_korpus:
                continue
            # Fallback: check om første 60% af citatet findes (håndterer mindre afvigelser)
            head = norm[: max(30, int(len(norm) * 0.6))]
            if head in samlet_korpus:
                continue
            suspekte.append(citat)
    return suspekte

