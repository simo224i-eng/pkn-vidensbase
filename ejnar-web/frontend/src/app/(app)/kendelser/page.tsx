"use client";

import { useEffect, useState } from "react";
import { useFilters } from "@/lib/FilterContext";
import { useDebounced } from "@/lib/useDebounced";
import { searchKendelser, ApiError } from "@/lib/api";
import type { FilterState, Kendelse } from "@/lib/types";
import FilterPanel from "@/components/FilterPanel";
import KendelseCard from "@/components/KendelseCard";

const PAGE_SIZE = 24;

export default function KendelserPage() {
  const { filters, loading: filtersLoading } = useFilters();
  const [q, setQ] = useState("");
  const [søgetype, setSøgetype] = useState<"ordret" | "intelligent">("ordret");
  const debouncedQ = useDebounced(q, 350);
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<Kendelse[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // React-anbefalet mønster ("Adjusting state when a prop changes"): når
  // filtrene ændres i en søskende-komponent (FilterPanel), nulstiller vi side
  // og markerer "søger" under selve renderet — ikke i en effect, så der ikke
  // opstår et ekstra flimrende render. q/søgetype/paginering sætter i stedet
  // loading direkte i deres egne event-handlers nedenfor.
  const [forrigeFilters, setForrigeFilters] = useState<FilterState>(filters);
  if (filters !== forrigeFilters) {
    setForrigeFilters(filters);
    setPage(1);
    setLoading(true);
  }

  useEffect(() => {
    if (filtersLoading) return;
    let cancelled = false;
    searchKendelser({ q: debouncedQ, søgetype, filters, page, page_size: PAGE_SIZE })
      .then((res) => {
        if (cancelled) return;
        setItems(res.items);
        setTotal(res.total);
        setError(null);
      })
      .catch((e) => !cancelled && setError(e instanceof ApiError ? e.message : "Søgning fejlede."))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [debouncedQ, søgetype, filters, page, filtersLoading]);

  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="grid grid-cols-1 md:grid-cols-[260px_1fr] gap-6">
      <aside>
        <FilterPanel />
      </aside>
      <section>
        <div className="mb-4 flex flex-col sm:flex-row gap-2">
          <input
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setPage(1);
              setLoading(true);
            }}
            placeholder="Søg — f.eks. skimmel, tag, selvrisiko, levetid…"
            className="flex-1 rounded-lg border border-line px-3.5 py-2 text-sm outline-none
                       focus:ring-2 focus:ring-accent/40 focus:border-accent bg-paper text-ink"
          />
          <div className="flex rounded-lg border border-line overflow-hidden text-[12.5px] font-medium shrink-0">
            {(["ordret", "intelligent"] as const).map((t) => (
              <button
                key={t}
                onClick={() => {
                  setSøgetype(t);
                  setPage(1);
                  setLoading(true);
                }}
                className={`px-3 py-2 transition-colors ${
                  søgetype === t ? "bg-ink text-white" : "bg-paper text-ink-2 hover:bg-surface"
                }`}
              >
                {t === "ordret" ? "Ordret" : "Intelligent"}
              </button>
            ))}
          </div>
        </div>

        <div className="text-[12.5px] text-ink-3 mb-3">
          {loading ? "Søger…" : `${total.toLocaleString("da-DK")} kendelser`}
        </div>

        {error && <div className="text-sm text-bad mb-4">{error}</div>}

        {!loading && items.length === 0 && !error && (
          <div className="text-center py-16 text-ink-3">
            <div className="text-2xl mb-2">🔍</div>
            <div className="font-semibold text-ink-2 mb-1">Ingen kendelser matcher</div>
            <div className="text-[13px]">Prøv at udvide filtrene eller ændre søgeordene.</div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          {items.map((k) => (
            <KendelseCard key={k.link} k={k} />
          ))}
        </div>

        {pages > 1 && (
          <div className="flex items-center justify-center gap-3 mt-6">
            <button
              disabled={page <= 1}
              onClick={() => {
                setPage((p) => p - 1);
                setLoading(true);
              }}
              className="px-3 py-1.5 rounded-lg border border-line text-[12.5px] font-medium disabled:opacity-40 hover:border-accent"
            >
              ← Forrige
            </button>
            <span className="text-[12.5px] text-ink-3">
              Side {page} af {pages}
            </span>
            <button
              disabled={page >= pages}
              onClick={() => {
                setPage((p) => p + 1);
                setLoading(true);
              }}
              className="px-3 py-1.5 rounded-lg border border-line text-[12.5px] font-medium disabled:opacity-40 hover:border-accent"
            >
              Næste →
            </button>
          </div>
        )}
      </section>
    </div>
  );
}
