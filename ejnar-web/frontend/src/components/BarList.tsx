"use client";

export function HorizontalBarList({
  rows, colorFor,
}: {
  rows: { label: string; value: number; suffix?: string }[];
  colorFor?: (v: number) => string;
}) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <div className="space-y-2">
      {rows.map((r) => (
        <div key={r.label} className="flex items-center gap-2.5">
          <div className="w-32 shrink-0 text-[11.5px] text-ink-2 truncate" title={r.label}>
            {r.label}
          </div>
          <div className="flex-1 h-4 bg-surface rounded-md overflow-hidden">
            <div
              className="h-full rounded-md"
              style={{
                width: `${Math.max(3, (r.value / max) * 100)}%`,
                background: colorFor ? colorFor(r.value) : "var(--accent)",
              }}
            />
          </div>
          <div className="w-12 shrink-0 text-[11.5px] font-semibold text-ink text-right">
            {r.value}
            {r.suffix || ""}
          </div>
        </div>
      ))}
    </div>
  );
}

export function VerticalBarChart({ rows }: { rows: { label: string; value: number }[] }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <div className="flex items-end gap-1 h-40">
      {rows.map((r) => (
        <div key={r.label} className="flex-1 flex flex-col items-center gap-1 group relative">
          <div
            className="w-full rounded-t-sm bg-accent group-hover:bg-accent-700 transition-colors"
            style={{ height: `${Math.max(2, (r.value / max) * 100)}%` }}
            title={`${r.label}: ${r.value}`}
          />
          <div className="text-[9px] text-ink-3 rotate-0 whitespace-nowrap">{r.label}</div>
        </div>
      ))}
    </div>
  );
}

export function StatTile({ value, label }: { value: string; label: string }) {
  return (
    <div className="card p-4 text-center">
      <div className="text-2xl font-extrabold text-ink tracking-tight">{value}</div>
      <div className="text-[10px] font-semibold uppercase tracking-wider text-ink-3 mt-1">{label}</div>
    </div>
  );
}
