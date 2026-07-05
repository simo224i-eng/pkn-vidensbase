"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getKendelse, ApiError } from "@/lib/api";
import { findMappeForLink, gemAfgørelse, fjernAfgørelse, hentAlleMapper, opretMappe } from "@/lib/sagsmapper";
import type { KendelseDetalje } from "@/lib/types";

const BADGE: Record<string, string> = {
  Medhold: "bg-ok-bg text-ok border-green-200",
  "Delvis medhold": "bg-cyan-50 text-cyan-700 border-cyan-200",
  "Ikke medhold": "bg-bad-bg text-bad border-red-200",
  Afvist: "bg-warn-bg text-warn border-amber-200",
};
const BADGE_DEFAULT = "bg-surface text-ink-3 border-line";

function formatDate(iso: string | null) {
  if (!iso) return "–";
  const [y, m, d] = iso.split("-");
  return `${d}.${m}.${y}`;
}

export default function KendelseDetaljePage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [data, setData] = useState<KendelseDetalje | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [gemtIMappe, setGemtIMappe] = useState<string | null>(null);
  const [kopieret, setKopieret] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getKendelse(params.id)
      .then((d) => {
        if (cancelled) return;
        setData(d);
        setGemtIMappe(findMappeForLink(d.link));
      })
      .catch((e) => !cancelled && setError(e instanceof ApiError ? e.message : "Kunne ikke hente kendelsen."));
    return () => {
      cancelled = true;
    };
  }, [params.id]);

  function kopiérLink() {
    const url = `${window.location.origin}/kendelser/${encodeURIComponent(params.id)}`;
    navigator.clipboard.writeText(url).then(() => {
      setKopieret(true);
      setTimeout(() => setKopieret(false), 1800);
    });
  }

  function gemISagsmappe() {
    if (!data) return;
    const mapper = hentAlleMapper();
    let mappe = mapper[0];
    if (!mappe) mappe = opretMappe("Min sagsmappe");
    gemAfgørelse(mappe.id, data);
    setGemtIMappe(mappe.id);
  }

  function fjernFraSagsmappe() {
    if (!data || !gemtIMappe) return;
    fjernAfgørelse(gemtIMappe, data.link);
    setGemtIMappe(null);
  }

  if (error) return <div className="text-sm text-bad">{error}</div>;
  if (!data) return <div className="text-sm text-ink-3">Indlæser…</div>;

  return (
    <div>
      <button onClick={() => router.back()} className="text-[12.5px] text-ink-3 hover:text-ink mb-4 font-medium">
        ← Alle kendelser
      </button>

      <div className="mb-2">
        <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wide border ${BADGE[data.udfald] || BADGE_DEFAULT}`}>
          {data.udfald}
        </span>
      </div>
      <h1 className="text-xl font-bold text-ink leading-snug mb-3 max-w-3xl">{data.titel}</h1>
      <div className="inline-flex flex-wrap border border-line rounded-lg overflow-hidden mb-4 bg-paper">
        {[
          ["Dato", formatDate(data.dato)],
          ["Sagsnr.", data.sagsnummer || "–"],
          ["Selskab", data.selskab || "–"],
          ["Mangeltype", data.mangeltype.join(" / ") || "–"],
          ["Opført", data.opførelsesår ? String(data.opførelsesår) : "–"],
        ].map(([label, val], i, arr) => (
          <div key={label} className={`px-4 py-2 ${i < arr.length - 1 ? "border-r border-line" : ""}`}>
            <div className="text-[9px] font-bold uppercase tracking-wider text-ink-3">{label}</div>
            <div className="text-[12.5px] font-semibold text-ink whitespace-nowrap">{val}</div>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap gap-2 mb-6">
        <a
          href={data.link} target="_blank" rel="noreferrer"
          className="text-[12px] font-medium text-ink-2 border border-line rounded-lg px-3 py-1.5 hover:border-accent"
        >
          Åbn original på ankeforsikring.dk ↗
        </a>
        <button onClick={kopiérLink} className="text-[12px] font-medium text-ink-2 border border-line rounded-lg px-3 py-1.5 hover:border-accent">
          {kopieret ? "✓ Link kopieret" : "🔗 Kopiér link"}
        </button>
        {gemtIMappe ? (
          <button onClick={fjernFraSagsmappe} className="text-[12px] font-medium text-accent-700 border border-blue-200 bg-accent-50 rounded-lg px-3 py-1.5">
            ✓ Gemt i sagsmappe — fjern
          </button>
        ) : (
          <button onClick={gemISagsmappe} className="text-[12px] font-medium text-ink-2 border border-line rounded-lg px-3 py-1.5 hover:border-accent">
            📁 Gem i sagsmappe
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-[220px_1fr] gap-8">
        {data.toc_html && (
          <aside className="hidden md:block">
            <div
              className="sticky top-20 [&_.rd-toc]:bg-paper [&_.rd-toc]:border [&_.rd-toc]:border-line-soft [&_.rd-toc]:rounded-xl [&_.rd-toc]:p-3.5
                         [&_.rd-toc-h]:text-[10px] [&_.rd-toc-h]:font-bold [&_.rd-toc-h]:uppercase [&_.rd-toc-h]:tracking-wider [&_.rd-toc-h]:text-ink-3 [&_.rd-toc-h]:mb-2.5
                         [&_.rd-toc-link]:block [&_.rd-toc-link]:text-[12.5px] [&_.rd-toc-link]:text-ink-2 [&_.rd-toc-link]:no-underline [&_.rd-toc-link]:py-1 [&_.rd-toc-link]:px-1.5 [&_.rd-toc-link]:rounded-md [&_.rd-toc-link]:mb-0.5
                         [&_.rd-toc-link:hover]:bg-accent-50 [&_.rd-toc-link:hover]:text-accent-700
                         [&_.rd-toc-l3]:pl-4 [&_.rd-toc-l3]:text-[11.5px] [&_.rd-toc-l3]:text-ink-3"
              dangerouslySetInnerHTML={{ __html: data.toc_html }}
            />
          </aside>
        )}
        {/* body_html er genereret af vores egen backend fra Ejnars scrapede afgørelsestekster
            (samme tillidsgrænse som resten af datasættet) — ikke fri brugerinput. */}
        <article
          className="max-w-[74ch] text-[15px] leading-[1.8] text-ink"
          dangerouslySetInnerHTML={{ __html: data.body_html }}
        />
      </div>
    </div>
  );
}
