"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  fjernAfgørelse, hentAlleMapper, omdøbMappe, opdaterNote, opretMappe, sletMappe,
  type Sagsmappe,
} from "@/lib/sagsmapper";

function formatDate(iso: string | null) {
  if (!iso) return "–";
  const [y, m, d] = iso.split("-");
  return `${d}.${m}.${y}`;
}

function byggDownloadTekst(mappe: Sagsmappe): string {
  const lines = [
    "EJNAR — SAGSMAPPE-EKSPORT",
    `Mappe: ${mappe.navn}`,
    `Antal kendelser: ${mappe.afgørelser.length}`,
    `Genereret: ${new Date().toLocaleString("da-DK")}`,
    "=".repeat(72), "",
  ];
  for (const a of mappe.afgørelser) {
    lines.push(
      `KENDELSE:    ${a.titel}`,
      `DATO:        ${formatDate(a.dato)}`,
      `UDFALD:      ${a.udfald || "–"}`,
      `SELSKAB:     ${a.selskab || "–"}`,
      `MANGELTYPE:  ${a.mangeltype.join(", ") || "–"}`,
      `LINK:        ${a.link}`,
    );
    if (a.note.trim()) lines.push(`NOTE:        ${a.note.trim()}`);
    lines.push("-".repeat(72), a.excerpt, "", "=".repeat(72), "");
  }
  return lines.join("\n");
}

function downloadTextFile(filename: string, content: string) {
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function SagsmapperPage() {
  const [mapper, setMapper] = useState<Sagsmappe[]>([]);
  const [nytNavn, setNytNavn] = useState("");

  // Hydrerer fra localStorage efter mount (utilgængeligt under SSR-prerender).
  // useSyncExternalStore ville være "korrekt" iht. linteren, men kræver en
  // snapshot-cache for at undgå at hentAlleMapper()'s nye array-reference
  // udløser render-loops — uforholdsmæssig kompleksitet for denne ene side.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => setMapper(hentAlleMapper()), []);
  const opdater = () => setMapper(hentAlleMapper());

  return (
    <div className="max-w-3xl">
      <p className="text-[12.5px] text-ink-3 mb-4">
        Saml kendelser til en konkret sag, skriv noter og download det hele som én fil.{" "}
        <strong className="text-ink-2">Gemmes i din browser</strong> (localStorage) — overlever
        genstart af browseren, men følger ikke med til en anden computer.
      </p>

      <div className="flex gap-2 mb-6">
        <input
          value={nytNavn}
          onChange={(e) => setNytNavn(e.target.value)}
          placeholder="Navn på ny sagsmappe — fx »Skimmelsag, Fyrrevej 12«"
          className="flex-1 rounded-lg border border-line px-3.5 py-2 text-sm outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent bg-paper"
        />
        <button
          onClick={() => {
            if (!nytNavn.trim()) return;
            opretMappe(nytNavn.trim());
            setNytNavn("");
            opdater();
          }}
          className="rounded-lg bg-accent text-white font-semibold text-[13px] px-4 py-2 hover:bg-accent-700 shrink-0"
        >
          ＋ Opret mappe
        </button>
      </div>

      {mapper.length === 0 ? (
        <div className="text-center py-14 text-ink-3">
          <div className="text-2xl mb-2">📁</div>
          <div className="font-semibold text-ink-2 mb-1">Ingen sagsmapper endnu</div>
          <div className="text-[13px]">Opret en mappe ovenfor, eller gem en kendelse fra detaljevisningen.</div>
        </div>
      ) : (
        <div className="space-y-4">
          {mapper.map((mappe) => (
            <MappeCard key={mappe.id} mappe={mappe} onChange={opdater} />
          ))}
        </div>
      )}
    </div>
  );
}

function MappeCard({ mappe, onChange }: { mappe: Sagsmappe; onChange: () => void }) {
  const [navn, setNavn] = useState(mappe.navn);
  const [åben, setÅben] = useState(true);

  return (
    <div className="card p-4">
      <div className="flex items-center gap-2 mb-3">
        <button onClick={() => setÅben((a) => !a)} className="text-[12px] text-ink-3 hover:text-ink shrink-0">
          {åben ? "▾" : "▸"}
        </button>
        <input
          value={navn}
          onChange={(e) => {
            setNavn(e.target.value);
            if (e.target.value.trim()) omdøbMappe(mappe.id, e.target.value.trim());
          }}
          className="flex-1 font-semibold text-[13.5px] text-ink bg-transparent outline-none border-b border-transparent focus:border-line"
        />
        <span className="text-[11px] text-ink-3 shrink-0">
          {mappe.afgørelser.length} kendelse{mappe.afgørelser.length !== 1 ? "r" : ""}
        </span>
        <button
          onClick={() => downloadTextFile(`sagsmappe_${mappe.navn.slice(0, 30)}.txt`, byggDownloadTekst(mappe))}
          className="text-[11.5px] font-medium text-ink-2 border border-line rounded-md px-2.5 py-1 hover:border-accent shrink-0"
        >
          ⬇️ Download
        </button>
        <button
          onClick={() => {
            sletMappe(mappe.id);
            onChange();
          }}
          className="text-[11.5px] font-medium text-bad border border-red-200 rounded-md px-2.5 py-1 hover:bg-bad-bg shrink-0"
        >
          🗑 Slet
        </button>
      </div>

      {åben && (
        <div className="space-y-3">
          {mappe.afgørelser.length === 0 && (
            <div className="text-[12px] text-ink-3">Mappen er tom — gem kendelser fra detaljevisningen.</div>
          )}
          {mappe.afgørelser.map((a) => (
            <div key={a.link} className="border-t border-line-soft pt-3">
              <div className="text-[12.5px] font-semibold text-ink leading-snug">{a.titel}</div>
              <div className="text-[11px] text-ink-3 mt-0.5 mb-2">
                {formatDate(a.dato)} · {a.udfald || "–"} · {a.selskab || "–"}
              </div>
              <textarea
                defaultValue={a.note}
                onBlur={(e) => opdaterNote(mappe.id, a.link, e.target.value)}
                placeholder="Egne noter til denne kendelse…"
                rows={2}
                className="w-full text-[12px] rounded-md border border-line px-2.5 py-1.5 outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent bg-paper resize-none mb-1.5"
              />
              <div className="flex gap-2">
                <Link
                  href={`/kendelser/${encodeURIComponent(a.id)}`}
                  className="text-[11.5px] font-medium text-accent-700 hover:underline"
                >
                  Åbn →
                </Link>
                <button
                  onClick={() => {
                    fjernAfgørelse(mappe.id, a.link);
                    onChange();
                  }}
                  className="text-[11.5px] font-medium text-ink-3 hover:text-bad"
                >
                  Fjern
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
