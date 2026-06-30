"""Læsesal – en bog-/manga-læser med eget design.

Læser billed-baserede bøger (manga, scannede sider), CBZ/ZIP-arkiver og PDF'er
med en immersiv læseroplevelse: bladring (tastatur/swipe/klik), zoom
(bredde/højde/pinch), fuldskærm, side-oversigt, læse-temaer, læseretning
(venstre→højre / højre→venstre) og hukommelse for sidst læste side pr. bog
(gemt i browseren via localStorage).

Bøger hentes fra to kilder:
  1. Mappen ``boeger/`` i projektet (committede bøger).
  2. Upload direkte i appen (kun for den aktuelle session).
"""

import base64
import hashlib
import io
import json
import mimetypes
import os
import zipfile

import streamlit as st

from shared import sidebar_log_ud

# ── Adgangskontrol ─────────────────────────────────────────────────────────────
if not st.session_state.get("_autentificeret_v2"):
    st.switch_page("app.py")
    st.stop()

# ── Konstanter ─────────────────────────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOK_DIR = os.path.join(_ROOT, "boeger")

IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".avif", ".bmp"}
ARCHIVE_EXT = {".cbz", ".zip"}
PDF_EXT = {".pdf"}

# Eget design – ikke Harald. Varm "læsesal" med indigo/rav-accent.
ACCENT = "#6366f1"      # indigo
ACCENT_2 = "#d97706"    # rav


# ── Hjælpere ───────────────────────────────────────────────────────────────────
def _natural_key(navn: str):
    """Sortér 'side2' før 'side10' (naturlig/menneskelig sortering)."""
    import re

    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", navn)]


def _data_url_from_bytes(raw: bytes, filnavn: str) -> str:
    mime = mimetypes.guess_type(filnavn)[0]
    if mime is None:
        mime = "image/svg+xml" if filnavn.lower().endswith(".svg") else "application/octet-stream"
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _book_id(navn: str) -> str:
    return hashlib.md5(navn.encode("utf-8")).hexdigest()[:12]


@st.cache_data(ttl=600, show_spinner=False)
def scan_books() -> list[dict]:
    """Find alle bøger i boeger/-mappen. Returnér letvægts-metadata (uden sider)."""
    boeger: list[dict] = []
    if not os.path.isdir(BOOK_DIR):
        return boeger

    for navn in sorted(os.listdir(BOOK_DIR), key=_natural_key):
        sti = os.path.join(BOOK_DIR, navn)
        if navn.startswith(".") or navn.lower() in {"readme.md", "readme.txt"}:
            continue

        if os.path.isdir(sti):
            sider = [
                f
                for f in os.listdir(sti)
                if os.path.splitext(f)[1].lower() in IMG_EXT and not f.startswith(".")
            ]
            if sider:
                boeger.append(
                    {
                        "id": _book_id(navn),
                        "title": navn,
                        "type": "images",
                        "path": sti,
                        "n_pages": len(sider),
                        "kilde": "mappe",
                    }
                )
            continue

        ext = os.path.splitext(navn)[1].lower()
        titel = os.path.splitext(navn)[0]
        if ext in ARCHIVE_EXT:
            try:
                with zipfile.ZipFile(sti) as z:
                    n = sum(
                        1
                        for n_ in z.namelist()
                        if os.path.splitext(n_)[1].lower() in IMG_EXT
                    )
                if n:
                    boeger.append(
                        {
                            "id": _book_id(navn),
                            "title": titel,
                            "type": "images",
                            "path": sti,
                            "n_pages": n,
                            "kilde": "arkiv",
                        }
                    )
            except Exception:
                pass
        elif ext in PDF_EXT:
            boeger.append(
                {
                    "id": _book_id(navn),
                    "title": titel,
                    "type": "pdf",
                    "path": sti,
                    "n_pages": None,
                    "kilde": "pdf",
                }
            )

    return boeger


@st.cache_data(ttl=600, show_spinner=False)
def load_image_pages(sti: str) -> list[str]:
    """Indlæs alle billedsider fra en mappe eller et arkiv som data-URL'er."""
    sider: list[str] = []
    if os.path.isdir(sti):
        filer = sorted(
            (f for f in os.listdir(sti) if os.path.splitext(f)[1].lower() in IMG_EXT),
            key=_natural_key,
        )
        for f in filer:
            with open(os.path.join(sti, f), "rb") as fh:
                sider.append(_data_url_from_bytes(fh.read(), f))
    else:  # arkiv
        with zipfile.ZipFile(sti) as z:
            navne = sorted(
                (
                    n
                    for n in z.namelist()
                    if os.path.splitext(n)[1].lower() in IMG_EXT and not n.endswith("/")
                ),
                key=_natural_key,
            )
            for n in navne:
                sider.append(_data_url_from_bytes(z.read(n), n))
    return sider


