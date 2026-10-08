// Ejnar — webapp til praksisresearch. Ren ES-modul uden build-step; taler med /v1-API'et.

// ── Hjælpere ─────────────────────────────────────────────────────────────────
const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const safeUrl = (u) => (/^https?:\/\//i.test(String(u || "")) ? String(u) : "#");
const uid = () => Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
const fmtNum = (n) => new Intl.NumberFormat("da-DK").format(n ?? 0);
const _df = new Intl.DateTimeFormat("da-DK", { day: "numeric", month: "short", year: "numeric" });
const fmtDate = (d) => { if (!d) return "Uden dato"; const x = new Date(d); return isNaN(x) ? d : _df.format(x); };
// Afgørelsesdato; "ca." når datoen er skønnet (scraperen gav en fallback-dato)
const fmtD = (x) => (x && x.date_estimated && x.date ? "ca. " : "") + fmtDate(x && x.date);

const store = {
  get(k, d) { try { const v = localStorage.getItem("ejnar." + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem("ejnar." + k, JSON.stringify(v)); } catch { /* privat tilstand */ } },
  del(k) { try { localStorage.removeItem("ejnar." + k); } catch { /* ignore */ } },
};

const ICONS = {
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  chat: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
  bookmark: '<path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>',
  up: '<path d="M12 19V5M5 12l7-7 7 7"/>',
  x: '<path d="M18 6 6 18M6 6l12 12"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  ext: '<path d="M15 3h6v6M10 14 21 3M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
  copy: '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
  spark: '<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/><path d="M19 17v4M17 19h4"/>',
  alert: '<path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  trash: '<path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"/>',
  out: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>',
  moon: '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  down: '<path d="m6 9 6 6 6-6"/>',
  scale: '<path d="M12 3v18M7 21h10M5 7h14M5 7l-3 7a3 3 0 0 0 6 0zM19 7l-3 7a3 3 0 0 0 6 0z"/>',
  doc: '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6M8 13h8M8 17h5"/>',
  retry: '<path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/>',
  chart: '<path d="M3 3v18h18"/><path d="M7 16v-5M12 16V8M17 16v-9"/>',
  thumbUp: '<path d="M7 10v11H4a1 1 0 0 1-1-1v-9a1 1 0 0 1 1-1h3zM7 10l4-7a2 2 0 0 1 3 2l-1 5h5.5a2 2 0 0 1 2 2.4l-1.6 7A2 2 0 0 1 16.9 21H7"/>',
  thumbDown: '<path d="M17 14V3h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1h-3zM17 14l-4 7a2 2 0 0 1-3-2l1-5H5.5a2 2 0 0 1-2-2.4l1.6-7A2 2 0 0 1 7.1 3H17"/>',
  quote: '<path d="M7 7h4v4c0 3-1 5-4 6M15 7h4v4c0 3-1 5-4 6"/>',
};
const icon = (n, cls = "") => `<svg class="i ${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[n] || ""}</svg>`;

const OUTCOMES = ["Medhold", "Delvis medhold", "Ikke medhold", "Afvist", "Ukendt"];
const OUT_KEY = { "Medhold": "medhold", "Delvis medhold": "delvis", "Ikke medhold": "ikke", "Afvist": "afvist", "Ukendt": "ukendt" };
const badge = (o) => `<span class="badge o-${OUT_KEY[o] || "ukendt"}">${esc(o || "Ukendt")}</span>`;

const SUGGESTIONS = [
  { k: "Praksis", q: "Hvornår dækker ejerskifteforsikringen skimmelsvamp i kælderen?" },
  { k: "Tilstandsrapport", q: "Hvornår er en skade undtaget, fordi forholdet er beskrevet i tilstandsrapporten?" },
  { k: "Erstatning", q: "Hvordan fastsætter nævnet fradrag for forbedring ved udskiftning af et tag?" },
  { k: "Ulovlige forhold", q: "Hvad kræves der for dækning af ulovlige forhold uden byggetilladelse?" },
];

// Advarsel om personoplysninger: spørgsmål sendes til den valgte AI-udbyder.
const PII = [
  ["CPR-nummer", /\b[0-3]\d[01]\d\d{2}[-\s]?\d{4}\b/],
  ["e-mailadresse", /\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b/],
  ["telefonnummer", /(?:\+45\s?)?\b\d{2}\s?\d{2}\s?\d{2}\s?\d{2}\b/],
  ["adresse", /\b[A-ZÆØÅ][a-zæøå]+(?:vej|gade|allé|alle|vænge|parken|stræde|plads|boulevard|toften)\s+\d+/],
];
function piiHits(text) {
  return PII.filter(([, rx]) => rx.test(text || "")).map(([label]) => label);
}
function piiWarning(text) {
  const hits = piiHits(text);
  return hits.length ? `<div class="pii">${icon("alert")}<span>Teksten ser ud til at indeholde ${hits.join(" og ")}. Spørgsmål sendes til en AI-udbyder – anonymisér navne, adresser og numre.</span></div>` : "";
}

// AKF-titler er et resumé af sagen. Første sætning bliver overskrift, men den
// stereotype indledning ("Klager over afslag på dækning for …") skæres af, så
// overskriften siger hvad sagen handler om.
const ABBR = /(?:^|\s)(?:bl\.a|jf|f\.eks|fx|ca|nr|kr|pkt|stk|mv|m\.v|evt|inkl|ifm|vedr|mht|dvs|pga|o\.l|m\.m|bl|a)$/i;
function splitTitle(t) {
  t = String(t || "").trim();
  const rx = /[.!?](?=\s+[A-ZÆØÅ0-9"“])/g;
  let m;
  while ((m = rx.exec(t))) {
    if (m.index < 20 || ABBR.test(t.slice(Math.max(0, m.index - 6), m.index))) continue;
    return [t.slice(0, m.index), t.slice(m.index + 1).trim()];
  }
  return [t.replace(/\.$/, ""), ""];
}
function headline(t) {
  const [first] = splitTitle(t);
  let h = first
    .replace(/^ejerskifte\w*\s*[-–:]\s*/i, "")
    .replace(/^klager(?:en)?\s+(?:i forbindelse med (?:en\s+)?ejerskifteforsikring\s+)?(?:klager\s+)?over\s+/i, "")
    .replace(/^(?:selskabets?\s+|forsikringsselskabets?\s+)?(?:afslag|afvisning|nægtelse|afvisninger)\s+(?:på|af)\s+(?:at\s+yde\s+)?(?:forsikrings)?dækning(?:en)?\s+(?:for|af|på|til|vedrørende|vedr\.)\s+(?:bl\.\s?a\.?\s+)?/i, "");
  h = h.trim() || first;
  return h.charAt(0).toUpperCase() + h.slice(1);
}

// ── Tilstand ─────────────────────────────────────────────────────────────────
const state = {
  key: store.get("key", ""),
  theme: store.get("theme", ""),
  view: store.get("view", "assistant"),
  meta: null,
  health: null,
  threads: store.get("threads", []),
  activeId: null,
  focusTurn: null,
  hotCite: null,
  draft: "",
  filters: { outcomes: [], defect_types: [], companies: [], coverage: [], year_from: null, year_to: null, ...store.get("filters", {}) },
  pop: null,
  popQuery: "",
  insight: { q: "", data: null, loading: false, error: "", ran: false },
  assess: { facts: "", data: null, loading: false, error: "" }, // bevidst ikke i localStorage
  miljo: { text: "", dtype: "", model: false, data: null, loading: false, error: "", fileName: "" }, // gemmes ikke

  search: { q: "", mode: "keyword", results: [], total: 0, counts: {}, loading: false, error: "", ran: false },
  reader: null,
  saved: store.get("saved", {}),
  navOpen: false,
  booting: false,
};
const saveThreads = () => store.set("threads", state.threads.slice(0, 60));
const activeThread = () => state.threads.find((t) => t.id === state.activeId) || null;
if (state.theme) document.documentElement.dataset.theme = state.theme;

// ── API ──────────────────────────────────────────────────────────────────────
class ApiError extends Error { constructor(status, msg) { super(msg); this.status = status; } }

async function api(path, { method = "GET", body, signal } = {}) {
  const r = await fetch(path, {
    method, signal,
    headers: { "X-API-Key": state.key, ...(body ? { "Content-Type": "application/json" } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (r.status === 401) { logout("Din adgangsnøgle blev afvist. Log ind igen."); throw new ApiError(401, "Ikke logget ind"); }
  if (!r.ok) {
    let detail = r.statusText;
    try { const j = await r.json(); detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch { /* ikke JSON */ }
    throw new ApiError(r.status, detail);
  }
  return r;
}
const apiJson = async (path, opts) => (await api(path, opts)).json();

function filtersBody(f = state.filters) {
  return {
    outcomes: f.outcomes, defect_types: f.defect_types, companies: f.companies, coverage: f.coverage || [],
    year_from: f.year_from || null, year_to: f.year_to || null,
  };
}
const activeFilterCount = () => {
  const f = state.filters;
  return f.outcomes.length + f.defect_types.length + f.companies.length + (f.coverage || []).length + (f.year_from || f.year_to ? 1 : 0);
};

// ── Render: skal og navigation ───────────────────────────────────────────────
const app = $("#app");

function render() {
  if (!state.key) return renderLogin();
  if (!state.meta) return renderBoot();
  const main = $(".main");
  const scroll = main ? main.scrollTop : 0;
  const focused = document.activeElement;
  const focusSel = focused?.dataset?.focus ? `[data-focus="${focused.dataset.focus}"]` : null;
  const caret = focused && "selectionStart" in focused ? focused.selectionStart : null;

  app.innerHTML = `
    <div class="shell ${state.navOpen ? "nav-open" : ""}">
      ${renderSidebar()}
      <main class="main" id="main">
        <div class="mobile-bar">
          <button class="icon-btn" data-act="nav" aria-label="Menu">${icon("menu")}</button>
          <span class="brand-name">Ejnar</span>
        </div>
        ${({ search: renderSearch, saved: renderSaved, insight: renderInsight, assess: renderAssess, miljo: renderMiljo }[state.view] || renderAssistant)()}
      </main>
    </div>
    ${state.reader ? renderReader() : ""}`;

  const m = $(".main");
  if (m) m.scrollTop = scroll;
  if (focusSel) {
    const el = $(focusSel);
    if (el) { el.focus({ preventScroll: true }); if (caret != null && "setSelectionRange" in el) try { el.setSelectionRange(caret, caret); } catch { /* ok */ } }
  }
  autosize();
}

function renderSidebar() {
  const nav = (v, ic, label, count) => `
    <button class="nav-item" data-act="view" data-v="${v}" ${state.view === v ? 'aria-current="page"' : ""}>
      ${icon(ic)}<span>${label}</span>${count != null ? `<span class="count">${count}</span>` : ""}
    </button>`;
  const nSaved = Object.keys(state.saved).length;
  const threads = state.threads.length
    ? state.threads.map((t) => `
        <div class="thread-item" role="button" tabindex="0" data-act="open-thread" data-id="${t.id}" ${t.id === state.activeId && state.view === "assistant" ? 'aria-current="true"' : ""}>
          <span>${esc(t.title)}</span>
          <button class="del" data-act="del-thread" data-id="${t.id}" aria-label="Slet samtale">${icon("x")}</button>
        </div>`).join("")
    : `<div class="side-empty">Dine samtaler gemmes her.</div>`;
  const h = state.health;
  const llmOk = !!h?.llm;
  return `
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">E</div>
        <div><div class="brand-name">Ejnar</div><div class="brand-sub">Ejerskifteforsikring · AKF</div></div>
      </div>
      <button class="new-btn" data-act="new">${icon("plus")}<span>Nyt spørgsmål</span><kbd>N</kbd></button>
      <nav class="nav">
        ${nav("assistant", "chat", "Assistent")}
        ${nav("search", "search", "Praksissøgning", fmtNum(state.meta.decisions))}
        ${nav("assess", "scale", "Lignende sager")}
        ${nav("insight", "chart", "Indsigt")}
        ${nav("saved", "bookmark", "Gemte kendelser", nSaved || null)}
        ${nav("miljo", "doc", "Miljøjuristen")}
      </nav>
      <div class="side-label">Seneste</div>
      <div class="threads">${threads}</div>
      <div class="side-foot">
        <div class="status" title="${esc(h?.llm || "Ingen sprogmodel konfigureret")}">
          <span class="dot ${llmOk ? "" : "warn"}"></span>
          <span>${fmtNum(state.meta.decisions)} kendelser · ${h?.search_mode === "hybrid" ? "hybrid søgning" : "nøgleordssøgning"}</span>
        </div>
        <button class="nav-item" data-act="theme">${icon(isDark() ? "sun" : "moon")}<span>${isDark() ? "Lyst tema" : "Mørkt tema"}</span></button>
        <button class="nav-item" data-act="logout">${icon("out")}<span>Log ud</span></button>
      </div>
    </aside>`;
}
const isDark = () => state.theme ? state.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;

// ── Filtre ───────────────────────────────────────────────────────────────────
function renderFilters() {
  const f = state.filters;
  const pill = (key, label, values, fmt) => {
    const active = values.length > 0;
    const val = active ? (values.length === 1 ? fmt(values[0]) : `${fmt(values[0])} +${values.length - 1}`) : "";
    return `
      <span style="position:relative">
        <button class="pill ${active ? "active" : ""}" data-act="pop" data-k="${key}" aria-expanded="${state.pop === key}">
          ${active ? "" : icon("plus")}<span>${label}</span>${active ? `<span class="val">${esc(val)}</span><span class="x" data-act="clear-filter" data-k="${key}" aria-label="Fjern filter">${icon("x")}</span>` : ""}
        </button>
        ${state.pop === key ? renderPop(key) : ""}
      </span>`;
  };
  const years = f.year_from || f.year_to ? [`${f.year_from || state.meta.year_min}–${f.year_to || state.meta.year_max}`] : [];
  return `<div class="filters">
    ${pill("outcomes", "Udfald", f.outcomes, (x) => x)}
    ${pill("defect_types", "Mangeltype", f.defect_types, (x) => x)}
    ${pill("companies", "Selskab", f.companies, (x) => x.replace(/,.*$/, ""))}
    ${pill("coverage", "Dækning", f.coverage || [], (x) => x)}
    ${pill("years", "År", years, (x) => x)}
  </div>`;
}

function renderPop(key) {
  if (key === "years") {
    const f = state.filters;
    return `<div class="pop" data-stop>
      <div class="years">
        <label>Fra<input type="number" inputmode="numeric" data-yr="from" min="${state.meta.year_min}" max="${state.meta.year_max}" placeholder="${state.meta.year_min}" value="${f.year_from || ""}"></label>
        <label>Til<input type="number" inputmode="numeric" data-yr="to" min="${state.meta.year_min}" max="${state.meta.year_max}" placeholder="${state.meta.year_max}" value="${f.year_to || ""}"></label>
      </div>
      <div class="pop-foot">
        <button class="btn ghost sm" data-act="clear-filter" data-k="years">Nulstil</button>
        <button class="btn primary sm" data-act="apply-years">Anvend</button>
      </div>
    </div>`;
  }
  const all = key === "outcomes" ? OUTCOMES : key === "defect_types" ? state.meta.defect_types
    : key === "coverage" ? (state.meta.coverage || ["Udvidet", "Basis", "Ikke angivet"]) : state.meta.companies;
  const counts = key === "outcomes" ? state.meta.outcome_counts || {} : key === "coverage" ? state.meta.coverage_counts || {} : {};
  const q = state.popQuery.toLowerCase();
  const list = all.filter((x) => !q || x.toLowerCase().includes(q));
  const sel = new Set(state.filters[key]);
  return `<div class="pop" data-stop>
    ${all.length > 8 ? `<input type="search" placeholder="Søg…" data-popq data-focus="popq" value="${esc(state.popQuery)}">` : ""}
    <div class="pop-list" role="listbox" aria-multiselectable="true">
      ${list.map((x) => `
        <button class="opt" role="option" aria-checked="${sel.has(x)}" data-act="toggle-opt" data-k="${key}" data-v="${esc(x)}">
          <span class="check">${icon("check")}</span><span>${esc(x)}</span>${counts[x] != null ? `<span class="n num">${fmtNum(counts[x])}</span>` : ""}
        </button>`).join("") || `<div class="side-empty">Ingen match</div>`}
    </div>
    ${sel.size ? `<div class="pop-foot"><button class="btn ghost sm" data-act="clear-filter" data-k="${key}">Ryd</button><button class="btn sm" data-act="close-pop">Færdig</button></div>` : ""}
  </div>`;
}

function filtersChanged() {
  store.set("filters", state.filters);
  if (state.view === "search") runSearch();
  else if (state.view === "insight") runStats();
  else if (state.view === "assess" && state.assess.data) runAssess();
  else render();
}

// ── Assistent ────────────────────────────────────────────────────────────────
function composer(dock) {
  const busy = activeThread()?.messages.some((m) => m.status === "streaming");
  return `
    <form class="composer" data-act="ask">
      <label class="sr" for="q">Spørgsmål</label>
      <textarea id="q" data-focus="composer" rows="1" placeholder="${dock ? "Stil et opfølgende spørgsmål…" : "Spørg om praksis, fx “Hvornår dækkes fugt i krybekælder?”"}">${esc(state.draft)}</textarea>
      <div class="composer-bar">
        ${renderFilters()}
        <button class="send" type="submit" aria-label="Send" ${!state.draft.trim() || busy ? "disabled" : ""}>${icon("up")}</button>
      </div>
      <div class="pii-slot">${piiWarning(state.draft)}</div>
    </form>`;
}

function renderAssistant() {
  const t = activeThread();
  if (!t || !t.messages.length) {
    return `
      <section class="hero">
        <div class="eyebrow">${icon("scale")}<span>Ankenævnet for Forsikring · ${fmtNum(state.meta.decisions)} kendelser ${state.meta.year_min}–${state.meta.year_max}</span></div>
        <h1 class="h1">Hvad siger <em>praksis</em>?</h1>
        <p class="lede">Stil et juridisk spørgsmål om ejerskifteforsikring. Ejnar finder de relevante kendelser, analyserer dem og svarer med kildehenvisning til hver påstand.</p>
        ${composer(false)}
        ${state.health && !state.health.llm ? `<div class="warn-box">${icon("alert")}<div>Der er ingen sprogmodel konfigureret på serveren, så assistenten kan ikke svare. Praksissøgningen virker stadig.</div></div>` : ""}
        <div class="suggest">
          ${SUGGESTIONS.map((s) => `<button class="sugg" data-act="suggest" data-q="${esc(s.q)}"><small>${s.k}</small>${esc(s.q)}</button>`).join("")}
        </div>
      </section>`;
  }
  const turns = [];
  for (let i = 0; i < t.messages.length; i++) {
    const m = t.messages[i];
    if (m.role !== "user") continue;
    turns.push({ q: m, a: t.messages[i + 1], idx: i + 1 });
  }
  const focusIdx = state.focusTurn ?? turns[turns.length - 1]?.idx;
  const focusMsg = t.messages[focusIdx];
  return `
    <div class="thread">
      <div class="thread-main">
        <div class="thread-inner">
          ${turns.map((tr) => renderTurn(tr)).join("")}
        </div>
        <div class="dock">${composer(true)}<div class="disclaimer">Ejnar kan tage fejl. Kontrollér altid konklusioner mod de citerede kendelser.</div></div>
      </div>
      <aside class="aside" aria-label="Kilder"><div class="aside-inner">${renderSources(focusMsg, focusIdx)}</div></aside>
    </div>`;
}

function filterChips(f) {
  if (!f) return "";
  const parts = [...(f.outcomes || []), ...(f.defect_types || []), ...(f.companies || []), ...(f.coverage || []).map((c) => `${c} dækning`)];
  if (f.year_from || f.year_to) parts.push(`${f.year_from || "…"}–${f.year_to || "…"}`);
  return parts.length ? `<div class="q-filters">${parts.map((p) => `<span class="tag">${esc(p)}</span>`).join("")}</div>` : "";
}

function renderTurn({ q, a, idx }) {
  let body = "";
  if (!a) body = "";
  else if (a.status === "error") {
    body = `<div class="err-box">${esc(a.error || "Noget gik galt.")}</div>
      <div class="turn-actions"><button class="btn ghost sm" data-act="retry" data-i="${idx}">${icon("retry")}Prøv igen</button></div>`;
  } else {
    const steps = a.status === "streaming" && !a.content ? renderSteps(a) : "";
    const suspect = a.suspect?.length ? `
      <div class="warn-box">${icon("alert")}<div><strong>Citatkontrol:</strong> følgende citat${a.suspect.length > 1 ? "er" : ""} kunne ikke genfindes ordret i kilderne og bør efterprøves.
        <ul>${a.suspect.slice(0, 4).map((s) => `<li>“${esc(s.length > 160 ? s.slice(0, 160) + "…" : s)}”</li>`).join("")}</ul></div></div>` : "";
    const actions = a.status === "done" ? `
      <div class="turn-actions">
        <button class="btn ghost sm" data-act="copy-answer" data-i="${idx}">${icon("copy")}Kopiér med referencer</button>
        <button class="btn ghost sm" data-act="print">${icon("doc")}Print / PDF</button>
        <button class="btn ghost sm" data-act="retry" data-i="${idx}">${icon("retry")}Generér igen</button>
        <span class="fb">${feedbackButtons(a, idx)}</span>
      </div>${a.feedback === "form" ? feedbackForm(idx) : ""}` : "";
    const conflicts = a.conflicts?.length ? `
      <div class="warn-box">${icon("alert")}<div><strong>Udfaldskontrol:</strong> svaret gengiver udfaldet af ${a.conflicts.length > 1 ? "disse kendelser" : "denne kendelse"} anderledes end nævnets afgørelse. Læs kendelsen.
        <ul>${a.conflicts.slice(0, 4).map((c) => `<li>[Kilde ${c.source}]: svaret siger „${esc(c.claimed)}“, kendelsen er „${esc(c.actual)}“</li>`).join("")}</ul></div></div>` : "";
    body = `${steps}<div class="answer" data-answer="${idx}">${a.content ? withCiteTitles(md(a.content), a.sources) : ""}${a.status === "streaming" && a.content ? '<span class="caret"></span>' : ""}</div>${conflicts}${suspect}${actions}`;
  }
  return `<article class="turn" data-turn="${idx}">
      <h2 class="q ${q.content.length > 160 ? "long" : ""}">${esc(q.content)}</h2>${filterChips(q.filters)}
      ${body}
    </article>`;
}

function renderSteps(a) {
  const s = (label, st) => `<div class="step ${st}"><span class="ic">${st === "done" ? icon("check") : st === "active" ? '<span class="spinner"></span>' : ""}</span>${label}</div>`;
  const got = !!a.sources;
  return `<div class="steps">
    ${s("Forstår spørgsmålet og planlægger søgningen", got ? "done" : "active")}
    ${s(got ? `Fandt ${a.sources.length} relevante kendelser` : "Søger i kendelserne", got ? "done" : "")}
    ${s("Analyserer praksis og skriver svar", got ? "active" : "")}
  </div>`;
}

function renderSources(msg, idx) {
  if (!msg || msg.role !== "assistant") return "";
  if (!msg.sources) {
    return `<div class="aside-h"><h3>Kilder</h3></div>${msg.status === "streaming" ? '<div class="skel"></div><div class="skel"></div><div class="skel"></div>' : '<div class="aside-empty">Ingen kilder.</div>'}`;
  }
  const cited = new Set(citedNumbers(msg.content || ""));
  const done = msg.status === "done";
  const ordered = [...msg.sources].sort((x, y) => (cited.has(y.n) - cited.has(x.n)) || x.n - y.n);
  return `
    <div class="aside-h"><h3>Kilder</h3><span>${done ? `${cited.size} citeret af ${msg.sources.length}` : `${msg.sources.length} fundet`}</span></div>
    ${ordered.map((s) => {
      const head = headline(s.title);
      const isCited = cited.has(s.n);
      return `<button class="src ${isCited ? "cited" : done ? "dim" : ""} ${state.hotCite === `${idx}:${s.n}` ? "hot" : ""}" data-act="open-doc" data-id="${esc(s.id)}" data-src="${idx}:${s.n}">
        <div class="src-top"><span class="src-n">${s.n}</span><span class="meta num">${esc(s.case_number || "—")}</span>${badge(s.outcome)}</div>
        <div class="src-title">${esc(head)}</div>
        <div class="meta"><span>${fmtD(s)}</span>${s.company ? `<span class="sep"></span><span>${esc(s.company.replace(/,.*$/, ""))}</span>` : ""}</div>
      </button>`;
    }).join("")}`;
}

// Kildechips viser AKF-journalnummer og dato ved hover, så de kan citeres i breve.
function withCiteTitles(html, sources) {
  if (!sources?.length) return html;
  const byN = Object.fromEntries(sources.map((s) => [String(s.n), s]));
  return html.replace(/data-n="(\d+)" aria-label="Kilde \d+"/g, (m, n) => {
    const s = byN[n];
    return s ? `data-n="${n}" aria-label="Kilde ${n}: AKF ${esc(s.case_number || "")}" title="AKF ${esc(s.case_number || "u.nr.")} · ${fmtD(s)} · ${esc(s.outcome || "")}"` : m;
  });
}

// Kildenumre i en henvisning: "3", "3, 5 og 7", "2–8" (interval) og "14, basisdækning"
function refNumbers(g) {
  const out = [];
  for (const m of String(g).matchAll(/(\d+)\s*[–—-]\s*(\d+)|\d+/g)) {
    const a = +(m[1] || m[0]), b = +(m[2] || m[0]);
    for (let n = a; n <= Math.min(b, a + 30); n++) if (!out.includes(n)) out.push(n);
  }
  return out;
}
const REF_RE = /\[Kilde[r]?\s+(\d[^\]]{0,80})\]/gi;
function citedNumbers(text) {
  const out = [];
  for (const m of text.matchAll(REF_RE)) for (const n of refNumbers(m[1])) if (!out.includes(n)) out.push(n);
  return out;
}
// Tekst i en henvisning ud over numrene, fx "basisdækning" i "[Kilde 14, basisdækning]"
const refNote = (g) => String(g).replace(/\d+\s*[–—-]\s*\d+|\d+|,|\bog\b|\bKilde[r]?\b/gi, " ").replace(/\s+/g, " ").trim();

// Lille, sikker markdown-renderer: escaper først og tillader kun et fast sæt elementer.
function inline(s) {
  s = esc(s);
  s = s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/(^|[\s(])\*(?!\s)([^*]+?)\*(?=[\s).,;:!?]|$)/g, "$1<em>$2</em>");
  s = s.replace(REF_RE, (_, g) => {
    const note = refNote(g);
    return refNumbers(g).map((n) => `<button class="cite" data-act="cite" data-n="${n}" aria-label="Kilde ${n}">${n}</button>`).join("") +
      (note ? ` <span class="cite-note">(${note})</span>` : "");
  });
  return s;
}
function md(src) {
  const lines = String(src || "").replace(/\r/g, "").split("\n");
  let html = "", list = null, para = [];
  const flush = () => { if (para.length) { html += `<p>${inline(para.join(" "))}</p>`; para = []; } };
  const close = () => { if (list) { html += `</${list}>`; list = null; } };
  for (const raw of lines) {
    const line = raw.trimEnd();
    let m;
    if (!line.trim()) { flush(); close(); continue; }
    if ((m = line.match(/^(#{1,4})\s+(.*)$/))) { flush(); close(); const l = Math.min(m[1].length + 1, 4); html += `<h${l}>${inline(m[2].replace(/\*\*/g, ""))}</h${l}>`; continue; }
    if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) { flush(); close(); html += "<hr>"; continue; }
    if ((m = line.match(/^\s*[-*•]\s+(.*)$/))) { flush(); if (list !== "ul") { close(); html += "<ul>"; list = "ul"; } html += `<li>${inline(m[1])}</li>`; continue; }
    if ((m = line.match(/^\s*\d+[.)]\s+(.*)$/))) { flush(); if (list !== "ol") { close(); html += "<ol>"; list = "ol"; } html += `<li>${inline(m[1])}</li>`; continue; }
    if ((m = line.match(/^>\s?(.*)$/))) { flush(); close(); html += `<blockquote>${inline(m[1])}</blockquote>`; continue; }
    close(); para.push(line.trim());
  }
  flush(); close();
  return html;
}

// ── Spørg ────────────────────────────────────────────────────────────────────
async function ask(question, { reuseIdx } = {}) {
  question = question.trim();
  if (!question) return;
  let t = activeThread();
  if (!t) {
    t = { id: uid(), title: question.slice(0, 80), created: Date.now(), messages: [] };
    state.threads.unshift(t);
    state.activeId = t.id;
  }
  const filters = JSON.parse(JSON.stringify(state.filters));
  let a;
  if (reuseIdx != null) {
    a = t.messages[reuseIdx];
    Object.assign(a, { content: "", sources: null, suspect: [], conflicts: [], status: "streaming", error: "" });
  } else {
    t.messages.push({ role: "user", content: question, filters });
    a = { role: "assistant", content: "", sources: null, suspect: [], status: "streaming" };
    t.messages.push(a);
  }
  const aIdx = t.messages.indexOf(a);
  state.focusTurn = null;
  state.draft = "";
  state.view = "assistant";
  render();
  scrollToTurn(aIdx);

  const history = t.messages.slice(0, aIdx - 1).filter((m) => m.status !== "error").slice(-10).map((m) => ({
    role: m.role, content: m.content.slice(0, 18000), source_ids: m.role === "assistant" ? (m.sources || []).map((s) => s.id) : [],
  }));

  let raf = 0;
  const paint = () => {
    raf = 0;
    const el = $(`[data-answer="${aIdx}"]`);
    if (!el || !a.content) return render();
    el.innerHTML = md(a.content) + '<span class="caret"></span>';
    $(".steps", el.parentElement)?.remove();
  };
  try {
    const r = await api("/v1/answer", { method: "POST", body: { question, history, filters: filtersBody(filters), stream: true } });
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let cut;
      while ((cut = buf.indexOf("\n\n")) >= 0) {
        const chunk = buf.slice(0, cut); buf = buf.slice(cut + 2);
        const ev = /^event: (.*)$/m.exec(chunk)?.[1];
        const data = /^data: (.*)$/m.exec(chunk)?.[1];
        if (!ev || !data) continue;
        const d = JSON.parse(data);
        if (ev === "sources") { a.sources = d.sources; render(); }
        else if (ev === "delta") { a.content += d.text; if (!raf) raf = requestAnimationFrame(paint); }
        else if (ev === "done") { a.content = d.answer; a.suspect = d.suspect_quotes || []; a.conflicts = d.outcome_conflicts || []; a.status = "done"; }
        else if (ev === "error") { throw new Error(d.detail); }
      }
    }
    if (a.status !== "done") a.status = a.content ? "done" : "error";
    if (!a.content) a.error = "Modellen returnerede intet svar.";
  } catch (e) {
    if (e.status === 401) return;
    a.status = "error";
    a.error = e.status === 503 ? e.message : `Kunne ikke hente svar: ${e.message}`;
  }
  cancelAnimationFrame(raf);
  saveThreads();
  render();
}

function scrollToTurn(idx) {
  requestAnimationFrame(() => $(`[data-turn="${idx}"]`)?.scrollIntoView({ behavior: "smooth", block: "start" }));
}

// ── Feedback (pilot) ─────────────────────────────────────────────────────────
const FB_REASONS = [
  ["forkert_gengivelse", "En kendelse er gengivet forkert"],
  ["mangler_kendelse", "En vigtig kendelse mangler"],
  ["irrelevante_kilder", "Kilderne passer ikke til spørgsmålet"],
  ["for_generelt", "For generelt / for meget almen viden"],
  ["for_langt", "For langt"],
  ["andet", "Andet"],
];
function feedbackButtons(a, idx) {
  if (a.feedback === "up" || a.feedback === "sent") return `<span class="fb-thanks">${icon("check")}Tak for feedback</span>`;
  return `<button class="btn ghost sm icon-only" data-act="fb-up" data-i="${idx}" title="Brugbart" aria-label="Brugbart">${icon("thumbUp")}</button>` +
    `<button class="btn ghost sm icon-only ${a.feedback === "form" ? "on" : ""}" data-act="fb-down" data-i="${idx}" title="Ikke brugbart" aria-label="Ikke brugbart">${icon("thumbDown")}</button>`;
}
function feedbackForm(idx) {
  return `<form class="fb-form" data-act="fb-send" data-i="${idx}">
    <strong>Hvad var galt?</strong>
    <div class="fb-reasons">${FB_REASONS.map(([k, l]) => `<label><input type="checkbox" name="r" value="${k}"> ${l}</label>`).join("")}</div>
    <textarea name="comment" rows="2" maxlength="2000" placeholder="Evt. kommentar – fx hvilken kendelse der mangler, eller hvad der er forkert (undgå personoplysninger)"></textarea>
    <div class="fb-bar"><button class="btn ghost sm" type="button" data-act="fb-cancel" data-i="${idx}">Annullér</button><button class="btn primary sm" type="submit">Send</button></div>
  </form>`;
}
async function sendFeedback(idx, rating, reasons = [], comment = "") {
  const t = activeThread(); const a = t?.messages[idx]; if (!a) return;
  const question = t.messages[idx - 1]?.content || "";
  try {
    await apiJson("/v1/feedback", { method: "POST", body: {
      rating, question, answer: a.content || "", source_ids: (a.sources || []).map((x) => x.id), reasons, comment } });
    a.feedback = rating === "up" ? "up" : "sent"; saveThreads(); render(); toast("Tak – feedbacken er gemt");
  } catch (e) { toast("Feedback kunne ikke sendes: " + e.message); }
}

function copyAnswer(idx) {
  const a = activeThread()?.messages[idx];
  if (!a) return;
  const byN = Object.fromEntries((a.sources || []).map((s) => [s.n, s]));
  const text = a.content.replace(REF_RE, (_, g) => {
    const refs = refNumbers(g).map((n) => byN[n]).filter(Boolean).map((s) => `AKF ${s.case_number || "u.nr."}, ${fmtD(s)}`);
    return refs.length ? `(${refs.join("; ")})` : "";
  });
  const cited = citedNumbers(a.content).map((n) => byN[n]).filter(Boolean);
  const refs = cited.length ? "\n\nKilder:\n" + cited.map((s) => `- AKF ${s.case_number || "u.nr."} (${fmtD(s)}): ${s.link}`).join("\n") : "";
  copy(text + refs, "Svar kopieret med referencer");
}

// ── Søgning ──────────────────────────────────────────────────────────────────
const MODES = [
  ["keyword", "Relevans", "Hybrid rangering af ord, afsnit og betydning. Hurtig og uden AI-omkostning."],
  ["exact", "Ordret", "Nøjagtig frase i titel eller tekst. Tomt felt viser nyeste. Sagsnumre virker også."],
  ["smart", "AI-søgning", "Omskriver søgningen, kombinerer semantisk og ordbaseret søgning og rerangerer med AI."],
];
let searchSeq = 0;

async function runSearch({ more = false } = {}) {
  const s = state.search;
  const seq = ++searchSeq;
  s.loading = true; s.error = ""; s.ran = true;
  if (!more) { s.results = []; s.total = 0; s.counts = {}; }
  render();
  try {
    const d = await apiJson("/v1/search", {
      method: "POST",
      body: { query: s.q, mode: s.q.trim() ? s.mode : "exact", filters: filtersBody(), limit: 25, offset: more ? s.results.length : 0 },
    });
    if (seq !== searchSeq) return;
    s.results = more ? s.results.concat(d.results) : d.results;
    s.total = d.total; s.counts = d.outcome_counts || {};
    s.lastQ = d.query; s.lastMode = d.mode;
  } catch (e) {
    if (seq !== searchSeq) return;
    s.error = e.message;
  }
  s.loading = false;
  render();
}

function renderDist(counts, total, clickable, label = "kendelser") {
  if (!total) return "";

  const seg = OUTCOMES.filter((o) => counts[o]).map((o) => `<div class="c-${OUT_KEY[o]}" style="flex-grow:${counts[o]}" title="${o}: ${counts[o]}"></div>`).join("");
  const legend = OUTCOMES.filter((o) => counts[o]).map((o) => {
    const inner = `<i class="c-${OUT_KEY[o]}"></i>${o} <span class="pct num">${Math.round((100 * counts[o]) / total)}%</span>`;
    return clickable ? `<button data-act="only-outcome" data-v="${o}" title="Vis kun ${o.toLowerCase()}">${inner}</button>` : `<span>${inner}</span>`;
  }).join("");
  return `<div class="dist">
    <div class="dist-h"><span><strong class="num">${fmtNum(total)}</strong> ${label}</span><span>Klager fik helt eller delvist medhold i <strong class="num">${klagerRate(counts, total)}%</strong> af de realitetsbehandlede</span></div>
    <div class="bar">${seg}</div>
    <div class="legend">${legend}</div>
  </div>`;
}

function renderResult(d, q) {
  const head = headline(d.title);
  const rest = splitTitle(d.title)[1];
  const snip = q && d.snippet && !/^[\d\s()/]+$/.test(q) && !d.title.toLowerCase().includes(q.toLowerCase()) ? `<div class="res-snip">${highlight(d.snippet, q)}</div>` : "";
  return `<button class="res" data-act="open-doc" data-id="${esc(d.id)}">
    <div class="res-head">${q ? highlight(head, q) : esc(head)}</div>
    ${rest ? `<div class="res-sum">${q ? highlight(rest, q) : esc(rest)}</div>` : ""}
    ${snip}
    <div class="meta"><span class="num">AKF ${esc(d.case_number || "—")}</span><span class="sep"></span><span>${fmtD(d)}</span>${d.company ? `<span class="sep"></span><span>${esc(d.company.replace(/,.*$/, ""))}</span>` : ""}</div>
    <div class="res-side">${badge(d.outcome)}${d.coverage && d.coverage !== "Ikke angivet" ? `<span class="tag">${esc(d.coverage)} dækning</span>` : ""}${(d.defect_types || []).slice(0, 2).map((t) => `<span class="tag">${esc(t)}</span>`).join("")}</div>
  </button>`;
}

function renderSearch() {
  const s = state.search;
  if (!s.ran && !s.loading) queueMicrotask(() => runSearch());
  const mode = MODES.find((m) => m[0] === s.mode);
  let body;
  if (s.error) body = `<div class="err-box">${esc(s.error)}</div>`;
  else if (s.loading && !s.results.length) body = '<div class="skel"></div><div class="skel"></div><div class="skel"></div><div class="skel"></div>';
  else if (!s.results.length) body = `<div class="empty">${icon("search")}<h3>Ingen kendelser fundet</h3><p>Prøv andre ord, skift til AI-søgning eller fjern et filter.</p></div>`;
  else {
    const capped = s.lastMode === "keyword" && s.total >= 200;
    body = `${renderDist(s.counts, s.total, true, capped ? "mest relevante kendelser" : s.lastMode === "smart" ? "udvalgte kendelser" : "kendelser")}
      <div class="results">${s.results.map((d) => renderResult(d, s.lastQ)).join("")}</div>
      ${s.results.length < s.total ? `<div class="more"><button class="btn" data-act="more" ${s.loading ? "disabled" : ""}>${s.loading ? '<span class="spinner"></span>' : ""}Vis flere · ${fmtNum(s.total - s.results.length)} tilbage</button></div>` : ""}`;
  }
  return `<section class="page">
    <div class="page-h"><div><h1 class="h2">Praksissøgning</h1><p class="page-sub">${fmtNum(state.meta.decisions)} kendelser fra Ankenævnet for Forsikring, ${state.meta.year_min}–${state.meta.year_max}</p></div></div>
    <form class="searchbar" data-act="search">
      ${icon("search")}
      <input type="search" data-focus="search" placeholder="Søg i kendelser, fx “fugt i krybekælder” eller et sagsnummer" value="${esc(s.q)}" aria-label="Søg">
      <div class="seg" role="group" aria-label="Søgemetode">
        ${MODES.map(([k, l]) => `<button type="button" data-act="mode" data-v="${k}" aria-pressed="${s.mode === k}">${l}</button>`).join("")}
      </div>
    </form>
    <div class="search-tools">${renderFilters()}<span class="mode-hint">${esc(mode[2])}</span></div>
    ${body}
  </section>`;
}

function renderSaved() {
  const items = Object.values(state.saved).sort((a, b) => (b.saved_at || 0) - (a.saved_at || 0));
  return `<section class="page">
    <div class="page-h"><div><h1 class="h2">Gemte kendelser</h1><p class="page-sub">Gemmes lokalt i denne browser.</p></div></div>
    ${items.length ? `<div class="results">${items.map((d) => renderResult(d, "")).join("")}</div>`
      : `<div class="empty">${icon("bookmark")}<h3>Ingen gemte kendelser endnu</h3><p>Åbn en kendelse og tryk “Gem” for at samle den her.</p></div>`}
  </section>`;
}

// ── Indsigt ──────────────────────────────────────────────────────────────────
let statsSeq = 0;
async function runStats() {
  const s = state.insight, seq = ++statsSeq;
  s.loading = true; s.error = ""; s.ran = true; render();
  try {
    const d = await apiJson("/v1/stats", { method: "POST", body: { query: s.q, filters: filtersBody() } });
    if (seq === statsSeq) s.data = d;
  } catch (e) { if (seq === statsSeq) s.error = e.message; }
  if (seq === statsSeq) { s.loading = false; render(); }
}

const pct = (a, b) => (b ? Math.round((100 * a) / b) : 0);
// Medholdsrate regnes af realitetsbehandlede sager: afviste (nævnet tog ikke
// stilling) og ukendte tæller hverken som tab eller gevinst for klager.
const decidedCount = (c, total) => total - (c["Afvist"] || 0) - (c["Ukendt"] || 0);
const klagerRate = (c, total) => pct((c["Medhold"] || 0) + (c["Delvis medhold"] || 0), decidedCount(c, total));
const OUT_CHART = OUTCOMES.slice(0, 4);

function niceMax(v) {
  if (v <= 5) return 5;
  const p = 10 ** Math.floor(Math.log10(v)), n = v / p;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * p;
}

function yearChart(rows) {
  if (!rows.length) return "";
  const max = niceMax(Math.max(...rows.map((r) => r.total)));
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(max * f));
  const every = rows.length > 16 ? 3 : rows.length > 9 ? 2 : 1;
  return `<div class="ychart" role="img" aria-label="Udfald pr. år, antal kendelser">
    <div class="ygrid">${ticks.map((t) => `<div style="bottom:${(100 * t) / max}%"><span class="num">${fmtNum(t)}</span></div>`).join("")}</div>
    <div class="ycols">
      ${rows.map((r, i) => `
        <div class="ycol" tabindex="0" data-tip="${esc(JSON.stringify(r))}">
          <div class="ystack" style="height:${(100 * r.total) / max}%">
            ${OUT_CHART.concat("Ukendt").filter((o) => r.counts[o]).map((o) => `<div class="c-${OUT_KEY[o]}" style="flex-grow:${r.counts[o]}"></div>`).join("")}
          </div>
          <span class="ylab num">${i % every === 0 || i === rows.length - 1 ? r.label : ""}</span>
        </div>`).join("")}
    </div>
    <div class="tip" hidden></div>
  </div>
  <table class="sr"><caption>Udfald pr. år</caption><tr><th>År</th><th>I alt</th>${OUT_CHART.map((o) => `<th>${o}</th>`).join("")}</tr>
    ${rows.map((r) => `<tr><td>${r.label}</td><td>${r.total}</td>${OUT_CHART.map((o) => `<td>${r.counts[o] || 0}</td>`).join("")}</tr>`).join("")}</table>`;
}

function breakdown(rows, key) {
  if (!rows.length) return '<div class="aside-empty">Ingen data.</div>';
  return `<div class="bd" role="table">
    <div class="bd-row bd-h" role="row"><span role="columnheader"></span><span role="columnheader" class="r">Sager</span><span role="columnheader">Udfaldsfordeling</span><span role="columnheader" class="r">Klager medhold</span></div>
    ${rows.map((r) => `
      <button class="bd-row" role="row" data-act="bd-filter" data-k="${key}" data-v="${esc(r.label)}" title="Filtrér på ${esc(r.label)}">
        <span class="bd-l" role="cell">${esc(key === "companies" ? r.label.replace(/,.*$/, "") : r.label)}</span>
        <span class="r num" role="cell">${fmtNum(r.total)}</span>
        <span class="bar" role="cell" aria-label="${OUT_CHART.map((o) => `${o} ${r.counts[o] || 0}`).join(", ")}">${OUTCOMES.filter((o) => r.counts[o]).map((o) => `<div class="c-${OUT_KEY[o]}" style="flex-grow:${r.counts[o]}"></div>`).join("")}</span>
        <span class="r num strong" role="cell">${klagerRate(r.counts, r.total)}%</span>
      </button>`).join("")}
  </div>`;
}

function renderInsight() {
  const s = state.insight;
  if (!s.ran && !s.loading) queueMicrotask(() => runStats());
  const d = s.data;
  let body;
  if (s.error) body = `<div class="err-box">${esc(s.error)}</div>`;
  else if (!d) body = '<div class="kpis">' + '<div class="skel" style="height:92px"></div>'.repeat(4) + '</div><div class="skel" style="height:280px"></div>';
  else if (!d.total) body = `<div class="empty">${icon("chart")}<h3>Ingen kendelser i udsnittet</h3><p>Fjern et filter eller ændr frasen.</p></div>`;
  else {
    const c = d.outcome_counts, years = d.by_year.map((r) => +r.label);
    const recent = d.by_year.filter((r) => +r.label >= Math.max(...years) - 4);
    const rTot = recent.reduce((a, r) => a + r.total, 0);
    const rC = {}; recent.forEach((r) => OUTCOMES.forEach((o) => (rC[o] = (rC[o] || 0) + (r.counts[o] || 0))));
    const kpi = (label, value, sub) => `<div class="kpi"><div class="kpi-l">${label}</div><div class="kpi-v num">${value}</div><div class="kpi-s">${sub}</div></div>`;
    body = `
      <div class="kpis ${s.loading ? "busy" : ""}">
        ${kpi("Kendelser i udsnittet", fmtNum(d.total), `${Math.min(...years)}–${Math.max(...years)}`)}
        ${kpi("Klager helt/delvist medhold", `${klagerRate(c, d.total)}%`, `af ${fmtNum(decidedCount(c, d.total))} realitetsbehandlede sager`)}
        ${kpi("Seneste 5 år", `${klagerRate(rC, rTot)}%`, `klager medhold i ${fmtNum(rTot)} sager`)}
        ${kpi("Afvist af nævnet", `${pct(c["Afvist"] || 0, d.total)}%`, "typisk pga. bevisførelse")}
      </div>
      <section class="card">
        <div class="card-h"><h3>Udfald pr. år</h3><div class="legend">${OUT_CHART.map((o) => `<span><i class="c-${OUT_KEY[o]}"></i>${o}</span>`).join("")}</div></div>
        ${yearChart(d.by_year)}
      </section>
      ${d.by_coverage?.length ? `<section class="card"><div class="card-h"><h3>Dækningstype</h3><span class="hint">Basis- eller udvidet ejerskifteforsikring, som angivet i kendelsen</span></div>${breakdown(d.by_coverage, "coverage")}</section>` : ""}
      <div class="grid2">
        <section class="card"><div class="card-h"><h3>Mangeltype</h3><span class="hint">Klik for at filtrere</span></div>${breakdown(d.by_defect, "defect_types")}</section>
        <section class="card"><div class="card-h"><h3>Forsikringsselskab</h3><span class="hint">Top 15 efter antal</span></div>${breakdown(d.by_company, "companies")}</section>
      </div>`;
  }
  return `<section class="page wide">
    <div class="page-h"><div><h1 class="h2">Indsigt</h1><p class="page-sub">Hvordan falder praksis ud? Afgræns med filtre eller en ordret frase.</p></div></div>
    <form class="searchbar" data-act="stats">${icon("search")}
      <input type="search" data-focus="stats" placeholder="Afgræns med en frase, fx “krybekælder” eller “asbest”" value="${esc(s.q)}" aria-label="Frase">
      <button class="btn sm" type="submit">Opdater</button>
    </form>
    <div class="search-tools">${renderFilters()}<span class="mode-hint">Udfald ses fra klagers side.</span></div>
    ${body}
  </section>`;
}

// ── Lignende sager ────────────────────────────────────────────────────────────
let assessSeq = 0;
async function runAssess() {
  const a = state.assess, seq = ++assessSeq;
  if (a.facts.trim().length < 20) { a.error = "Beskriv sagen med mindst et par sætninger."; return render(); }
  a.loading = true; a.error = ""; render();
  try {
    const d = await apiJson("/v1/assess", { method: "POST", body: { facts: a.facts, filters: filtersBody(), limit: 25 } });
    if (seq === assessSeq) a.data = d;
  } catch (e) { if (seq === assessSeq) a.error = e.message; }
  if (seq === assessSeq) { a.loading = false; render(); }
}

function assessQuestion(facts) {
  return "Hvilken praksis har Ankenævnet for Forsikring om sager, der ligner dette faktum? " +
    "Beskriv hvilke kendelser der ligner mest, hvordan de faldt ud, og hvilke momenter nævnet lagde vægt på.\n\n" +
    `Faktum:\n${facts.trim()}`;
}

function renderAssess() {
  const a = state.assess, d = a.data;
  let result = "";
  if (a.error) result = `<div class="err-box">${esc(a.error)}</div>`;
  else if (a.loading && !d) result = '<div class="kpis">' + '<div class="skel" style="height:92px"></div>'.repeat(3) + '</div><div class="skel" style="height:240px"></div>';
  else if (d && !d.total) result = `<div class="empty">${icon("search")}<h3>Ingen lignende kendelser</h3><p>Prøv at beskrive skaden mere konkret eller fjern et filter.</p></div>`;
  else if (d) {
    const decided = d.total - (d.outcome_counts["Afvist"] || 0) - (d.outcome_counts["Ukendt"] || 0);
    const kpi = (label, value, sub) => `<div class="kpi"><div class="kpi-l">${label}</div><div class="kpi-v num">${value}</div><div class="kpi-s">${sub}</div></div>`;
    result = `
      <div class="kpis three ${a.loading ? "busy" : ""}">
        ${kpi("Klager fik helt/delvist medhold", `${d.claimant_success_rate}%`, `af ${fmtNum(decided)} realitetsbehandlede lignende sager`)}
        ${kpi("Lignende kendelser", fmtNum(d.total), "rangeret efter lighed med faktum")}
        ${kpi("Typiske mangeltyper", "", d.defect_types.slice(0, 3).map((t) => esc(t.label)).join(" · ") || "–")}
      </div>
      ${renderDist(d.outcome_counts, d.total, false, "mest lignende kendelser")}
      <div class="assess-cta">
        <div><strong>Vil du have et praksisoverblik?</strong><span>Assistenten gennemgår de lignende kendelser, hvad nævnet lagde vægt på, og citerer dem.</span></div>
        <button class="btn primary" data-act="assess-ai" ${state.health?.llm ? "" : "disabled"}>${icon("spark")}Få praksisoverblik</button>
      </div>
      <div class="results">${d.similar.map((x) => renderResult(x, a.facts)).join("")}</div>`;
  }
  return `<section class="page wide">
    <div class="page-h"><div><h1 class="h2">Lignende sager</h1><p class="page-sub">Beskriv et faktum. Ejnar finder de kendelser, der ligner mest, og viser hvordan nævnet afgjorde dem.</p></div></div>
    <form class="composer assess-box" data-act="assess">
      <label class="sr" for="facts">Sagens faktum</label>
      <textarea id="facts" data-focus="facts" rows="6" placeholder="Fx: Villa fra 1968 købt i 2021. Efter overtagelsen konstateres fugt og skimmel i krybekælderen. Tilstandsrapporten angav K1 for 'fugt i krybekælder'. Selskabet afviser med henvisning til alder og tilstandsrapport.">${esc(a.facts)}</textarea>
      <div class="composer-bar">
        ${renderFilters()}
        <span class="hint">Gemmes ikke</span>
        <button class="btn primary" type="submit" ${a.loading ? "disabled" : ""}>${a.loading ? '<span class="spinner"></span>' : icon("search")}Find lignende sager</button>
      </div>
      <div class="pii-slot">${piiWarning(a.facts)}</div>
    </form>
    ${result}
  </section>`;
}

// ── Miljøjuristen: screeningstjek ───────────────────────────────────────────
// Uploadede dokumenter gemmes ikke. Teksten sendes kun til en sprogmodel, hvis brugeren vælger det.
const DOKTYPER = [["", "Gæt automatisk"], ["screening_projekt", "Screening af projekt (§ 21)"],
  ["screening_plan", "Screening af plan (§ 10)"], ["miljoerapport_plan", "Miljørapport for plan"],
  ["projekttilladelse", "§ 25-tilladelse / miljøkonsekvensrapport"]];
const ART = { ikke_behandlet: "Ikke behandlet", uden_grundlag: "Uden synligt grundlag", svag_formulering: "Svag formulering",
  kriterier_mangler: "Kriterier mangler", model: "Fundet af sprogmodel", stedtjek: "Fundet på kort" };
let miljoSeq = 0;

async function runMiljo(form) {
  const m = state.miljo, seq = ++miljoSeq;
  const file = form.querySelector("#miljo-fil")?.files?.[0];
  m.text = form.querySelector("#miljo-tekst")?.value || "";
  m.dtype = form.querySelector("#miljo-type")?.value || "";
  m.model = !!form.querySelector("#miljo-model")?.checked;
  m.kommune = form.querySelector("#miljo-kommune")?.value || "";
  m.plannr = form.querySelector("#miljo-plannr")?.value || "";
  m.adresse = form.querySelector("#miljo-adresse")?.value || "";
  m.sted = !!form.querySelector("#miljo-sted")?.checked;
  if (!file && m.text.trim().length < 200) { m.error = "Vælg en fil eller indsæt mindst et par afsnit tekst."; return render(); }
  m.loading = true; m.error = ""; m.fileName = file ? file.name : ""; render();
  try {
    let r;
    if (file) {
      const fd = new FormData();
      fd.append("fil", file);
      if (m.dtype) fd.append("dokumenttype", m.dtype);
      fd.append("brug_model", m.model ? "true" : "false");
      fd.append("stedtjek", m.sted ? "true" : "false");
      for (const k of ["kommune", "plannr", "adresse"]) if (m[k]) fd.append(k, m[k]);
      const res = await fetch("/v1/miljoejurist/tjek", { method: "POST", headers: { "X-API-Key": state.key }, body: fd });
      if (res.status === 401) { logout("Din adgangsnøgle blev afvist. Log ind igen."); return; }
      if (!res.ok) { let d = res.statusText; try { d = (await res.json()).detail; } catch { /* ok */ } throw new ApiError(res.status, d); }
      r = await res.json();
    } else {
      r = await apiJson("/v1/miljoejurist/tjek-tekst", { method: "POST", body: { tekst: m.text, dokumenttype: m.dtype || null, brug_model: m.model,
        stedtjek: m.sted, kommune: m.kommune || null, plannr: m.plannr || null, adresse: m.adresse || null } });
    }
    if (seq === miljoSeq) m.data = r;
  } catch (e) { if (seq === miljoSeq) m.error = e.message; }
  if (seq === miljoSeq) { m.loading = false; render(); }
}

function renderKilde(k) {
  const t = { lov: "Lov", vejledning: "Vejledning", praksis: "Praksis", eu: "EU-dom", kort: "Kort" }[k.type] || k.type;
  return `<li class="mj-src"><span class="mj-tag t-${esc(k.type)}">${t}</span>
    <a href="${esc(safeUrl(k.url))}" target="_blank" rel="noopener">${esc(k.ref)} ${icon("ext")}</a>
    <blockquote>${esc(k.citat)}${k.citat_ok ? "" : ' <span class="mj-warn">kunne ikke genfindes ordret</span>'}</blockquote>
    ${k.ekstra?.fejl ? `<div class="mj-sub">Nævnet underkendte: ${esc(k.ekstra.fejl)}</div>` : ""}
    ${(k.ekstra?.originaler || []).slice(0, 1).map((o) => `<div class="mj-sub">Myndighedens oprindelige dokument: <a href="${esc(safeUrl(o.url))}" target="_blank" rel="noopener">${esc(o.titel)}</a> (${esc(o.type)})</div>`).join("")}</li>`;
}

function renderSvaghed(s, n) {
  const cit = s.citat_dokument
    ? `<blockquote class="mj-doc">«${esc(s.citat_dokument)}»${s.citat_ok === false ? ' <span class="mj-warn">citatet kunne ikke genfindes ordret</span>' : ""}</blockquote>`
    : "";
  return `<article class="mj-card">
    <header><span class="mj-n">${n}</span><h3>${esc(s.titel)} <span class="mj-id">${esc(s.punkt)}</span></h3>
      <span class="mj-art">${esc(ART[s.art] || s.art)}</span></header>
    <div class="mj-row"><strong>Svaghed</strong><p>${esc(s.svaghed)}</p>${cit}</div>
    <div class="mj-row"><strong>Hvorfor</strong><p>${esc(s.hvorfor || "–")}</p><p class="mj-q">${esc(s.spørgsmål)}</p></div>
    <details class="mj-row" ${n <= 2 ? "open" : ""}><summary><strong>Kilder (${s.kilder.length})</strong></summary><ul>${s.kilder.map(renderKilde).join("")}</ul></details>
  </article>`;
}

function renderStedfakta(st) {
  if (!st) return "";
  if (!st.sted) return `<section class="mj-not"><h3>Stedtjek</h3><p>${esc(st.note || "")}</p></section>`;
  const rows = st.fund.map((f) => `<tr><td>${esc(f.type)}</td><td>${f.link ? `<a href="${esc(safeUrl(f.link))}" target="_blank" rel="noopener">${esc(f.navn)}</a>` : esc(f.navn)}</td>
    <td class="num">${fmtNum(f.afstand_m)} m</td><td>${f.nævnt ? "nævnt" : '<span class="mj-warn">ikke nævnt</span>'}</td></tr>`).join("");
  return `<section class="mj-not"><h3>Stedfakta · ${esc(st.sted.beskrivelse)}</h3>
    <div class="mj-tab"><table><thead><tr><th>Type</th><th>Område</th><th>Afstand</th><th>I dokumentet</th></tr></thead><tbody>${rows}</tbody></table></div>
    <p class="mj-sub">${esc(st.note || "")}</p></section>`;
}

function renderMiljo() {
  const m = state.miljo, d = m.data;
  let result = "";
  if (m.error) result = `<div class="err-box">${esc(m.error)}</div>`;
  else if (m.loading) result = '<div class="skel" style="height:120px"></div><div class="skel" style="height:240px"></div>';
  else if (d) {
    const typeNavn = (DOKTYPER.find((x) => x[0] === d.dokumenttype) || [0, d.dokumenttype])[1];
    result = `
      <div class="mj-sum">
        <div><strong>${esc(d.dokument)}</strong> · ${fmtNum(d.ord)} ord · ${esc(typeNavn)} · ${esc(d.lag.join(" + "))}</div>
        <p>${esc(d.note)}</p>
        <button class="btn" data-act="miljo-dl">${icon("doc")}Hent rapport (Markdown)</button>
      </div>
      ${d.svagheder.length ? d.svagheder.map((s, i) => (s.niveau === "opmærksomhed" && (i === 0 || d.svagheder[i - 1].niveau !== "opmærksomhed")
          ? `<h2 class="mj-h">Øvrige opmærksomhedspunkter</h2><p class="mj-sub">Lavere prioritet: emner, der ikke ses behandlet, eller som nævnene sjældnere har underkendt på.</p>` : "") + renderSvaghed(s, i + 1)).join("")
        : `<div class="empty"><h3>Værktøjets kontroller slog ikke ud</h3><p>Det er ikke en vurdering af, om afgørelsen holder. Se listen over, hvad værktøjet ikke vurderer.</p></div>`}
      ${renderStedfakta(d.sted)}
      ${d.mindre?.length ? `<details class="mj-not"><summary><strong>Mindre bemærkninger (${d.mindre.length})</strong></summary><ul>${d.mindre.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></details>` : ""}
      <section class="mj-not"><h3>Hvad værktøjet ikke har vurderet</h3><ul>${d.ikke_vurderet.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
        ${d.punkter_ikke_relevante.length ? `<details><summary>Tjeklistepunkter, der ikke er kørt (${d.punkter_ikke_relevante.length})</summary><ul>${d.punkter_ikke_relevante.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></details>` : ""}
      </section>`;
  }
  const llm = !!state.health?.llm;
  return `<section class="page wide">
    <div class="page-h"><div><h1 class="h2">Miljøjuristen · screeningstjek</h1>
      <p class="page-sub">Upload en screeningsafgørelse, miljørapport eller § 25-tilladelse. Miljøjuristen finder mulige svagheder,
      citerer dokumentet ordret og holder dem op mod loven, vejledningen og lignende afgørelser fra Planklagenævnet og
      Miljø- og Fødevareklagenævnet. Den vurderer ikke, om afgørelsen holder.</p></div></div>
    <form class="composer mj-form" data-act="miljo">
      <label class="mj-file"><span>Dokument (PDF, Word, HTML eller tekst)</span><input type="file" id="miljo-fil" accept=".pdf,.docx,.txt,.html,.htm"></label>
      <label class="sr" for="miljo-tekst">Eller indsæt tekst</label>
      <textarea id="miljo-tekst" rows="5" placeholder="…eller indsæt teksten fra screeningen her">${esc(m.text)}</textarea>
      <div class="mj-sted">
        <label class="mj-chk"><input type="checkbox" id="miljo-sted" ${m.sted === false ? "" : "checked"}> Stedtjek (kort)</label>
        <input id="miljo-kommune" placeholder="Kommune (fx Sønderborg)" value="${esc(m.kommune || "")}">
        <input id="miljo-plannr" placeholder="Plannr. (fx 4.1-10)" value="${esc(m.plannr || "")}">
        <input id="miljo-adresse" placeholder="…eller adresse" value="${esc(m.adresse || "")}">
        <span class="hint">Tomme felter: placeringen gættes ud fra dokumentet</span>
      </div>
      <div class="composer-bar">
        <select id="miljo-type" aria-label="Dokumenttype">${DOKTYPER.map(([v, l]) => `<option value="${v}" ${m.dtype === v ? "selected" : ""}>${l}</option>`).join("")}</select>
        <label class="mj-chk" title="${llm ? "Teksten sendes til den konfigurerede AI-udbyder" : "Ingen sprogmodel konfigureret"}">
          <input type="checkbox" id="miljo-model" ${m.model && llm ? "checked" : ""} ${llm ? "" : "disabled"}> Brug også sprogmodel</label>
        <span class="hint">Gemmes ikke</span>
        <button class="btn primary" type="submit" ${m.loading ? "disabled" : ""}>${m.loading ? '<span class="spinner"></span>' : icon("search")}Tjek dokumentet</button>
      </div>
    </form>
    ${result}
  </section>`;
}

// ── Læser ────────────────────────────────────────────────────────────────────
const STOP = new Set("hvad hvor hvornår hvordan hvilke hvilken være blev bliver eller efter skal kunne ikke også nævnet nævnets praksis dækning dækker forsikring ejerskifteforsikring ejerskifteforsikringen sagen sager klager selskabet mellem under".split(" "));
function terms(q) {
  return [...new Set((q || "").toLowerCase().match(/[\wæøå]{4,}/g) || [])].filter((t) => !STOP.has(t)).sort((a, b) => b.length - a.length).slice(0, 8);
}
function highlight(text, q) {
  let s = esc(text);
  const ts = terms(q);
  const phrase = (q || "").trim().toLowerCase();
  if (/\s/.test(phrase) && phrase.length <= 80 && String(text).toLowerCase().includes(phrase)) ts.unshift(phrase);
  if (!ts.length) return s;
  const rx = new RegExp(`(${ts.map((t) => esc(t).replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "gi");
  return s.replace(/(<[^>]+>)|([^<]+)/g, (m, tag, txt) => tag || txt.replace(rx, "<mark>$1</mark>"));
}

async function openReader(id, q = "") {
  state.reader = { id, q, data: null, error: "", summary: "", sumLoading: false, similar: null };
  state.pop = null;
  render();
  try {
    const d = await apiJson(`/v1/decisions/${encodeURIComponent(id)}?q=${encodeURIComponent(q)}`);
    if (state.reader?.id === id) {
      state.reader.data = d; render();
      apiJson(`/v1/decisions/${encodeURIComponent(d.id)}/similar?limit=6`)
        .then((sim) => { if (state.reader?.id === id) { state.reader.similar = sim; render(); } })
        .catch(() => { if (state.reader?.id === id) { state.reader.similar = []; render(); } });
    }
  } catch (e) {
    if (state.reader?.id === id) { state.reader.error = e.message; render(); }
  }
}

// Kendelsestekster (især ældre, PDF-udtrukne) starter med anonymiserede parter og
// formalia. Den del foldes sammen, og spærrede ord ("k e n d e l s e") samles.
function docText(text, q) {
  const clean = String(text || "")
    .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\uFFFD\uE000-\uF8FF]/g, "")
    .replace(/\s*Ankenævnet for Forsikring\s+\d+\.\s+\d{4,6}\s*/g, " ");
  const lines = clean.split(/\n+/).map((l) => l.trim())
    .map((l) => l.replace(/(?:^|\s)((?:[A-Za-zÆØÅæøå] ){2,}[A-Za-zÆØÅæøå])(?=\s|:|$)/g, (m, w) => m.replace(w, w.replace(/ /g, ""))))
    .filter((l) => l && !/^[_\-–—=.\s]{3,}$/.test(l));
  let start = 0;
  for (let i = 0; i < Math.min(lines.length, 30); i++) {
    if (/^(kendelse|dom)\s*:?$|afsagt sålydende/i.test(lines[i])) { start = i + 1; }
  }
  const block = (b) => {
    const h = b.match(/^#{2,3}\s+(.*)$/);
    if (h) return `<h4>${esc(h[1])}</h4>`;
    if (/^(?:(?:derfor|herefter|som følge heraf|med dette forbehold)\s+)?bestemmes\s*:?$/i.test(b)) return "<h4>Afgørelse</h4>";
    if (b.length <= 48 && /^[A-ZÆØÅ]/.test(b) && /:$/.test(b) && !/\d{2}/.test(b)) return `<h4>${esc(b.replace(/:$/, ""))}</h4>`;
    return `<p>${highlight(b, q)}</p>`;
  };
  const pre = start ? `<details class="preamble"><summary>Parter og formalia</summary>${lines.slice(0, start).map((l) => `<div>${esc(l)}</div>`).join("")}</details>` : "";
  // Saml hårde linjeskift (PDF-ombrydning) til afsnit: nyt afsnit kun efter
  // sætningsafslutning efterfulgt af stort begyndelsesbogstav, eller ved overskrifter.
  const isHead = (l) => /^#{2,3}\s/.test(l) || (l.length <= 48 && /^[A-ZÆØÅ]/.test(l) && /:$/.test(l) && !/\d{2}/.test(l)) || /^\S*\s*\S*\s*bestemmes\s*:?$/i.test(l);
  const paras = [];
  for (const l of lines.slice(start)) {
    const prev = paras[paras.length - 1];
    if (prev != null && !isHead(l) && !isHead(prev) && (!/[.!?:;]["”)]?$/.test(prev) || /^[a-zæøå(§]/.test(l))) {
      paras[paras.length - 1] = /[a-zæøå]-$/.test(prev) ? prev.slice(0, -1) + l : `${prev} ${l}`;
    } else paras.push(l);
  }
  return pre + paras.map(block).join("");
}

function renderReader() {
  const r = state.reader;
  const d = r.data;
  const saved = d && state.saved[d.id];
  let body;
  if (r.error) body = `<div class="err-box">${esc(r.error)}</div>`;
  else if (!d) body = '<div class="skel" style="height:40px;width:60%"></div><div class="skel"></div><div class="skel" style="height:320px"></div>';
  else {
    const head = headline(d.title);
    const rest = d.title;
    body = `
      <div class="meta">${badge(d.outcome)}${(d.defect_types || []).map((t) => `<span class="tag">${esc(t)}</span>`).join("")}</div>
      <h1 class="doc-h">${esc(head)}</h1>
      ${rest ? `<p class="doc-sum">${esc(rest)}</p>` : ""}
      <dl class="doc-grid">
        <div><dt>Sagsnummer</dt><dd class="num">${esc(d.case_number || "—")}</dd></div>
        <div><dt>Afsagt</dt><dd>${fmtD(d)}</dd></div>
        <div><dt>Selskab</dt><dd title="${esc(d.company)}">${esc(d.company || "—")}</dd></div>
        <div><dt>Udfald for klager</dt><dd>${esc(d.outcome)}</dd></div>
        <div><dt>Dækning</dt><dd>${esc(d.coverage || "Ikke angivet")}</dd></div>
      </dl>
      ${r.summary || r.sumLoading ? `<div class="summary"><div class="summary-h">${icon("spark")}AI-resumé</div>${r.sumLoading ? '<div class="step active"><span class="spinner"></span>Læser kendelsen…</div>' : `<div class="answer">${md(r.summary)}</div>`}</div>` : ""}
      <div class="doc-text">${docText(d.text, r.q)}</div>
      <section class="similar">
        <h3>Lignende kendelser</h3>
        ${r.similar == null ? '<div class="skel" style="height:64px"></div><div class="skel" style="height:64px"></div>'
          : r.similar.length ? r.similar.map((x) => `
            <button class="sim" data-act="open-doc" data-id="${esc(x.id)}">
              <span class="sim-h">${esc(headline(x.title))}</span>
              <span class="meta"><span class="num">AKF ${esc(x.case_number || "—")}</span><span class="sep"></span><span>${fmtD(x)}</span></span>
              ${badge(x.outcome)}
            </button>`).join("") : '<div class="aside-empty">Ingen lignende kendelser fundet.</div>'}
      </section>`;
  }
  return `
    <div class="scrim" data-act="close-reader"></div>
    <div class="drawer" role="dialog" aria-modal="true" aria-label="Kendelse">
      <div class="drawer-bar">
        <button class="icon-btn" data-act="close-reader" aria-label="Luk">${icon("x")}</button>
        <span class="grow">${d ? `AKF ${esc(d.case_number || "")}` : ""}</span>
        ${d ? `
          <button class="btn ghost sm" data-act="summary" ${r.sumLoading || r.summary || !state.health?.llm ? "disabled" : ""}>${icon("spark")}Resumé</button>
          <button class="btn ghost sm" data-act="copy-ref">${icon("copy")}Reference</button>
          <button class="btn ghost sm" data-act="print">${icon("doc")}Print</button>
          <button class="btn ghost sm ${saved ? "on" : ""}" data-act="save">${icon("bookmark")}${saved ? "Gemt" : "Gem"}</button>
          <a class="btn sm" href="${esc(safeUrl(d.link))}" target="_blank" rel="noopener noreferrer">${icon("ext")}Original</a>` : ""}
      </div>
      <div class="drawer-body">${body}</div>
    </div>`;
}

async function loadSummary() {
  const r = state.reader;
  if (!r?.data) return;
  r.sumLoading = true; render();
  try {
    const d = await apiJson(`/v1/decisions/${encodeURIComponent(r.id)}/summary`, { method: "POST" });
    if (state.reader === r) r.summary = d.summary;
  } catch (e) {
    if (state.reader === r) r.summary = `_Resumé kunne ikke hentes: ${e.message}_`;
  }
  r.sumLoading = false;
  render();
}

// ── Login / opstart ──────────────────────────────────────────────────────────
function renderLogin(error = "") {
  app.innerHTML = `
    <div class="login"><form class="login-card" data-act="login">
      <div class="brand"><div class="brand-mark">E</div><div><div class="brand-name">Ejnar</div><div class="brand-sub">Ejerskifteforsikring · AKF</div></div></div>
      <h1>Praksis, med kilder.</h1>
      <p>Research i Ankenævnet for Forsikrings kendelser om ejerskifteforsikring.</p>
      <div class="field"><label for="key">Adgangsnøgle</label><input id="key" type="password" autocomplete="current-password" required autofocus></div>
      <button class="btn primary" type="submit">Fortsæt</button>
      <div class="err" role="alert">${esc(error)}</div>
      <small>Nøglen gemmes kun i denne browser. Kontakt din administrator for at få adgang.</small>
    </form></div>`;
}

function renderBoot(msg = "Indlæser…") {
  app.innerHTML = `<div class="login"><div class="login-card">
    <div class="brand"><div class="brand-mark">E</div><div><div class="brand-name">Ejnar</div><div class="brand-sub">Ejerskifteforsikring · AKF</div></div></div>
    <div class="step active"><span class="spinner"></span>${esc(msg)}</div></div></div>`;
}

async function boot() {
  if (state.booting) return;
  state.booting = true;
  renderBoot();
  for (let attempt = 0; ; attempt++) {
    try {
      const [meta, health] = await Promise.all([apiJson("/v1/meta"), fetch("/health").then((r) => r.json()).catch(() => null)]);
      state.meta = meta; state.health = health;
      break;
    } catch (e) {
      if (e.status === 401) { state.booting = false; return; }
      if (e.status === 503 && attempt < 60) { renderBoot("Ejnar starter op og indlæser kendelserne…"); await new Promise((r) => setTimeout(r, 4000)); continue; }
      state.booting = false;
      return renderLogin(e.message || "Kunne ikke forbinde til serveren.");
    }
  }
  state.booting = false;
  render();
}

function logout(msg = "") {
  state.key = ""; state.meta = null; state.reader = null;
  store.del("key");
  renderLogin(msg);
}

// ── Diverse ──────────────────────────────────────────────────────────────────
let toastT;
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg; t.classList.add("show");
  clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove("show"), 2200);
}
async function copy(text, msg = "Kopieret") {
  try { await navigator.clipboard.writeText(text); toast(msg); } catch { toast("Kunne ikke kopiere"); }
}
function autosize() {
  for (const ta of $$(".composer textarea:not(#facts)")) { ta.style.height = "auto"; ta.style.height = Math.min(ta.scrollHeight, 240) + "px"; }
}
function newThread() {
  state.activeId = null; state.focusTurn = null; state.view = "assistant"; state.navOpen = false; store.set("view", "assistant");
  render();
  $("#q")?.focus();
}

// ── Hændelser ────────────────────────────────────────────────────────────────
app.addEventListener("click", (e) => {
  const el = e.target.closest("[data-act]");
  if (state.pop && !e.target.closest("[data-stop]") && !(el && ["pop", "toggle-opt", "clear-filter"].includes(el.dataset.act))) {
    state.pop = null; state.popQuery = "";
    if (!el) return render();
  }
  if (!el) return;
  const act = el.dataset.act;
  const f = state.filters;
  switch (act) {
    case "nav": state.navOpen = !state.navOpen; return render();
    case "miljo-dl": {
      const d = state.miljo.data;
      if (!d) return;
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([d.markdown], { type: "text/markdown" }));
      a.download = "screeningstjek.md"; a.click(); URL.revokeObjectURL(a.href);
      return;
    }
    case "view":
      state.view = el.dataset.v; state.navOpen = false; store.set("view", state.view);
      if (state.view === "assistant") state.focusTurn = null;
      return render();
    case "new": return newThread();
    case "open-thread":
      state.activeId = el.dataset.id; state.view = "assistant"; state.focusTurn = null; state.navOpen = false; return render();
    case "del-thread":
      e.stopPropagation();
      state.threads = state.threads.filter((t) => t.id !== el.dataset.id);
      if (state.activeId === el.dataset.id) state.activeId = null;
      saveThreads(); return render();
    case "theme":
      state.theme = isDark() ? "light" : "dark";
      document.documentElement.dataset.theme = state.theme; store.set("theme", state.theme); return render();
    case "logout": return logout();
    case "suggest": return ask(el.dataset.q);
    case "pop":
      if (e.target.closest(".x")) return;
      state.pop = state.pop === el.dataset.k ? null : el.dataset.k; state.popQuery = ""; return render();
    case "close-pop": state.pop = null; return render();
    case "toggle-opt": {
      const arr = f[el.dataset.k]; const v = el.dataset.v; const i = arr.indexOf(v);
      i >= 0 ? arr.splice(i, 1) : arr.push(v);
      return filtersChanged();
    }
    case "clear-filter":
      e.stopPropagation();
      if (el.dataset.k === "years") { f.year_from = null; f.year_to = null; } else f[el.dataset.k] = [];
      state.pop = null; return filtersChanged();
    case "apply-years": {
      const from = parseInt($('[data-yr="from"]')?.value, 10), to = parseInt($('[data-yr="to"]')?.value, 10);
      f.year_from = Number.isFinite(from) ? from : null; f.year_to = Number.isFinite(to) ? to : null;
      state.pop = null; return filtersChanged();
    }
    case "only-outcome": f.outcomes = [el.dataset.v]; return filtersChanged();
    case "cite": {
      const aIdx = +el.closest("[data-turn]").dataset.turn; // assistent-beskedens indeks
      state.focusTurn = aIdx; state.hotCite = `${aIdx}:${el.dataset.n}`;
      render();
      const card = $(`.src[data-src="${aIdx}:${el.dataset.n}"]`);
      card?.scrollIntoView({ behavior: "smooth", block: "nearest" });
      if (card && innerWidth > 1180) return;
      if (card) return openReader(card.dataset.id, activeThread()?.messages[aIdx - 1]?.content || "");
      return;
    }
    case "open-doc": {
      if (el.closest(".drawer")) { $(".drawer-body")?.scrollTo({ top: 0 }); return openReader(el.dataset.id, state.reader?.q || ""); }
      const q = el.dataset.src ? activeThread()?.messages[+el.dataset.src.split(":")[0] - 1]?.content : state.search.lastQ;
      return openReader(el.dataset.id, q || "");
    }
    case "close-reader": state.reader = null; return render();
    case "summary": return loadSummary();
    case "save": {
      const d = state.reader?.data; if (!d) return;
      if (state.saved[d.id]) { delete state.saved[d.id]; toast("Fjernet fra gemte"); }
      else { const { text, ...lite } = d; state.saved[d.id] = { ...lite, saved_at: Date.now() }; toast("Gemt"); }
      store.set("saved", state.saved); return render();
    }
    case "copy-ref": {
      const d = state.reader?.data; if (!d) return;
      return copy(`Ankenævnet for Forsikring, kendelse af ${fmtD(d)}, sag nr. ${d.case_number || "—"} (${d.company || "ukendt selskab"}). ${d.link}`, "Reference kopieret");
    }
    case "copy-answer": return copyAnswer(+el.dataset.i);
    case "fb-up": return sendFeedback(+el.dataset.i, "up");
    case "fb-down": { const a = activeThread()?.messages[+el.dataset.i]; if (a) { a.feedback = a.feedback === "form" ? "" : "form"; render(); } return; }
    case "fb-cancel": { const a = activeThread()?.messages[+el.dataset.i]; if (a) { a.feedback = ""; render(); } return; }
    case "retry": {
      const t = activeThread(); const i = +el.dataset.i;
      return ask(t.messages[i - 1].content, { reuseIdx: i });
    }
    case "mode":
      state.search.mode = el.dataset.v;
      if (state.search.q.trim()) return runSearch();
      return render();
    case "more": return runSearch({ more: true });
    case "assess-ai": state.activeId = null; return ask(assessQuestion(state.assess.facts));
    case "print": return window.print();
    case "bd-filter": {
      const arr = f[el.dataset.k];
      if (!arr.includes(el.dataset.v)) arr.push(el.dataset.v);
      return filtersChanged();
    }
  }
});

function showTip(col) {
  const chart = col.closest(".ychart"), tip = $(".tip", chart);
  const r = JSON.parse(col.dataset.tip);
  tip.innerHTML = `<strong>${r.label}</strong><span class="num">${fmtNum(r.total)} sager</span>` +
    OUT_CHART.filter((o) => r.counts[o]).map((o) => `<div><i class="c-${OUT_KEY[o]}"></i>${o}<b class="num">${r.counts[o]}</b></div>`).join("") +
    `<div class="tip-f">Klager medhold ${klagerRate(r.counts, r.total)}%</div>`;
  tip.hidden = false;
  const cr = chart.getBoundingClientRect(), br = col.getBoundingClientRect();
  const x = Math.min(Math.max(br.left - cr.left + br.width / 2, 90), cr.width - 90);
  tip.style.left = `${x}px`;
  $$(".ycol.on", chart).forEach((c) => c.classList.remove("on")); col.classList.add("on");
}
app.addEventListener("focusin", (e) => { const col = e.target.closest?.(".ycol"); if (col) showTip(col); });
app.addEventListener("mouseleave", (e) => {
  if (e.target.matches?.(".ychart")) { $(".tip", e.target).hidden = true; $$(".ycol.on", e.target).forEach((c) => c.classList.remove("on")); }
}, true);

app.addEventListener("mouseover", (e) => {
  const col = e.target.closest(".ycol");
  if (col) return showTip(col);
  const c = e.target.closest(".cite");
  if (!c) return;
  const aIdx = +c.closest("[data-turn]").dataset.turn;
  const key = `${aIdx}:${c.dataset.n}`;
  if (state.focusTurn !== aIdx && state.focusTurn !== null) return;
  $$(".src.hot").forEach((x) => x.classList.remove("hot"));
  $(`.src[data-src="${key}"]`)?.classList.add("hot");
});

app.addEventListener("submit", (e) => {
  e.preventDefault();
  const act = e.target.dataset.act;
  if (act === "login") {
    state.key = $("#key").value.trim();
    store.set("key", state.key);
    return boot();
  }
  if (act === "ask") return ask(state.draft);
  if (act === "search") { state.search.q = $('[data-focus="search"]').value; return runSearch(); }
  if (act === "assess") return runAssess();
  if (act === "fb-send") {
    const fd = new FormData(e.target);
    return sendFeedback(+e.target.dataset.i, "down", fd.getAll("r"), String(fd.get("comment") || "").trim());
  }
  if (act === "stats") { state.insight.q = $('[data-focus="stats"]').value; return runStats(); }
  if (act === "miljo") return runMiljo(e.target);
});

app.addEventListener("input", (e) => {
  const t = e.target;
  const slot = t.closest("form")?.querySelector(".pii-slot");
  if (slot) slot.innerHTML = piiWarning(t.value);
  if (t.matches("#facts")) {
    state.assess.facts = t.value;
  } else if (t.matches(".composer textarea")) {
    state.draft = t.value; autosize();
    $$(".send").forEach((b) => (b.disabled = !state.draft.trim() || activeThread()?.messages.some((m) => m.status === "streaming")));
  } else if (t.matches("[data-popq]")) {
    state.popQuery = t.value; render();
  } else if (t.matches('[data-focus="search"]')) {
    state.search.q = t.value;
  }
});

app.addEventListener("keydown", (e) => {
  if (e.target.matches(".composer textarea:not(#facts)") && e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault(); if (state.draft.trim()) ask(state.draft);
  }
  if (e.target.matches(".thread-item") && e.key === "Enter") e.target.click();
});

document.addEventListener("keydown", (e) => {
  const typing = e.target.matches("input, textarea");
  if (e.key === "Escape") {
    if (state.pop) { state.pop = null; return render(); }
    if (state.reader) { state.reader = null; return render(); }
    if (state.navOpen) { state.navOpen = false; return render(); }
  }
  if (typing || e.metaKey || e.ctrlKey || e.altKey || !state.meta) return;
  if (e.key === "/") { e.preventDefault(); ($('[data-focus="search"]') || $("#q"))?.focus(); }
  else if (e.key.toLowerCase() === "n" && !state.reader) { e.preventDefault(); newThread(); }
});

matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change", () => { if (!state.theme && state.meta) render(); });

state.key ? boot() : renderLogin();
