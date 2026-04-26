"""Scan alle PKN + MFKN afgørelser for referencer til vejledninger."""
import csv, zipfile, os, re, glob
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
csv.field_size_limit(10_000_000)

# ── Patterns ─────────────────────────────────────────────────────────────────
_VEJL_PATTERNS = [
    # "Vejledning om X" / "Vejledning til X"
    re.compile(r'[Vv]ejledning(?:en)?\s+(?:om|til|vedr(?:ørende)?\.?|angående)\s+([A-ZÆØÅa-zæøå§\-,\s]{5,80}?)(?:\.|,|\s*\()', re.UNICODE),
    # "Vejledning nr. XXXX"
    re.compile(r'[Vv]ejledning\s+nr\.?\s*(\d{1,5})\s+af\s+(\d{1,2}\.?\s*\w+\s*\d{4})', re.UNICODE),
    # "Naturstyrelsens/Miljøstyrelsens/Plan- og Landdistriktsstyrelsens vejledning"
    re.compile(r'((?:Natur|Miljø|Kyst|Plan-?\s*og\s*Landdistrikts|Erhvervs|Energi)styrelsens?\s+vejledning(?:\s+om\s+[A-ZÆØÅa-zæøå§\-,\s]{3,60})?)', re.UNICODE),
    # Named vejledninger
    re.compile(r'(Planlægningsvejledningen|Landzoneadministrationsvejledningen|Håndbog\s+om\s+[A-ZÆØÅa-zæøå\-\s]{3,50})', re.UNICODE),
    # "jf. vejledning" / "ifølge vejledningen"
    re.compile(r'(?:jf\.|ifølge|henvist\s+til|henviser\s+til)\s+(?:den\s+)?([A-ZÆØÅ][a-zæøå]+(?:styrelsens?|s)\s+vejledning(?:\s+om\s+[A-ZÆØÅa-zæøå§\-,\s]{3,60})?)', re.UNICODE),
    # "Vejl. om X" (abbreviated)
    re.compile(r'[Vv]ejl\.\s+(?:om|til)\s+([A-ZÆØÅa-zæøå§\-,\s]{5,60}?)(?:\.|,|\s*\()', re.UNICODE),
]

# Skip bekendtgørelser, love, domme
_SKIP = re.compile(r'bekendtgørelse|forordning|direktiv|dom\s|afgørelse\s|lov(?:en|givning)', re.IGNORECASE)


def _normalize(ref: str) -> str:
    ref = ref.strip().rstrip(".,;:")
    ref = re.sub(r'\s+', ' ', ref)
    if ref and ref[0].islower():
        ref = ref[0].upper() + ref[1:]
    return ref


def _load_csvs(pattern):
    """Load all CSV files matching glob pattern from zip archives."""
    rows = []
    seen_links = set()
    for zf in sorted(glob.glob(os.path.join(ROOT, pattern))):
        try:
            with zipfile.ZipFile(zf) as z:
                inner = [n for n in z.namelist() if n.endswith('.csv')][0]
                with z.open(inner) as f:
                    import io
                    reader = csv.DictReader(io.TextIOWrapper(f, encoding='utf-8'))
                    for r in reader:
                        link = r.get("Link", "")
                        if link in seen_links:
                            continue
                        seen_links.add(link)
                        rows.append(r)
        except Exception as e:
            print(f"  Fejl ved {zf}: {e}")
    return rows


def _extract_refs(tekst: str) -> list[str]:
    """Extract vejledning references from decision text."""
    refs = []
    for pat in _VEJL_PATTERNS:
        for m in pat.finditer(tekst):
            full = m.group(0) if m.lastindex is None else m.group(0)
            # For numbered vejledninger, use full match
            raw = m.group(0)
            if m.lastindex and m.lastindex >= 1:
                raw = m.group(1)
                if m.lastindex >= 2:
                    raw = f"Vejledning nr. {m.group(1)} af {m.group(2)}"
            normalized = _normalize(raw)
            if _SKIP.search(normalized):
                continue
            if len(normalized) < 8:
                continue
            refs.append(normalized)
    return refs


