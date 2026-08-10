// Sagsmapper persisteret i localStorage — overlever browser-genstart, i
// modsætning til Streamlit-versionens rene session-state. Simpelt og
// dependency-frit; kan senere flyttes server-side hvis flere brugere skal
// dele mapper.
import type { Kendelse } from "./types";

const STORAGE_KEY = "ejnar_sagsmapper_v1";

export interface GemtAfgørelse {
  id: string;
  link: string;
  titel: string;
  dato: string | null;
  udfald: string;
  selskab: string;
  mangeltype: string[];
  excerpt: string;
  note: string;
  tilføjet: string;
}

export interface Sagsmappe {
  id: string;
  navn: string;
  oprettet: string;
  afgørelser: GemtAfgørelse[];
}

interface Lager {
  mapper: Record<string, Sagsmappe>;
}

function tomtLager(): Lager {
  return { mapper: {} };
}

function læs(): Lager {
  if (typeof window === "undefined") return tomtLager();
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return tomtLager();
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" && parsed.mapper ? parsed : tomtLager();
  } catch {
    return tomtLager();
  }
}

function skriv(lager: Lager) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(lager));
}

function nytId(): string {
  return Math.random().toString(36).slice(2, 12);
}

export function hentAlleMapper(): Sagsmappe[] {
  return Object.values(læs().mapper).sort((a, b) => a.oprettet.localeCompare(b.oprettet));
}

export function opretMappe(navn: string): Sagsmappe {
  const lager = læs();
  const mappe: Sagsmappe = {
    id: nytId(),
    navn,
    oprettet: new Date().toISOString(),
    afgørelser: [],
  };
  lager.mapper[mappe.id] = mappe;
  skriv(lager);
  return mappe;
}

export function omdøbMappe(id: string, nytNavn: string) {
  const lager = læs();
  if (lager.mapper[id]) {
    lager.mapper[id].navn = nytNavn;
    skriv(lager);
  }
}

export function sletMappe(id: string) {
  const lager = læs();
  delete lager.mapper[id];
  skriv(lager);
}

export function gemAfgørelse(mappeId: string, k: Kendelse): boolean {
  const lager = læs();
  const mappe = lager.mapper[mappeId];
  if (!mappe) return false;
  if (mappe.afgørelser.some((a) => a.link === k.link)) return false;
  mappe.afgørelser.push({
    id: k.id, link: k.link, titel: k.titel, dato: k.dato, udfald: k.udfald,
    selskab: k.selskab, mangeltype: k.mangeltype, excerpt: k.excerpt,
    note: "", tilføjet: new Date().toISOString(),
  });
  skriv(lager);
  return true;
}

export function fjernAfgørelse(mappeId: string, link: string) {
  const lager = læs();
  const mappe = lager.mapper[mappeId];
  if (!mappe) return;
  mappe.afgørelser = mappe.afgørelser.filter((a) => a.link !== link);
  skriv(lager);
}

export function opdaterNote(mappeId: string, link: string, note: string) {
  const lager = læs();
  const mappe = lager.mapper[mappeId];
  if (!mappe) return;
  const a = mappe.afgørelser.find((x) => x.link === link);
  if (a) {
    a.note = note;
    skriv(lager);
  }
}

export function findMappeForLink(link: string): string | null {
  const lager = læs();
  for (const mappe of Object.values(lager.mapper)) {
    if (mappe.afgørelser.some((a) => a.link === link)) return mappe.id;
  }
  return null;
}

export function alleGemteLinks(): Set<string> {
  const lager = læs();
  const links = new Set<string>();
  Object.values(lager.mapper).forEach((m) => m.afgørelser.forEach((a) => links.add(a.link)));
  return links;
}