@st.cache_data(ttl=600, show_spinner=False)
def load_pdf(sti: str) -> str:
    with open(sti, "rb") as fh:
        return _data_url_from_bytes(fh.read(), sti)


@st.cache_data(ttl=600, show_spinner=False)
def load_cover(sti: str) -> str | None:
    """Kun første side som data-URL (billig forside til biblioteks-grid)."""
    try:
        if os.path.isdir(sti):
            filer = sorted(
                (f for f in os.listdir(sti) if os.path.splitext(f)[1].lower() in IMG_EXT),
                key=_natural_key,
            )
            if not filer:
                return None
            with open(os.path.join(sti, filer[0]), "rb") as fh:
                return _data_url_from_bytes(fh.read(), filer[0])
        with zipfile.ZipFile(sti) as z:
            navne = sorted(
                (
                    n
                    for n in z.namelist()
                    if os.path.splitext(n)[1].lower() in IMG_EXT and not n.endswith("/")
                ),
                key=_natural_key,
            )
            if not navne:
                return None
            return _data_url_from_bytes(z.read(navne[0]), navne[0])
    except Exception:
        return None


def load_first_page(bog: dict) -> str | None:
    if bog["type"] != "images":
        return None
    return load_cover(bog["path"])


# ── Upload-håndtering (session) ─────────────────────────────────────────────────
def _process_upload(uploaded) -> dict | None:
    navn = uploaded.name
    ext = os.path.splitext(navn)[1].lower()
    titel = os.path.splitext(navn)[0]
    raw = uploaded.getvalue()
    bid = "up_" + _book_id(navn)

    if ext in PDF_EXT:
        return {
            "id": bid, "title": titel, "type": "pdf", "n_pages": None,
            "kilde": "upload", "_pdf": _data_url_from_bytes(raw, navn),
        }
    if ext in ARCHIVE_EXT:
        sider = []
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            navne = sorted(
                (n for n in z.namelist()
                 if os.path.splitext(n)[1].lower() in IMG_EXT and not n.endswith("/")),
                key=_natural_key,
            )
            for n in navne:
                sider.append(_data_url_from_bytes(z.read(n), n))
        if sider:
            return {
                "id": bid, "title": titel, "type": "images", "n_pages": len(sider),
                "kilde": "upload", "_pages": sider,
            }
    if ext in IMG_EXT:
        return {
            "id": bid, "title": titel, "type": "images", "n_pages": 1,
            "kilde": "upload", "_pages": [_data_url_from_bytes(raw, navn)],
        }
    return None


# ── Sideopsætning: eget design, fjern Streamlit-/Harald-chrome ──────────────────
def inject_reader_css() -> None:
    st.markdown(
        f"""
<style>
  /* Skjul Streamlit/Harald-chrome på denne side for et rent læser-look */
  header[data-testid="stHeader"] {{ display:none !important; }}
  [data-testid="stToolbar"] {{ display:none !important; }}
  [data-testid="stDecoration"] {{ display:none !important; }}
  [data-testid="stAppViewContainer"] > .main {{ background:#0d0f14; }}
  .stApp {{ background:#0d0f14; }}
  [data-testid="stMainBlockContainer"], .block-container {{
      padding-top:1.2rem !important; padding-bottom:1rem !important;
      max-width:1400px !important;
  }}
  /* Sidebar: mørk og diskret */
  section[data-testid="stSidebar"] {{ background:#0a0c10 !important; }}
  section[data-testid="stSidebar"] * {{ color:#cbd5e1; }}

  /* Komponent-iframe uden hvid kant */
  iframe {{ border-radius:14px; }}

  /* Upload-felt + expander */
  [data-testid="stFileUploader"] {{
      background:#161922; border:1px dashed #2b3140; border-radius:12px; padding:.4rem;
  }}
  [data-testid="stFileUploader"] * {{ color:#cbd5e1 !important; }}
  [data-testid="stExpander"] {{ border:1px solid #232838 !important; border-radius:12px !important;
      background:#12151c !important; }}
  [data-testid="stExpander"] summary,
  [data-testid="stExpander"] summary p,
  [data-testid="stExpander"] details > summary span {{ color:#e7e9ee !important; font-weight:600; }}
  [data-testid="stExpander"] svg {{ fill:#cbd5e1 !important; }}
  [data-testid="stExpander"] [data-testid="stCaptionContainer"],
  [data-testid="stExpander"] [data-testid="stCaptionContainer"] * {{ color:#9aa3b2 !important; }}

  /* Knapper — overdøv Streamlits egne styles */
  div[data-testid="stButton"] > button, .stButton > button {{
      background:{ACCENT} !important; color:#fff !important; border:none !important;
      border-radius:9px !important; font-weight:600 !important; font-size:13px !important;
      letter-spacing:.2px !important; transition:filter .15s, transform .1s !important;
  }}
  div[data-testid="stButton"] > button:hover, .stButton > button:hover {{
      filter:brightness(1.12); transform:translateY(-1px);
  }}
  div[data-testid="stButton"] > button p {{ color:#fff !important; }}

  .ls-card {{ transition:transform .16s ease, box-shadow .16s ease; }}
  .ls-card:hover {{ transform:translateY(-4px); }}

  h1,h2,h3 {{ color:#f8fafc; }}
</style>
""",
        unsafe_allow_html=True,
    )


