import type {
  AskEvent, ChatMessage, FilterOptions, FilterState, KendelseDetalje, KendelserResponse,
  StatsResponse,
} from "./types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, { credentials: "same-origin", ...init });
  if (!r.ok) {
    let detail = r.statusText;
    try {
      const body = await r.json();
      detail = body.detail || detail;
    } catch {
      /* ingen JSON-body */
    }
    throw new ApiError(r.status, detail);
  }
  return r.json();
}

export function login(password: string) {
  return req<{ ok: boolean }>("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
}

export function logout() {
  return req<{ ok: boolean }>("/api/logout", { method: "POST" });
}

export function getFilters() {
  return req<FilterOptions>("/api/filters");
}

function filterParams(f: Partial<FilterState>): URLSearchParams {
  const p = new URLSearchParams();
  f.mangeltype?.forEach((v) => p.append("mangeltype", v));
  f.selskab?.forEach((v) => p.append("selskab", v));
  f.udfald?.forEach((v) => p.append("udfald", v));
  if (f.år_min != null) p.set("år_min", String(f.år_min));
  if (f.år_max != null) p.set("år_max", String(f.år_max));
  if (f.opførelsesår_min != null) p.set("opførelsesår_min", String(f.opførelsesår_min));
  if (f.opførelsesår_max != null) p.set("opførelsesår_max", String(f.opførelsesår_max));
  return p;
}

export function searchKendelser(opts: {
  q?: string;
  søgetype?: "ordret" | "intelligent";
  filters?: Partial<FilterState>;
  page?: number;
  page_size?: number;
}) {
  const p = filterParams(opts.filters || {});
  if (opts.q) p.set("q", opts.q);
  if (opts.søgetype) p.set("søgetype", opts.søgetype);
  p.set("page", String(opts.page ?? 1));
  p.set("page_size", String(opts.page_size ?? 25));
  return req<KendelserResponse>(`/api/kendelser?${p.toString()}`);
}

export function getKendelse(id: string) {
  return req<KendelseDetalje>(`/api/kendelser/${encodeURIComponent(id)}`);
}

export function getStats(filters: Partial<FilterState> = {}) {
  const p = filterParams(filters);
  return req<StatsResponse>(`/api/stats?${p.toString()}`);
}

export function downloadNotat(spørgsmål: string, svar: string, kilder: unknown[]) {
  return fetch("/api/notat", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ spørgsmål, svar, kilder }),
  });
}

export function kildeCitat(kendelseId: string, svar: string) {
  return req<{ quotes: string[]; toc_html: string; body_html: string }>("/api/kilde-citat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kendelse_id: kendelseId, svar }),
  });
}

/**
 * Streamer et AI-svar via Server-Sent Events. onEvent kaldes for hvert event
 * efterhånden som de ankommer (kilder → mange delta'er → done/error).
 */
export async function askStream(
  spørgsmål: string,
  historik: ChatMessage[],
  filters: Partial<FilterState>,
  onEvent: (ev: AskEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const r = await fetch("/api/ask", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ spørgsmål, historik, filtre: filters }),
    signal,
  });
  if (!r.ok || !r.body) {
    onEvent({ type: "error", message: `Serverfejl (${r.status})` });
    return;
  }

  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop() ?? "";
    for (const part of parts) {
      const line = part.split("\n").find((l) => l.startsWith("data: "));
      if (!line) continue;
      try {
        onEvent(JSON.parse(line.slice(6)) as AskEvent);
      } catch {
        /* ufuldstændigt/ugyldigt event — spring over */
      }
    }
  }
}
