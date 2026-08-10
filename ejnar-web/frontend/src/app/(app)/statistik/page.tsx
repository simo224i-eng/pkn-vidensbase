"use client";

import { useEffect, useState } from "react";
import { useFilters } from "@/lib/FilterContext";
import { useDebounced } from "@/lib/useDebounced";
import { getStats, ApiError } from "@/lib/api";
import type { StatsResponse } from "@/lib/types";
import { HorizontalBarList, StatTile, VerticalBarChart } from "@/components/BarList";
import FilterPanel from "@/components/FilterPanel";

function medholdColor(pct: number): string {
  if (pct >= 60) return "#10b981";
  if (pct >= 30) return "#f59e0b";
  return "#ef4444";
}

export default function StatistikPage() {
  const { filters, loading: filtersLoading } = useFilters();
  // Ét stats-kald pr. "færdigt" filtervalg — ikke ét pr. slider-hak.
  const debouncedFilters = useDebounced(filters, 300);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (filtersLoading) return;
    let cancelled = false;
    getStats(debouncedFilters)
      .then((s) => !cancelled && setStats(s))
      .catch((e) => !cancelled && setError(e instanceof ApiError ? e.message : "Kunne ikke hente statistik."));
    return () => {
      cancelled = true;
    };
  }, [debouncedFilters, filtersLoading]);

  return (
    <div className="grid grid-cols-1 md:grid-cols-[260px_1fr] gap-6">
      <aside>
        <FilterPanel />
      </aside>
      <section>
        {error && <div className="text-sm text-bad mb-4">{error}</div>}
        {!stats && !error && <div className="text-sm text-ink-3">Indlæser statistik…</div>}
        {stats && stats.total === 0 && <div className="text-sm text-ink-3">Ingen data med de valgte filtre.</div>}
        {stats && stats.total > 0 && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <StatTile value={stats.total.toLocaleString("da-DK")} label="Kendelser" />
              <StatTile value={`${Math.round(stats.medhold_pct)}%`} label="Medhold-rate" />
              <StatTile value={String(stats.antal_selskaber)} label="Selskaber" />
              <StatTile value={stats.år_span} label="Årsinterval" />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <div className="card p-4">
                <div className="text-[12px] font-semibold text-ink mb-3">Kendelser per år</div>
                <VerticalBarChart rows={stats.per_år.map((r) => ({ label: String(r.år), value: r.antal }))} />
              </div>
              <div className="card p-4">
                <div className="text-[12px] font-semibold text-ink mb-3">Top mangeltyper</div>
                <HorizontalBarList
                  rows={stats.top_mangeltyper.map((r) => ({ label: r.mangeltype, value: r.antal }))}
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <div className="card p-4">
                <div className="text-[12px] font-semibold text-ink mb-3">Top forsikringsselskaber</div>
                <HorizontalBarList
                  rows={stats.top_selskaber.map((r) => ({ label: r.selskab, value: r.antal }))}
                />
              </div>
              <div className="card p-4">
                <div className="text-[12px] font-semibold text-ink mb-3">Medhold-rate per mangeltype</div>
                <HorizontalBarList
                  rows={stats.medhold_rate_per_mangeltype.map((r) => ({
                    label: r.mangeltype, value: r.medhold_pct, suffix: "%",
                  }))}
                  colorFor={medholdColor}
                />
              </div>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