# ── Læser-komponenten (HTML/JS) — nyt, immersivt design ──────────────────────────
def render_reader(bog: dict, pages: list[str] | None, pdf_url: str | None):
    cfg = {
        "id": bog["id"],
        "title": bog["title"],
        "type": bog["type"],
        "pages": pages or [],
        "pdf": pdf_url or "",
    }
    cfg_json = json.dumps(cfg)

    html = r"""
<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
  :root { --accent:#6366f1; }
  * { box-sizing:border-box; -webkit-tap-highlight-color:transparent; }
  html,body { margin:0; padding:0; height:100%; overflow:hidden;
              font-family:'Inter',system-ui,-apple-system,sans-serif; }
  #app { position:relative; width:100%; height:100%; background:#0d0f14; color:#e7e9ee;
         display:flex; flex-direction:column; overflow:hidden; user-select:none;
         transition:background .3s; }
  #app[data-bg="dim"]   { background:#1b1f29; }
  #app[data-bg="sepia"] { background:#e9dcc3; }
  #app[data-bg="light"] { background:#dfe3ea; }

  /* ── Glas-bjælker, auto-skjul ── */
  .chrome { position:absolute; left:0; right:0; z-index:20; display:flex; align-items:center; gap:8px;
            padding:11px 16px; background:rgba(13,15,20,.62); backdrop-filter:blur(14px) saturate(1.2);
            -webkit-backdrop-filter:blur(14px) saturate(1.2);
            transition:opacity .3s, transform .3s; }
  #top { top:0; border-bottom:1px solid rgba(255,255,255,.07); }
  #bot { bottom:0; border-top:1px solid rgba(255,255,255,.07); }
  #app:not(.show) #top { opacity:0; transform:translateY(-100%); pointer-events:none; }
  #app:not(.show) #bot { opacity:0; transform:translateY(100%);  pointer-events:none; }

  .title { font-weight:600; color:#f4f5f8; font-size:13.5px; white-space:nowrap; overflow:hidden;
           text-overflow:ellipsis; max-width:34%; }
  .grow { flex:1; }
  .pill { font-variant-numeric:tabular-nums; font-weight:600; font-size:12.5px; color:#e7e9ee;
          background:rgba(255,255,255,.08); border-radius:20px; padding:5px 13px; }
  .ico { display:inline-flex; align-items:center; justify-content:center; gap:6px;
         background:rgba(255,255,255,.07); color:#dfe3ea; border:1px solid rgba(255,255,255,.09);
         border-radius:9px; height:34px; min-width:34px; padding:0 10px; font-size:13px; cursor:pointer;
         font-family:inherit; line-height:1; transition:background .12s, color .12s, border-color .12s; }
  .ico:hover { background:rgba(255,255,255,.16); color:#fff; }
  .ico.on { background:var(--accent); border-color:var(--accent); color:#fff; }
  .lbl { font-size:12.5px; font-weight:500; }

  /* ── Scene ── */
  #stage { position:relative; flex:1; overflow:auto; display:flex; align-items:flex-start;
           justify-content:center; -webkit-overflow-scrolling:touch; }
  #stage.center { align-items:center; }
  #pageimg { display:block; max-width:none; animation:fade .28s ease; }
  #pagecanvas { display:block; animation:fade .28s ease; }
  @keyframes fade { from{opacity:.0; transform:scale(.992);} to{opacity:1; transform:none;} }

  .nav { position:absolute; top:48px; bottom:56px; width:24%; z-index:10; cursor:pointer;
         display:flex; align-items:center; opacity:0; transition:opacity .2s; }
  .nav.left  { left:0;  justify-content:flex-start; }
  .nav.right { right:0; justify-content:flex-end; }
  .nav:hover { opacity:1; }
  .nav .chev { font-size:30px; color:#fff; margin:0 12px; width:46px; height:46px; border-radius:50%;
               background:rgba(13,15,20,.55); display:flex; align-items:center; justify-content:center;
               backdrop-filter:blur(6px); }

  #loader { position:absolute; inset:0; display:flex; align-items:center; justify-content:center;
            color:#8b92a3; font-size:13px; z-index:5; }

  /* ── Slider ── */
  #slider { flex:1; -webkit-appearance:none; height:5px; border-radius:5px;
            background:rgba(255,255,255,.16); outline:none; }
  #slider::-webkit-slider-thumb { -webkit-appearance:none; width:15px; height:15px; border-radius:50%;
            background:var(--accent); cursor:pointer; border:2px solid #fff; box-shadow:0 1px 4px rgba(0,0,0,.5); }
  #slider::-moz-range-thumb { width:15px; height:15px; border-radius:50%; background:var(--accent);
            cursor:pointer; border:2px solid #fff; }

  /* ── Side-oversigt (thumbnails) ── */
  #overview { position:absolute; inset:0; z-index:40; background:rgba(8,9,13,.96);
              backdrop-filter:blur(8px); display:none; flex-direction:column; }
  #overview.open { display:flex; }
  #ovhead { display:flex; align-items:center; gap:10px; padding:14px 18px;
            border-bottom:1px solid rgba(255,255,255,.08); }
  #ovhead .t { font-weight:600; font-size:14px; color:#f4f5f8; }
  #ovgrid { flex:1; overflow:auto; display:grid; gap:14px; padding:18px;
            grid-template-columns:repeat(auto-fill, minmax(120px,1fr)); }
  .thumb { cursor:pointer; border-radius:8px; overflow:hidden; border:2px solid transparent;
           background:#161922; transition:border-color .12s, transform .12s; position:relative; }
  .thumb:hover { transform:translateY(-3px); }
  .thumb.cur { border-color:var(--accent); }
  .thumb img, .thumb canvas { width:100%; display:block; aspect-ratio:2/3; object-fit:cover; background:#0d0f14; }
  .thumb .num { position:absolute; bottom:0; left:0; right:0; font-size:11px; text-align:center;
                background:rgba(8,9,13,.78); color:#cbd5e1; padding:3px 0; font-weight:600; }

  .hint { position:absolute; bottom:74px; left:50%; transform:translateX(-50%);
          background:rgba(13,15,20,.86); color:#cbd5e1; font-size:11.5px; padding:7px 14px;
          border-radius:22px; border:1px solid rgba(255,255,255,.1); z-index:15; pointer-events:none;
          transition:opacity .5s; }
</style></head>
<body>
<div id="app" class="show">

  <div class="chrome" id="top">
    <span class="title" id="t"></span>
    <span class="grow"></span>
    <button class="ico" id="dir" title="Læseretning (d)"><span class="lbl">→ V&rarr;H</span></button>
    <button class="ico" id="bg"  title="Baggrund / tema (t)">◐</button>
    <button class="ico" id="grid" title="Side-oversigt (g)">▦</button>
    <button class="ico" id="fs"  title="Fuldskærm (f)">⛶</button>
  </div>

  <div id="stage">
    <div class="nav left"  id="navL"><span class="chev">‹</span></div>
    <div class="nav right" id="navR"><span class="chev">›</span></div>
    <div id="loader">Indlæser…</div>
    <img id="pageimg" style="display:none">
    <canvas id="pagecanvas" style="display:none"></canvas>
  </div>

  <div class="hint" id="hint">← → bladr · klik i siderne · swipe · dobbeltklik zoomer · g = oversigt</div>

  <div class="chrome" id="bot">
    <button class="ico" id="prev" title="Forrige">‹</button>
    <input type="range" id="slider" min="0" max="0" value="0">
    <span class="pill" id="ind">– / –</span>
    <button class="ico" id="next" title="Næste">›</button>
    <span style="width:8px"></span>
    <button class="ico" id="zfw" title="Tilpas bredde (w)"><span class="lbl">↔</span></button>
    <button class="ico" id="zfh" title="Tilpas højde (h)"><span class="lbl">↕</span></button>
    <button class="ico" id="zout" title="Zoom ud (−)">−</button>
    <span class="pill" id="zind" style="min-width:62px;text-align:center;">100%</span>
    <button class="ico" id="zin" title="Zoom ind (+)">+</button>
  </div>

  <div id="overview">
    <div id="ovhead">
      <span class="t">Oversigt</span><span class="grow" style="flex:1"></span>
      <button class="ico" id="ovclose">Luk ✕</button>
    </div>
    <div id="ovgrid"></div>
  </div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"></script>
<script>
const CFG = __CFG__;
const KEY = "harald_book_" + CFG.id;
const KEY_DIR = "ls_reader_dir";
const KEY_ZOOM = "ls_reader_zoom";
const KEY_BG = "ls_reader_bg";

const app = document.getElementById('app');
const stage = document.getElementById('stage');
const img = document.getElementById('pageimg');
const canvas = document.getElementById('pagecanvas');
const loader = document.getElementById('loader');
const indEl = document.getElementById('ind');
const sliderEl = document.getElementById('slider');
const zindEl = document.getElementById('zind');
const hintEl = document.getElementById('hint');
const ovEl = document.getElementById('overview');
const ovGrid = document.getElementById('ovgrid');
document.getElementById('t').textContent = CFG.title;

let total = 0, cur = 0, pdfDoc = null;
let zoomMode = localStorage.getItem(KEY_ZOOM) || 'width';
let rtl = localStorage.getItem(KEY_DIR) === 'rtl';
const BGS = ['dark', 'dim', 'sepia', 'light'];
let bg = localStorage.getItem(KEY_BG) || 'dark';
let ovBuilt = false;

async function init() {
  app.setAttribute('data-bg', bg);
  const saved = parseInt(localStorage.getItem(KEY) || "0", 10);
  if (CFG.type === 'pdf') {
    if (!window.pdfjsLib) { loader.textContent = "Kunne ikke indlæse PDF-motor (ingen netværk?)"; return; }
    pdfjsLib.GlobalWorkerOptions.workerSrc =
      "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
    try { pdfDoc = await pdfjsLib.getDocument(CFG.pdf).promise; total = pdfDoc.numPages; }
    catch (e) { loader.textContent = "Kunne ikke åbne PDF: " + e; return; }
    img.style.display = 'none'; canvas.style.display = 'block';
  } else {
    total = CFG.pages.length;
    canvas.style.display = 'none'; img.style.display = 'block';
  }
  sliderEl.max = Math.max(0, total - 1);
  applyDir();
  cur = Math.min(Math.max(saved, 0), total - 1);
  await show(cur);
  poke();
  setTimeout(() => { hintEl.style.opacity = '0'; }, 4600);
}

function applyDir() { document.getElementById('dir').innerHTML =
  rtl ? '<span class="lbl">← H&rarr;V</span>' : '<span class="lbl">→ V&rarr;H</span>'; }

async function renderPdfPage(n, target, scaleOverride) {
  const page = await pdfDoc.getPage(n + 1);
  const base = page.getViewport({ scale: 1 });
  let scale = scaleOverride;
  if (scale == null) {
    if (zoomMode === 'width')       scale = (stage.clientWidth - 4) / base.width;
    else if (zoomMode === 'height') scale = (stage.clientHeight - 4) / base.height;
    else scale = parseFloat(zoomMode) * ((stage.clientWidth - 4) / base.width);
  }
  const dpr = window.devicePixelRatio || 1;
  const vp = page.getViewport({ scale: scale * dpr });
  const cnv = target || canvas;
  cnv.width = vp.width; cnv.height = vp.height;
  cnv.style.width = (vp.width / dpr) + 'px'; cnv.style.height = (vp.height / dpr) + 'px';
  await page.render({ canvasContext: cnv.getContext('2d'), viewport: vp }).promise;
}

function applyImgZoom() {
  if (zoomMode === 'width')        { img.style.width = '100%'; img.style.height = 'auto'; }
  else if (zoomMode === 'height')  { img.style.height = (stage.clientHeight - 4) + 'px'; img.style.width = 'auto'; }
  else { img.style.width = (stage.clientWidth * parseFloat(zoomMode)) + 'px'; img.style.height = 'auto'; }
}

async function show(n) {
  if (total === 0) { loader.textContent = "Ingen sider"; return; }
  n = Math.min(Math.max(n, 0), total - 1); cur = n;
  loader.style.display = 'flex';
  if (CFG.type === 'pdf') {
    await renderPdfPage(n);
  } else {
    img.style.animation = 'none'; void img.offsetWidth; img.style.animation = '';
    await new Promise((res) => { img.onload = res; img.onerror = res; img.src = CFG.pages[n]; });
    applyImgZoom();
    [n + 1, n - 1].forEach((k) => { if (k >= 0 && k < total) { const p = new Image(); p.src = CFG.pages[k]; } });
  }
  loader.style.display = 'none';
  stage.scrollTop = 0; stage.scrollLeft = 0;
  updateHud(); localStorage.setItem(KEY, String(n));
}

function updateHud() {
  indEl.textContent = (cur + 1) + " / " + total;
  sliderEl.value = cur; updateZoomInd();
  ovGrid.querySelectorAll('.thumb').forEach((t, i) => t.classList.toggle('cur', i === cur));
}
function updateZoomInd() {
  zindEl.textContent = (zoomMode === 'width') ? 'Bredde'
                     : (zoomMode === 'height') ? 'Højde'
                     : Math.round(parseFloat(zoomMode) * 100) + '%';
}

function next() { show(cur + 1); } function prev() { show(cur - 1); }
function advance() { rtl ? prev() : next(); } function back() { rtl ? next() : prev(); }

function setZoom(mode) {
  zoomMode = mode; localStorage.setItem(KEY_ZOOM, String(mode));
  if (CFG.type === 'pdf') renderPdfPage(cur); else applyImgZoom();
  stage.classList.toggle('center', mode === 'height'); updateZoomInd();
}
function zoomBy(f) {
  let base = (zoomMode === 'width' || zoomMode === 'height') ? 1 : parseFloat(zoomMode);
  setZoom(Math.min(4, Math.max(0.25, +(base * f).toFixed(2))));
}

// ── Side-oversigt ──
async function buildOverview() {
  if (ovBuilt) return; ovBuilt = true;
  for (let i = 0; i < total; i++) {
    const d = document.createElement('div'); d.className = 'thumb'; d.dataset.i = i;
    if (CFG.type === 'pdf') {
      const c = document.createElement('canvas'); d.appendChild(c);
      renderPdfPage(i, c, 0.22).catch(() => {});
    } else {
      const im = document.createElement('img'); im.loading = 'lazy'; im.src = CFG.pages[i]; d.appendChild(im);
    }
    const num = document.createElement('div'); num.className = 'num'; num.textContent = i + 1; d.appendChild(num);
    d.onclick = () => { show(i); closeOverview(); };
    ovGrid.appendChild(d);
  }
}
function openOverview() { buildOverview(); ovEl.classList.add('open'); updateHud();
  const c = ovGrid.querySelector('.thumb.cur'); if (c) c.scrollIntoView({ block: 'center' }); }
function closeOverview() { ovEl.classList.remove('open'); }

// ── Auto-skjul af bjælker ──
let hideTimer = null;
function poke() {
  app.classList.add('show');
  clearTimeout(hideTimer);
  hideTimer = setTimeout(() => { if (!ovEl.classList.contains('open')) app.classList.remove('show'); }, 2600);
}
['mousemove', 'touchstart', 'keydown', 'click'].forEach(e => window.addEventListener(e, poke, { passive: true }));

// ── Knapper ──
document.getElementById('zfw').onclick = () => setZoom('width');
document.getElementById('zfh').onclick = () => setZoom('height');
document.getElementById('zin').onclick = () => zoomBy(1.25);
document.getElementById('zout').onclick = () => zoomBy(0.8);
document.getElementById('prev').onclick = back;
document.getElementById('next').onclick = advance;
document.getElementById('navL').onclick = () => (rtl ? next() : prev());
document.getElementById('navR').onclick = () => (rtl ? prev() : next());
document.getElementById('dir').onclick = () => { rtl = !rtl; localStorage.setItem(KEY_DIR, rtl ? 'rtl' : 'ltr'); applyDir(); };
document.getElementById('bg').onclick = () => {
  bg = BGS[(BGS.indexOf(bg) + 1) % BGS.length]; app.setAttribute('data-bg', bg); localStorage.setItem(KEY_BG, bg);
};
document.getElementById('grid').onclick = openOverview;
document.getElementById('ovclose').onclick = closeOverview;
sliderEl.oninput = () => show(parseInt(sliderEl.value, 10));
document.getElementById('fs').onclick = () => {
  if (document.fullscreenElement) document.exitFullscreen();
  else if (app.requestFullscreen) app.requestFullscreen();
};

// ── Tastatur ──
window.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') { closeOverview(); return; }
  if (['ArrowRight', 'PageDown', ' '].includes(e.key)) { e.preventDefault(); advance(); }
  else if (['ArrowLeft', 'PageUp'].includes(e.key)) { e.preventDefault(); back(); }
  else if (e.key === 'Home') show(0);
  else if (e.key === 'End') show(total - 1);
  else if (e.key === '+' || e.key === '=') zoomBy(1.25);
  else if (e.key === '-') zoomBy(0.8);
  else if (e.key.toLowerCase() === 'f') document.getElementById('fs').click();
  else if (e.key.toLowerCase() === 'w') setZoom('width');
  else if (e.key.toLowerCase() === 'h') setZoom('height');
  else if (e.key.toLowerCase() === 'g') openOverview();
  else if (e.key.toLowerCase() === 'd') document.getElementById('dir').click();
  else if (e.key.toLowerCase() === 't') document.getElementById('bg').click();
});

// ── Touch: swipe + dobbelt-tap ──
let tx = 0, ty = 0, tt = 0, lastTap = 0;
stage.addEventListener('touchstart', (e) => {
  if (e.touches.length === 1) { tx = e.touches[0].clientX; ty = e.touches[0].clientY; tt = Date.now(); }
}, { passive: true });
stage.addEventListener('touchend', (e) => {
  const dt = Date.now() - tt;
  const dx = (e.changedTouches[0].clientX - tx), dy = (e.changedTouches[0].clientY - ty);
  const now = Date.now();
  if (Math.abs(dx) < 12 && Math.abs(dy) < 12) {
    if (now - lastTap < 320) { setZoom((zoomMode === 'width') ? 1.6 : 'width'); lastTap = 0; return; }
    lastTap = now;
  }
  if (dt < 600 && Math.abs(dx) > 55 && Math.abs(dx) > Math.abs(dy) * 1.4) {
    if (stage.scrollWidth <= stage.clientWidth + 8) { if (dx < 0) advance(); else back(); }
  }
}, { passive: true });
stage.addEventListener('dblclick', () => setZoom((zoomMode === 'width') ? 1.6 : 'width'));
window.addEventListener('resize', () => { if (CFG.type === 'pdf') renderPdfPage(cur); else applyImgZoom(); });

init();
</script>
</body></html>
"""
    html = html.replace("__CFG__", cfg_json)
    st.components.v1.html(html, height=880, scrolling=False)


