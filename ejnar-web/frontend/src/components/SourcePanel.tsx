"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { kildeCitat } from "@/lib/api";
import type { Kendelse } from "@/lib/types";

function formatDate(iso: string | null) {
  if (!iso) return "–";
  const [y, m, d] = iso.split("-");
  return `${d}.${m}.${y}`;
}

export default function SourcePanel({
  kilder, svarTekst, openIndex, onOpen, onClose,
}: {
  kilder: Kendelse[];
  svarTekst: string;
  openIndex: number | null;
  onOpen: (i: number) => void;
  onClose: () => void;
}) {
  const [q, setQ] = useState("");

  if (openIndex != null && kilder[openIndex]) {
    // key={id}: fremtvinger remount ved skift af kilde, så useState(null) i
    // OpenSource altid starter frisk — undgår manuel state-reset i en effect.
    return <OpenSource key={kilder[openIndex].id} k={kilder[openIndex]} svarTekst={svarTekst} onClose={onClose} />;
  }

  const filtered = kilder.filter((k) => {
    if (!q.trim()) return true;
    const blob = `${k.titel} ${k.selskab} ${k.sagsnummer} ${k.udfald} ${k.mangeltype.join(" ")}`.toLowerCase();
    return blob.includes(q.toLowerCase());
  });

  return (
    <div className="card p-3">
      <div className="text-[11px] font-bold uppercase tracking-wider text-ink-3 mb-2">
        Fundne afgørelser ({kilder.length})
      </div>
      {kilder.length > 4 && (
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Filtrér på titel, selskab, sagsnr, udfald…"
          className="w-full mb-2 rounded-md border border-line px-2.5 py-1.5 text-[12px] outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent bg-paper"
        />
      )}
      <div className="space-y-2 max-h-[520px] overflow-y-auto">
        {filtered.map((k) => {
          const idx = kilder.indexOf(k);
          return (
            <button
              key={k.link}
              onClick={() => onOpen(idx)}
              className="w-full text-left border border-line-soft rounded-lg p-2.5 hover:border-accent transition-colors"
            >
              <div className="flex items-center gap-2 mb-1">
                <span className="inline-flex items-center justify-center w-5 h-5 rounded-md bg-accent-50 text-accent-700 text-[10.5px] font-bold shrink-0">
                  {idx + 1}
                </span>
                <span className="text-[10.5px] text-ink-3">
                  {formatDate(k.dato)} · {k.udfald} · {k.selskab}
                </span>
              </div>
              <div className="text-[12px] font-semibold text-ink leading-snug">{k.titel}</div>
            </button>
          );
        })}
        {filtered.length === 0 && <div className="text-[12px] text-ink-3 py-2">Ingen match.</div>}
      </div>
    </div>
  );
}

function OpenSource({ k, svarTekst, onClose }: { k: Kendelse; svarTekst: string; onClose: () => void }) {
  const [data, setData] = useState<{ quotes: string[]; toc_html: string; body_html: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    kildeCitat(k.id, svarTekst)
      .then((d) => !cancelled && setData(d))
      .catch(() => !cancelled && setError("Kunne ikke indlæse kendelsen."));
    return () => {
      cancelled = true;
    };
  }, [k.id, svarTekst]);

  return (
    <div className="card overflow-hidden">
      <div className="p-3 border-b border-line-soft bg-surface">
        <button onClick={onClose} className="text-[12px] text-ink-3 hover:text-ink font-medium mb-2">
          ← Luk
        </button>
        <div className="text-[13px] font-bold text-ink leading-snug">{k.titel}</div>
        <div className="text-[11px] text-ink-3 mt-0.5">
          {formatDate(k.dato)} · {k.udfald} · {k.selskab} · sag {k.sagsnummer || "–"}
        </div>
      </div>
      {error && <div className="p-3 text-sm text-bad">{error}</div>}
      {!error && !data && <div className="p-3 text-sm text-ink-3">Indlæser…</div>}
      {data && (
        <>
          {data.quotes.length > 0 && (
            <div className="m-3 p-3 rounded-lg bg-accent-50 border border-blue-100">
              <div className="text-[10px] font-bold uppercase tracking-wider text-accent-700 mb-1.5">
                ✦ Citat brugt i svaret — fremhævet nedenfor
              </div>
              {data.quotes.slice(0, 4).map((qt, i) => (
                <div key={i} className="text-[12.5px] italic text-ink-2 border-l-2 border-accent pl-2.5 my-1.5">
                  »{qt}«
                </div>
              ))}
            </div>
          )}
          <div
            className="max-h-[460px] overflow-y-auto px-4 pb-4 text-[13.5px] leading-[1.7] text-ink
                       [&_mark]:bg-yellow-200 [&_mark]:text-ink [&_mark]:px-0.5 [&_mark]:rounded-sm"
            dangerouslySetInnerHTML={{ __html: data.body_html }}
          />
        </>
      )}
      <div className="px-4 pb-3">
        <Link href={`/kendelser/${encodeURIComponent(k.id)}`} className="text-[11.5px] text-accent-700 font-medium hover:underline">
          Åbn kendelsen i Ejnar →
        </Link>
      </div>
    </div>
  );
}
