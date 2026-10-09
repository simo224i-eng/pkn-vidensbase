// Miljøjuristen — selvstændig side til screeningstjek. Ren ES-modul uden build-step; taler med /v1/miljoejurist.
// Uploadede dokumenter gemmes ikke. Teksten sendes kun til en sprogmodel, hvis brugeren vælger det.

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const safeUrl = (u) => (/^https?:\/\//i.test(String(u || "")) ? String(u) : "#");
const fmtNum = (n) => new Intl.NumberFormat("da-DK").format(n ?? 0);
const store = {
  get(k, d) { try { const v = localStorage.getItem("miljoejurist." + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem("miljoejurist." + k, JSON.stringify(v)); } catch { /* privat tilstand */ } },
  del(k) { try { localStorage.removeItem("miljoejurist." + k); } catch { /* ignore */ } },
};
const ICONS = {
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  ext: '<path d="M15 3h6v6M10 14 21 3M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
  doc: '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6M8 13h8M8 17h5"/>',
};
const icon = (n) => `<svg class="i" viewBox="0 0 24 24" aria-hidden="true">${ICONS[n] || ""}</svg>`;

const DOKTYPER = [["", "Gæt automatisk"], ["screening_projekt", "Screening af projekt (§ 21)"],
  ["screening_plan", "Screening af plan (§ 10)"], ["miljoerapport_plan", "Miljørapport for plan"],
  ["projekttilladelse", "§ 25-tilladelse / miljøkonsekvensrapport"]];
const ART = { ikke_behandlet: "Ikke behandlet", uden_grundlag: "Uden synligt grundlag", svag_formulering: "Svag formulering",
  kriterier_mangler: "Kriterier mangler", model: "Fundet af sprogmodel", stedtjek: "Fundet på kort" };

const state = { key: store.get("key", ""), health: null, text: "", dtype: "", model: false, sted: true,
  kommune: "", plannr: "", adresse: "", udeluk: "", data: null, loading: false, error: "", loginError: "" };
let seq = 0;

class ApiError extends Error { constructor(status, msg) { super(msg); this.status = status; } }
async function api(path, opts = {}) {
  const headers = { ...(state.key ? { "X-API-Key": state.key } : {}), ...(opts.json ? { "Content-Type": "application/json" } : {}) };
  const res = await fetch(path, { method: opts.method || "GET", headers, body: opts.json ? JSON.stringify(opts.json) : opts.body });
  if (!res.ok) { let d = res.statusText; try { d = (await res.json()).detail; } catch { /* ok */ } throw new ApiError(res.status, d); }
  return res.json();
}

async function run(form) {
  const my = ++seq;
  const file = form.querySelector("#fil")?.files?.[0];
  state.text = form.querySelector("#tekst").value;
  state.dtype = form.querySelector("#type").value;
  state.model = form.querySelector("#model").checked;
  state.sted = form.querySelector("#sted").checked;
  for (const k of ["kommune", "plannr", "adresse", "udeluk"]) state[k] = form.querySelector("#" + k).value.trim();
  if (!file && state.text.trim().length < 200) { state.error = "Vælg en fil eller indsæt mindst et par afsnit tekst."; return render(); }
  state.loading = true; state.error = ""; render();
  try {
    let r;
    if (file) {
      const fd = new FormData();
      fd.append("fil", file);
      if (state.dtype) fd.append("dokumenttype", state.dtype);
      fd.append("brug_model", state.model ? "true" : "false");
      fd.append("stedtjek", state.sted ? "true" : "false");
      for (const k of ["kommune", "plannr", "adresse", "udeluk"]) if (state[k]) fd.append(k, state[k]);
      r = await api("/v1/miljoejurist/tjek", { method: "POST", body: fd });
    } else {
      r = await api("/v1/miljoejurist/tjek-tekst", { method: "POST", json: { tekst: state.text, dokumenttype: state.dtype || null,
        brug_model: state.model, stedtjek: state.sted, kommune: state.kommune || null, plannr: state.plannr || null, adresse: state.adresse || null,
        udeluk: state.udeluk ? state.udeluk.split(/[,;\s]+/).filter(Boolean) : [] } });
    }
    if (my === seq) state.data = r;
  } catch (e) {
    if (e.status === 401) { store.del("key"); state.key = ""; state.health = { ...state.health, nøgle_kræves: true }; state.loginError = "Nøglen blev afvist."; }
    else if (my === seq) state.error = e.message;
  }
  if (my === seq) { state.loading = false; render(); }
}

function renderKilde(k) {
  const t = { lov: "Lov", vejledning: "Vejledning", praksis: "Praksis", eu: "EU-dom", kort: "Kort" }[k.type] || k.type;
  return `<li class="src"><span class="tag">${esc(t)}</span>
    <a href="${esc(safeUrl(k.url))}" target="_blank" rel="noopener">${esc(k.ref)} ${icon("ext")}</a>
    <blockquote>${esc(k.citat)}${k.citat_ok ? "" : ' <span class="warn">kunne ikke genfindes ordret</span>'}</blockquote>
    ${k.ekstra?.fejl ? `<div class="sub">Nævnet underkendte: ${esc(k.ekstra.fejl)}</div>` : ""}
    ${(k.ekstra?.originaler || []).slice(0, 1).map((o) => `<div class="sub">Myndighedens oprindelige dokument: <a href="${esc(safeUrl(o.url))}" target="_blank" rel="noopener">${esc(o.titel)}</a> (${esc(o.type)})</div>`).join("")}</li>`;
}

function renderSvaghed(s, n) {
  const cit = s.citat_dokument
    ? `<blockquote>«${esc(s.citat_dokument)}»${s.citat_ok === false ? ' <span class="warn">citatet kunne ikke genfindes ordret</span>' : ""}</blockquote>` : "";
  return `<article class="card svag">
    <header><span class="n">${n}</span><h3>${esc(s.titel)} <span class="pid">${esc(s.punkt)}</span></h3>${s.risiko ? `<span class="art rsk-${esc(s.risiko)}">Risiko: ${esc(s.risiko)}</span>` : `<span class="art">${esc(ART[s.art] || s.art)}</span>`}</header>
    <div class="row"><strong>Svaghed</strong><p>${esc(s.svaghed)}</p>${cit}</div>
    <div class="row"><strong>Hvorfor</strong><p>${esc(s.hvorfor || "–")}</p><p class="q">${esc(s.spørgsmål)}</p></div>
    <details class="row" ${n <= 2 ? "open" : ""}><summary><strong>Kilder (${s.kilder.length})</strong></summary><ul>${s.kilder.map(renderKilde).join("")}</ul></details>
  </article>`;
}

function renderSted(st) {
  if (!st) return "";
  if (!st.sted) return `<section class="not"><h3>Stedtjek</h3><p>${esc(st.note || "")}</p></section>`;
  const rows = st.fund.map((f) => `<tr><td>${esc(f.type)}</td><td>${f.link ? `<a href="${esc(safeUrl(f.link))}" target="_blank" rel="noopener">${esc(f.navn)}</a>` : esc(f.navn)}</td>
    <td class="num">${fmtNum(f.afstand_m)} m</td><td>${f.nævnt ? "nævnt" : '<span class="warn">ikke nævnt</span>'}</td></tr>`).join("");
  return `<section class="not"><h3>Stedfakta · ${esc(st.sted.beskrivelse)}</h3>
    <div class="tab"><table><thead><tr><th>Type</th><th>Område</th><th>Afstand</th><th>I dokumentet</th></tr></thead><tbody>${rows}</tbody></table></div>
    <p class="sub">${esc(st.note || "")}</p></section>`;
}

function renderResultat() {
  const d = state.data;
  if (state.error) return `<div class="err">${esc(state.error)}</div>`;
  if (state.loading) return '<div class="skel" style="height:110px"></div><div class="skel" style="height:240px"></div>';
  if (!d) return "";
  const typeNavn = (DOKTYPER.find((x) => x[0] === d.dokumenttype) || [0, d.dokumenttype])[1];
  const model = d.lag.includes("model");
  const svag = d.svagheder.length ? d.svagheder.map((s, i) => {
      const ny = i === 0 || d.svagheder[i - 1].niveau !== s.niveau;
      let h = "";
      if (ny && model && s.niveau === "svaghed") h = '<h2 class="sec">Punkter med risiko for ophævelse</h2>';
      if (ny && s.niveau === "opmærksomhed") h = model
        ? '<h2 class="sec">Særlige opmærksomhedspunkter (helgardering)</h2><p class="sub">Punkter, hvor vurderingen kan styrkes. Nævnene accepterer ofte en vurdering på dette niveau.</p>'
        : '<h2 class="sec">Øvrige opmærksomhedspunkter</h2><p class="sub">Lavere prioritet: emner, der ikke ses behandlet, eller som nævnene sjældnere har underkendt på.</p>';
      return h + renderSvaghed(s, i + 1);
    }).join("")
    : '<div class="card empty"><h3>Værktøjets kontroller slog ikke ud</h3><p>Det er ikke en vurdering af, om afgørelsen holder. Se listen over, hvad værktøjet ikke vurderer.</p></div>';
  return `
    <div class="card sum">
      ${d.udeluk?.length ? `<div class="sub">Simulation: ${esc(d.udeluk.join(", "))} er skjult fra praksissøgningen.</div>` : ""}
      <div><strong>${esc(d.dokument)}</strong> · ${fmtNum(d.ord)} ord · ${esc(typeNavn)} · ${esc(d.lag.join(" + "))}</div>
      <p>${esc(d.note)}</p>
      <button class="btn" data-act="dl">${icon("doc")}Hent rapport (Markdown)</button>
    </div>
    ${d.udfald ? `<div class="card risk r-${esc(d.udfald.niveau)}"><div class="rk">Indikator for ophævelsesrisiko</div>
      <div class="rv">${esc(d.udfald.niveau)} <span>ca. ${esc(d.udfald.sandsynlighed)} %</span></div>
      <p>${esc(d.udfald.begrundelse || "")}</p>
      <p class="sub">Udgangspunkt for denne afgørelsestype: ${esc(d.udfald.basisrate ?? "–")} % af de påklagede sager ophæves helt eller delvist. Indikatoren er en modelvurdering testet på nævnssager, ikke en forudsigelse af den konkrete sag.</p></div>` : ""}
    ${svag}
    ${renderSted(d.sted)}
    ${d.mindre?.length ? `<details class="not"><summary><strong>Mindre bemærkninger (${d.mindre.length})</strong></summary><ul>${d.mindre.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></details>` : ""}
    <section class="not"><h3>Hvad værktøjet ikke har vurderet</h3><ul>${d.ikke_vurderet.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
      ${d.punkter_ikke_relevante.length ? `<details><summary>Tjeklistepunkter, der ikke er kørt (${d.punkter_ikke_relevante.length})</summary><ul>${d.punkter_ikke_relevante.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></details>` : ""}
    </section>`;
}

function renderLogin() {
  return `<form class="login" data-act="login">
    <div class="top" style="padding:0 0 24px"><div class="logo">M</div><b>Miljøjuristen</b></div>
    <label for="key">Adgangsnøgle</label><input id="key" type="password" autocomplete="off">
    ${state.loginError ? `<div class="warn">${esc(state.loginError)}</div>` : ""}
    <button class="btn primary" type="submit">Fortsæt</button>
    <p class="sub">Nøglen gemmes kun i denne browser.</p></form>`;
}

function render() {
  const app = document.getElementById("app");
  if (state.health?.nøgle_kræves && !state.key) { app.innerHTML = renderLogin(); return; }
  const llm = !!state.health?.llm;
  app.innerHTML = `
  <div class="top"><div class="logo">M</div><b>Miljøjuristen</b><span>Screeningstjek</span><span class="sp"></span>
    ${state.key ? '<button class="linkbtn" data-act="logout">Log ud</button>' : ""}</div>
  <main class="page">
    <h1>Hvor er screeningen svag?</h1>
    <p class="lead">Upload en screeningsafgørelse, miljørapport eller § 25-tilladelse. Miljøjuristen finder mulige svagheder,
      citerer dokumentet ordret og holder dem op mod loven, vejledningen, EU-domme og lignende afgørelser fra Planklagenævnet og
      Miljø- og Fødevareklagenævnet. Den vurderer ikke, om afgørelsen holder.</p>
    <form class="card form" data-act="tjek">
      <label class="file"><span>Dokument (PDF, Word, HTML eller tekst)</span><input type="file" id="fil" accept=".pdf,.docx,.txt,.html,.htm"></label>
      <label class="sr" for="tekst">Eller indsæt tekst</label>
      <textarea id="tekst" rows="5" placeholder="…eller indsæt teksten fra screeningen her">${esc(state.text)}</textarea>
      <div class="sted">
        <label class="chk"><input type="checkbox" id="sted" ${state.sted ? "checked" : ""}> Stedtjek (kort)</label>
        <input id="kommune" placeholder="Kommune (fx Sønderborg)" value="${esc(state.kommune)}">
        <input id="plannr" placeholder="Plannr. (fx 4.1-10)" value="${esc(state.plannr)}">
        <input id="adresse" placeholder="…eller adresse" value="${esc(state.adresse)}">
        <span class="hint">Tomme felter: placeringen gættes ud fra dokumentet</span>
      </div>
      <details class="sim"${state.udeluk ? " open" : ""}><summary>Simulation</summary>
        <label for="udeluk">Skjul nævnsafgørelser fra praksissøgningen (sags-id, fx P1c222e8f)</label>
        <input id="udeluk" value="${esc(state.udeluk)}" placeholder="P1c222e8f">
        <span class="hint">Bruges til at teste værktøjet på en sag, nævnet har afgjort, uden at det kan finde svaret.</span>
      </details>
      <div class="bar">
        <select id="type" aria-label="Dokumenttype">${DOKTYPER.map(([v, l]) => `<option value="${v}" ${state.dtype === v ? "selected" : ""}>${l}</option>`).join("")}</select>
        <label class="chk" title="${llm ? "Teksten sendes til den konfigurerede AI-udbyder" : "Ingen sprogmodel konfigureret"}">
          <input type="checkbox" id="model" ${state.model && llm ? "checked" : ""} ${llm ? "" : "disabled"}> Brug også sprogmodel${llm ? "" : " (ikke sat op)"}</label>
        <span class="sp"></span><span class="hint">Gemmes ikke</span>
        <button class="btn primary" type="submit" ${state.loading ? "disabled" : ""}>${state.loading ? '<span class="spinner"></span>' : icon("search")}Tjek dokumentet</button>
      </div>
    </form>
    ${renderResultat()}
  </main>`;
}

document.addEventListener("submit", (e) => {
  e.preventDefault();
  const act = e.target.dataset.act;
  if (act === "tjek") return run(e.target);
  if (act === "login") {
    state.key = e.target.querySelector("#key").value.trim();
    store.set("key", state.key); state.loginError = ""; render();
  }
});
document.addEventListener("click", (e) => {
  const el = e.target.closest("[data-act]");
  if (!el || el.tagName === "FORM") return;
  if (el.dataset.act === "dl" && state.data) {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([state.data.markdown], { type: "text/markdown" }));
    a.download = "screeningstjek.md"; a.click(); URL.revokeObjectURL(a.href);
  }
  if (el.dataset.act === "logout") { store.del("key"); state.key = ""; render(); }
});

(async () => {
  try { state.health = await (await fetch("/health")).json(); } catch { state.health = {}; }
  render();
})();