# ── Sidebar ──────────────────────────────────────────────────────────────────────
inject_reader_css()
with st.sidebar:
    st.markdown(
        "<div style='padding:1rem .4rem .6rem;'>"
        "<div style='font-family:Georgia,serif;font-size:1.25rem;font-weight:700;color:#f8fafc;'>Læsesal</div>"
        "<div style='font-size:11px;color:#8b92a3;letter-spacing:.4px;'>Bog- &amp; manga-læser</div>"
        "</div>",
        unsafe_allow_html=True,
    )
sidebar_log_ud()

if "_uploadede_boeger" not in st.session_state:
    st.session_state["_uploadede_boeger"] = {}


# ── Hoved-UI ───────────────────────────────────────────────────────────────────
valgt_id = st.session_state.get("_aktiv_bog")

if valgt_id:
    bog = None
    pages = None
    pdf_url = None
    if valgt_id in st.session_state["_uploadede_boeger"]:
        bog = st.session_state["_uploadede_boeger"][valgt_id]
        pages = bog.get("_pages")
        pdf_url = bog.get("_pdf")
    else:
        for b in scan_books():
            if b["id"] == valgt_id:
                bog = b
                break
        if bog:
            if bog["type"] == "images":
                pages = load_image_pages(bog["path"])
            else:
                pdf_url = load_pdf(bog["path"])

    if not bog:
        st.session_state.pop("_aktiv_bog", None)
        st.rerun()

    c1, c2 = st.columns([1, 6])
    with c1:
        if st.button("← Bibliotek", use_container_width=True):
            st.session_state.pop("_aktiv_bog", None)
            st.rerun()
    with c2:
        st.markdown(
            f"<div style='font-family:Georgia,serif;font-weight:700;font-size:1.1rem;color:#f8fafc;"
            f"padding-top:.3rem;'>{bog['title']}</div>",
            unsafe_allow_html=True,
        )

    render_reader(bog, pages, pdf_url)

