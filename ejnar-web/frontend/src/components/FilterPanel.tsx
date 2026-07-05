"use client";

import { useFilters } from "@/lib/FilterContext";

function MultiChipSelect({
  label, options, selected, onChange,
}: {
  label: string;
  options: string[];
  selected: string[];
  onChange: (vals: string[]) => void;
}) {
  function toggle(v: string) {
    onChange(selected.includes(v) ? selected.filter((x) => x !== v) : [...selected, v]);
  }
  return (
    <div>
      <div className="text-[10px] font-bold uppercase tracking-wider text-ink-3 mb-1.5">{label}</div>
      <div className="flex flex-wrap gap-1.5">
        {options.map((opt) => (
          <button
            key={opt}
            onClick={() => toggle(opt)}
            className={`px-2.5 py-1 rounded-md text-[11.5px] font-medium border transition-colors ${
              selected.includes(opt)
                ? "bg-ink text-white border-ink"
                : "bg-paper text-ink-2 border-line hover:border-accent"
            }`}
          >
            {opt}
          </button>
        ))}
      </div>
    </div>
  );
}

function RangeSlider({
  label, min, max, value, onChange,
}: {
  label: string;
  min: number;
  max: number;
  value: [number, number];
  onChange: (v: [number, number]) => void;
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between mb-1.5">
        <div className="text-[10px] font-bold uppercase tracking-wider text-ink-3">{label}</div>
        <div className="text-[11px] font-semibold text-ink-2">
          {value[0]}–{value[1]}
        </div>
      </div>
      <div className="flex gap-2 items-center">
        <input
          type="range" min={min} max={max} value={value[0]}
          onChange={(e) => onChange([Math.min(Number(e.target.value), value[1]), value[1]])}
          className="w-full accent-accent"
        />
        <input
          type="range" min={min} max={max} value={value[1]}
          onChange={(e) => onChange([value[0], Math.max(Number(e.target.value), value[0])])}
          className="w-full accent-accent"
        />
      </div>
    </div>
  );
}

export default function FilterPanel() {
  const { options, filters, setFilters, resetFilters, hasActiveFilters, loading, error } = useFilters();

  if (loading) return <div className="text-sm text-ink-3">Indlæser filtre…</div>;
  if (error) return <div className="text-sm text-bad">{error}</div>;
  if (!options) return null;

  return (
    <div className="card p-4 space-y-4">
      <MultiChipSelect
        label="Mangeltype" options={options.mangeltyper} selected={filters.mangeltype}
        onChange={(v) => setFilters({ ...filters, mangeltype: v })}
      />
      <MultiChipSelect
        label="Forsikringsselskab" options={options.selskaber} selected={filters.selskab}
        onChange={(v) => setFilters({ ...filters, selskab: v })}
      />
      <MultiChipSelect
        label="Udfald" options={options.udfald} selected={filters.udfald}
        onChange={(v) => setFilters({ ...filters, udfald: v })}
      />
      <RangeSlider
        label="Husets opførelsesår" min={options.opførelsesår_min} max={options.opførelsesår_max}
        value={[filters.opførelsesår_min ?? options.opførelsesår_min, filters.opførelsesår_max ?? options.opførelsesår_max]}
        onChange={([lo, hi]) => setFilters({ ...filters, opførelsesår_min: lo, opførelsesår_max: hi })}
      />
      <RangeSlider
        label="Afgørelsesår" min={options.år_min} max={options.år_max}
        value={[filters.år_min ?? options.år_min, filters.år_max ?? options.år_max]}
        onChange={([lo, hi]) => setFilters({ ...filters, år_min: lo, år_max: hi })}
      />
      {hasActiveFilters && (
        <button
          onClick={resetFilters}
          className="w-full text-[12px] font-medium text-ink-2 border border-line rounded-lg py-2 hover:border-accent hover:text-accent-700 transition-colors"
        >
          Nulstil filtre
        </button>
      )}
    </div>
  );
}
