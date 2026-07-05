"use client";

import Link from "next/link";
import type { Kendelse } from "@/lib/types";

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

export default function KendelseCard({ k }: { k: Kendelse }) {
  return (
    <Link
      href={`/kendelser/${encodeURIComponent(k.id)}`}
      className="card block p-4 hover:border-accent transition-colors"
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] text-ink-3 font-medium">{formatDate(k.dato)}</span>
        <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${BADGE[k.udfald] || BADGE_DEFAULT}`}>
          {k.udfald}
        </span>
      </div>
      <div className="text-[13.5px] font-semibold text-ink leading-snug mb-2">{k.titel}</div>
      <div className="flex flex-wrap gap-1 mb-2">
        {k.mangeltype.map((m) => (
          <span key={m} className="px-1.5 py-0.5 rounded bg-surface border border-line-soft text-[10px] text-ink-2">
            {m}
          </span>
        ))}
        {k.selskab && (
          <span className="px-1.5 py-0.5 rounded bg-surface border border-line-soft text-[10px] text-ink-2">
            {k.selskab}
          </span>
        )}
        {k.opførelsesår && (
          <span className="px-1.5 py-0.5 rounded bg-accent-50 border border-blue-100 text-[10px] text-accent-700">
            Opført {k.opførelsesår}
          </span>
        )}
      </div>
      <p className="text-[12.5px] text-ink-2 leading-relaxed line-clamp-2">{k.excerpt}</p>
    </Link>
  );
}