else:
    # ── Biblioteks-visning ───────────────────────────────────────────────────────
    st.markdown(
        f"""
<div style="padding:1.5rem 0 1.2rem;">
  <div style="font-family:Georgia,'Times New Roman',serif;font-size:clamp(1.8rem,3vw,2.5rem);
              font-weight:700;color:#f8fafc;letter-spacing:-0.5px;line-height:1.1;">Læsesal</div>
  <div style="height:3px;width:46px;background:linear-gradient(90deg,{ACCENT},{ACCENT_2});
              border-radius:3px;margin:.8rem 0 1rem;"></div>
  <div style="font-size:13.5px;color:#9aa3b2;max-width:64ch;line-height:1.65;">
    Dit personlige bibliotek. Vælg en bog og fortsæt præcis hvor du slap.
    Tilføj bøger i mappen <code style="color:#c7cdd9;background:#1b1f29;padding:1px 6px;border-radius:5px;">boeger/</code>
    eller upload dem herunder — manga (billeder), CBZ/ZIP og PDF understøttes.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    with st.expander("➕  Tilføj en bog  ·  upload billeder, CBZ/ZIP eller PDF", expanded=False):
        st.caption(
            "Upload kun materiale du har lov til at bruge. Filer ligger i din session; "
            "vil du beholde en bog permanent, så læg den i `boeger/`-mappen."
        )
        up = st.file_uploader(
            "Vælg fil",
            type=["pdf", "cbz", "zip", "jpg", "jpeg", "png", "webp", "gif", "avif", "bmp"],
            accept_multiple_files=False,
            label_visibility="collapsed",
        )
        if up is not None:
            try:
                ny = _process_upload(up)
                if ny:
                    st.session_state["_uploadede_boeger"][ny["id"]] = ny
                    st.success(f"„{ny['title']}” er klar i biblioteket nedenfor.")
                else:
                    st.warning("Filtypen kunne ikke læses som en bog.")
            except Exception as e:
                st.error(f"Kunne ikke behandle filen: {e}")

    repo_boeger = scan_books()
    upload_boeger = list(st.session_state["_uploadede_boeger"].values())
    alle = upload_boeger + repo_boeger

    if not alle:
        st.info(
            "Ingen bøger endnu. Læg en mappe med billedsider (eller en .cbz/.pdf-fil) "
            "i `boeger/`-mappen, eller upload en fil ovenfor."
        )
    else:
        st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)
        kolonner = st.columns(5, gap="medium")
        for i, b in enumerate(alle):
            with kolonner[i % 5]:
                cover = b.get("_pages", [None])[0] if b["kilde"] == "upload" else load_first_page(b)
                badge = {"pdf": "PDF", "arkiv": "CBZ", "mappe": "Serie", "upload": "Upload"}.get(b["kilde"], "Bog")
                sider_txt = f"{b['n_pages']} sider" if b.get("n_pages") else "PDF"

                if cover:
                    cover_html = (
                        f"<img src='{cover}' style='width:100%;aspect-ratio:2/3;object-fit:cover;"
                        f"display:block;background:#0d0f14;'/>"
                    )
                else:
                    cover_html = (
                        "<div style='width:100%;aspect-ratio:2/3;"
                        f"background:linear-gradient(150deg,{ACCENT}22,#0d0f14 70%);display:flex;"
                        "align-items:center;justify-content:center;font-size:40px;color:#475569;'>📕</div>"
                    )

                st.markdown(
                    f"""
<div class="ls-card" style="border-radius:12px;overflow:hidden;background:#161922;
     border:1px solid #232838;box-shadow:0 6px 18px rgba(0,0,0,.35);">
  <div style="position:relative;">
    {cover_html}
    <span style="position:absolute;top:8px;left:8px;font-size:9px;font-weight:700;
                 letter-spacing:.6px;text-transform:uppercase;color:#fff;
                 background:rgba(13,15,20,.7);backdrop-filter:blur(4px);
                 padding:3px 8px;border-radius:20px;">{badge}</span>
  </div>
  <div style="padding:.7rem .8rem .15rem;">
    <div style="font-size:13px;font-weight:600;color:#f1f3f7;line-height:1.35;min-height:2.6em;
                display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;"
         title="{b['title']}">{b['title']}</div>
    <div style="font-size:10.5px;color:#7c8492;margin-top:3px;">{sider_txt}</div>
  </div>
</div>
""",
                    unsafe_allow_html=True,
                )
                if st.button("Læs  ›", key=f"open_{b['id']}", use_container_width=True):
                    st.session_state["_aktiv_bog"] = b["id"]
                    st.rerun()
