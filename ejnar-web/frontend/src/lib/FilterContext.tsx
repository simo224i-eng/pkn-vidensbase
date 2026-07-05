"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { getFilters } from "./api";
import type { FilterOptions, FilterState } from "./types";

interface Ctx {
  options: FilterOptions | null;
  loading: boolean;
  error: string | null;
  filters: FilterState;
  setFilters: (f: FilterState) => void;
  resetFilters: () => void;
  hasActiveFilters: boolean;
  reload: () => void;
}

const TOM: FilterState = { mangeltype: [], selskab: [], udfald: [] };

const FilterCtx = createContext<Ctx | null>(null);

export function FilterProvider({ children }: { children: ReactNode }) {
  const [options, setOptions] = useState<FilterOptions | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<FilterState>(TOM);
  const [gen, setGen] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getFilters()
      .then((opts) => {
        if (cancelled) return;
        setOptions(opts);
        setError(null);
        setFilters((prev) => ({
          ...prev,
          år_min: prev.år_min ?? opts.år_min,
          år_max: prev.år_max ?? opts.år_max,
          opførelsesår_min: prev.opførelsesår_min ?? opts.opførelsesår_min,
          opførelsesår_max: prev.opførelsesår_max ?? opts.opførelsesår_max,
        }));
      })
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : "Kunne ikke hente filtre."))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [gen]);

  const resetFilters = () => {
    if (!options) return;
    setFilters({
      mangeltype: [], selskab: [], udfald: [],
      år_min: options.år_min, år_max: options.år_max,
      opførelsesår_min: options.opførelsesår_min, opførelsesår_max: options.opførelsesår_max,
    });
  };

  const hasActiveFilters = useMemo(() => {
    if (!options) return false;
    return (
      filters.mangeltype.length > 0 || filters.selskab.length > 0 || filters.udfald.length > 0 ||
      filters.år_min !== options.år_min || filters.år_max !== options.år_max ||
      filters.opførelsesår_min !== options.opførelsesår_min ||
      filters.opførelsesår_max !== options.opførelsesår_max
    );
  }, [filters, options]);

  return (
    <FilterCtx.Provider
      value={{
        options, loading, error, filters, setFilters, resetFilters, hasActiveFilters,
        reload: () => {
          setLoading(true);
          setGen((g) => g + 1);
        },
      }}
    >
      {children}
    </FilterCtx.Provider>
  );
}

export function useFilters() {
  const ctx = useContext(FilterCtx);
  if (!ctx) throw new Error("useFilters skal bruges inden i <FilterProvider>");
  return ctx;
}
