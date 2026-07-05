// Spejler backend/app/models.py — hold i sync ved ændringer i API'et.

export interface Kendelse {
  id: string;
  dato: string | null;
  år: number | null;
  opførelsesår: number | null;
  titel: string;
  link: string;
  excerpt: string;
  sagsnummer: string;
  selskab: string;
  udfald: string;
  mangeltype: string[];
}

export interface KendelseDetalje extends Kendelse {
  tekst: string;
  toc_html: string;
  body_html: string;
}

export interface KendelserResponse {
  total: number;
  items: Kendelse[];
}

export interface FilterOptions {
  mangeltyper: string[];
  selskaber: string[];
  udfald: string[];
  år_min: number;
  år_max: number;
  opførelsesår_min: number;
  opførelsesår_max: number;
}

export interface FilterState {
  mangeltype: string[];
  selskab: string[];
  udfald: string[];
  år_min?: number;
  år_max?: number;
  opførelsesår_min?: number;
  opførelsesår_max?: number;
}

export interface ChatMessage {
  rolle: "bruger" | "assistent";
  tekst: string;
  kilder?: Kendelse[];
  suspekte?: string[];
  auto_filter?: AutoFilterInfo;
}

export interface AutoFilterInfo {
  suggested: Record<string, string[]>;
  applied: boolean;
  before: number;
  after: number;
}

export interface StatsResponse {
  total: number;
  medhold_pct: number;
  antal_selskaber: number;
  år_span: string;
  per_år: { år: number; antal: number }[];
  udfald_per_år: { år: number; udfald: string; antal: number }[];
  top_mangeltyper: { mangeltype: string; antal: number }[];
  top_selskaber: { selskab: string; antal: number }[];
  medhold_rate_per_mangeltype: { mangeltype: string; antal: number; medhold_pct: number }[];
}

export type AskEvent =
  | { type: "kilder"; kilder: Kendelse[]; auto_filter: AutoFilterInfo }
  | { type: "delta"; text: string }
  | { type: "done"; text: string; suspekte: string[] }
  | { type: "error"; message: string };