def _get_context(tekst: str, ref: str, window: int = 100) -> str:
    """Get surrounding context for a reference."""
    idx = tekst.lower().find(ref.lower()[:20])
    if idx == -1:
        return ""
    start = max(0, idx - window)
    end = min(len(tekst), idx + len(ref) + window)
    ctx = tekst[start:end].replace("\n", " ").strip()
    return f"…{ctx}…" if start > 0 else f"{ctx}…"


def main():
    print("=" * 60)
    print("SCAN: Vejlednings-referencer i PKN + MFKN afgørelser")
    print("=" * 60)

    all_refs = Counter()
    ref_retsomraade = defaultdict(set)
    ref_kilde = defaultdict(set)
    ref_context = {}

    # ── PKN ──
    print("\nIndlæser PKN...")
    pkn_rows = _load_csvs("pkn_*.csv.zip")
    print(f"  {len(pkn_rows)} afgørelser")

    for i, row in enumerate(pkn_rows):
        tekst = row.get("Tekst", "")
        retsomraade = row.get("Retsomraade", row.get("Retsområde", "PKN"))
        refs = _extract_refs(tekst)
        for ref in refs:
            all_refs[ref] += 1
            ref_retsomraade[ref].add(retsomraade)
            ref_kilde[ref].add("pkn")
            if ref not in ref_context:
                ctx = _get_context(tekst, ref)
                if ctx:
                    ref_context[ref] = ctx[:200]
        if (i + 1) % 2000 == 0:
            print(f"  PKN: {i+1}/{len(pkn_rows)} skannet...")

    print(f"  PKN færdig. {sum(1 for r in ref_kilde if 'pkn' in ref_kilde[r])} unikke vejledninger fundet.")

    # ── MFKN ──
    print("\nIndlæser MFKN...")
    mfkn_rows = _load_csvs("mfkn_*.csv.zip")
    print(f"  {len(mfkn_rows)} afgørelser")

    for i, row in enumerate(mfkn_rows):
        tekst = row.get("Tekst", "")
        retsomraade = row.get("Retsomraade", row.get("Retsområde", "MFKN"))
        refs = _extract_refs(tekst)
        for ref in refs:
            all_refs[ref] += 1
            ref_retsomraade[ref].add(retsomraade)
            ref_kilde[ref].add("mfkn")
            if ref not in ref_context:
                ctx = _get_context(tekst, ref)
                if ctx:
                    ref_context[ref] = ctx[:200]
        if (i + 1) % 5000 == 0:
            print(f"  MFKN: {i+1}/{len(mfkn_rows)} skannet...")

    print(f"  MFKN færdig. {sum(1 for r in ref_kilde if 'mfkn' in ref_kilde[r])} unikke vejledninger fundet.")

    # ── Output ──
    print(f"\n{'=' * 60}")
    print(f"TOTAL: {len(all_refs)} unikke vejlednings-referencer fundet")
    print(f"{'=' * 60}")

    out_path = os.path.join(ROOT, "vejledning_references.csv")
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["vejledning_ref", "count", "retsomraade", "kilde", "example_context"])
        for ref, count in all_refs.most_common():
            kilde = " + ".join(sorted(ref_kilde[ref]))
            ro = " | ".join(sorted(ref_retsomraade[ref]))
            ctx = ref_context.get(ref, "")
            writer.writerow([ref, count, ro, kilde, ctx])

    print(f"\nGemt til: {out_path}")

    print(f"\n{'─' * 60}")
    print("TOP 40 MEST-CITEREDE VEJLEDNINGER:")
    print(f"{'─' * 60}")
    for i, (ref, count) in enumerate(all_refs.most_common(40)):
        kilde = " + ".join(sorted(ref_kilde[ref]))
        ro = " | ".join(sorted(list(ref_retsomraade[ref])[:3]))
        print(f"  {i+1:3d}. [{count:5d}x] ({kilde:10s}) {ref[:70]}")
        if ro:
            print(f"       Retsområder: {ro[:80]}")


if __name__ == "__main__":
    main()
