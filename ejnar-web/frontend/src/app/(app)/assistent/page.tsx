"use client";

import { useRef, useState } from "react";
import { useFilters } from "@/lib/FilterContext";
import { askStream, downloadNotat } from "@/lib/api";
import { mdToHtml, erstatKildeRefs } from "@/lib/markdown";
import type { AskEvent, ChatMessage, Kendelse } from "@/lib/types";
import SourcePanel from "@/components/SourcePanel";

interface Turn {
  bruger: string;
  assistentTekst: string;
  kilder: Kendelse[];
  suspekte: string[];
  streaming: boolean;
  fejl?: string;
  openSourceIdx: number | null;
}

const FORSLAG = [
  "Hvornår dækker ejerskifteforsikringen skimmelsvamp?",
  "Hvilken praksis har Ankenævnet for utætheder i tag?",
  "Hvordan bedømmes restlevetid på installationer?",
  "Hvornår er en mangel undtaget pga. tilstandsrapporten?",
];

export default function AssistentPage() {
  const { filters } = useFilters();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const busy = turns.some((t) => t.streaming);
  const abortRef = useRef<AbortController | null>(null);

  async function stil(spørgsmål: string) {
    const s = spørgsmål.trim();
    if (!s || busy) return;
    setInput("");

    const historik: ChatMessage[] = turns.flatMap((t) => [
      { rolle: "bruger" as const, tekst: t.bruger },
      { rolle: "assistent" as const, tekst: t.assistentTekst, kilder: t.kilder },
    ]);

    setTurns((prev) => [
      ...prev,
      { bruger: s, assistentTekst: "", kilder: [], suspekte: [], streaming: true, openSourceIdx: null },
    ]);

    const controller = new AbortController();
    abortRef.current = controller;

    const update = (fn: (t: Turn) => Turn) =>
      setTurns((prev) => prev.map((t, i) => (i === prev.length - 1 ? fn(t) : t)));

    await askStream(
      s, historik, filters,
      (ev: AskEvent) => {
        if (ev.type === "kilder") update((t) => ({ ...t, kilder: ev.kilder }));
        else if (ev.type === "delta") update((t) => ({ ...t, assistentTekst: t.assistentTekst + ev.text }));
        else if (ev.type === "done") update((t) => ({ ...t, assistentTekst: ev.text, suspekte: ev.suspekte, streaming: false }));
        else if (ev.type === "error") update((t) => ({ ...t, fejl: ev.message, streaming: false }));
      },
      controller.signal,
    );
  }

  function setOpenSource(turnIdx: number, srcIdx: number | null) {
    setTurns((prev) => prev.map((t, i) => (i === turnIdx ? { ...t, openSourceIdx: srcIdx } : t)));
  }

  function ryd() {
    abortRef.current?.abort();
    setTurns([]);
  }

  return (
    <div>
      <div className="card p-4 mb-5 flex items-start gap-3">
        <span className="text-xl">✦</span>
        <div>
          <div className="text-[13px] font-semibold text-ink">Spørg til praksis om ejerskifteforsikring</div>
          <div className="text-[12px] text-ink-3 mt-0.5">
            Svarer med kildehenvisninger du kan klikke på. Opfølgningsspørgsmål husker kontekst.
          </div>
          <div className="text-[10.5px] text-ink-3 mt-1">Søgemetode: TF-IDF (keyword-baseret)</div>
        </div>
      </div>

      {turns.length === 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-5">
          {FORSLAG.map((f) => (
            <button
              key={f}
              onClick={() => stil(f)}
              className="text-left text-[12.5px] text-ink-2 border border-line-soft rounded-xl px-3.5 py-3 hover:border-accent hover:bg-accent-50/40 transition-colors"
            >
              {f}
            </button>
          ))}
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          stil(input);
        }}
        className="flex gap-2 mb-3"
      >
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              stil(input);
            }
          }}
          rows={2}
          placeholder="Spørg om Ankenævnets praksis — fx »Hvornår dækkes skjult skimmel?«"
          className="flex-1 rounded-lg border border-line px-3.5 py-2 text-sm outline-none resize-none
                     focus:ring-2 focus:ring-accent/40 focus:border-accent bg-paper text-ink"
        />
        <div className="flex flex-col gap-2">
          <button
            type="submit"
            disabled={busy || !input.trim()}
            className="rounded-lg bg-accent text-white font-semibold text-[13px] px-4 py-2 hover:bg-accent-700 disabled:opacity-50"
          >
            Send ➤
          </button>
          {turns.length > 0 && (
            <button type="button" onClick={ryd} className="rounded-lg border border-line text-[12px] font-medium px-4 py-1.5 hover:border-accent">
              Ryd chat
            </button>
          )}
        </div>
      </form>

      <div className="space-y-6">
        {[...turns].reverse().map((t, ri) => {
          const i = turns.length - 1 - ri;
          const html = erstatKildeRefs(mdToHtml(t.assistentTekst), t.kilder);
          return (
            <div key={i}>
              <div className="flex justify-end mb-1">
                <span className="text-[10px] font-bold uppercase tracking-wider text-ink-3">Du</span>
              </div>
              <div className="flex justify-end mb-3">
                <div className="bg-ink text-white rounded-2xl rounded-tr-md px-4 py-2.5 text-[13px] max-w-[75%]">
                  {t.bruger}
                </div>
              </div>

              <div className="flex items-center gap-1.5 mb-2">
                <span className="text-[10px] font-bold uppercase tracking-wider text-accent-700">Ejnar</span>
                {t.streaming && <span className="text-[11px] text-ink-3">søger og svarer…</span>}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-[1.6fr_1fr] gap-4">
                <div>
                  <div
                    className="card px-4 py-3.5 text-[14px] leading-[1.7] prose-svar cite-click-container"
                    onClick={(e) => {
                      const el = (e.target as HTMLElement).closest<HTMLElement>("[data-kilde]");
                      if (el) setOpenSource(i, Number(el.dataset.kilde) - 1);
                    }}
                    dangerouslySetInnerHTML={{ __html: html || (t.streaming ? "…" : "") }}
                  />
                  {t.fejl && <div className="mt-2 text-sm text-bad">{t.fejl}</div>}
                  {!t.streaming && t.assistentTekst && (
                    <div className="flex items-center gap-3 mt-2">
                      <button
                        onClick={() => navigator.clipboard.writeText(t.assistentTekst)}
                        className="text-[11.5px] text-ink-3 hover:text-ink font-medium border border-line rounded-md px-2.5 py-1"
                      >
                        Kopiér svar
                      </button>
                      <button
                        onClick={() =>
                          downloadNotat(t.bruger, t.assistentTekst, t.kilder).then(async (r) => {
                            const blob = await r.blob();
                            const url = URL.createObjectURL(blob);
                            const a = document.createElement("a");
                            a.href = url;
                            a.download = "ejnar-notat.html";
                            a.click();
                            URL.revokeObjectURL(url);
                          })
                        }
                        className="text-[11.5px] text-ink-3 hover:text-ink font-medium border border-line rounded-md px-2.5 py-1"
                      >
                        📄 Download som notat
                      </button>
                      {t.suspekte.length > 0 && (
                        <details className="text-[11.5px]">
                          <summary className="cursor-pointer text-warn font-medium">
                            ⚠ Citatkontrol — {t.suspekte.length} citat(er) bør dobbelttjekkes
                          </summary>
                          <div className="mt-1.5 space-y-1 text-ink-2">
                            {t.suspekte.slice(0, 5).map((c, ci) => (
                              <div key={ci} className="italic">
                                »{c.length > 160 ? c.slice(0, 160) + "…" : c}«
                              </div>
                            ))}
                          </div>
                        </details>
                      )}
                    </div>
                  )}
                </div>
                <div>
                  {t.kilder.length === 0 ? (
                    <div className="text-[12px] text-ink-3">Ingen kilder fundet til dette svar.</div>
                  ) : (
                    <SourcePanel
                      kilder={t.kilder}
                      svarTekst={t.assistentTekst}
                      openIndex={t.openSourceIdx}
                      onOpen={(idx) => setOpenSource(i, idx)}
                      onClose={() => setOpenSource(i, null)}
                    />
                  )}
                </div>
              </div>
            </div>
          );
        })}

        {turns.length === 0 && (
          <div className="text-center py-14 text-ink-3">
            <div className="text-2xl mb-2">💬</div>
            <div className="font-semibold text-ink-2 mb-1">Stil dit første spørgsmål</div>
            <div className="text-[13px]">Skriv ovenfor eller vælg et forslag.</div>
          </div>
        )}
      </div>
    </div>
  );
}
