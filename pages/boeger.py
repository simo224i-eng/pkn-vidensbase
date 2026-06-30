"""Bog-/manga-læser til Harald-vidensbasen.

En selvstændig fane der lader brugeren læse billed-baserede bøger (manga,
scannede sider), CBZ/ZIP-arkiver og PDF'er med en flydende læseroplevelse:
bladring (tastatur/swipe/klik), zoom (fit-bredde/-højde/pinch), fuldskærm,
læseretning (venstre→højre / højre→venstre), og hukommelse for sidst læste
side pr. bog (gemt i browseren via localStorage).

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

from shared import inject_css, logo, sidebar_log_ud

# ── Adgangskontrol ─────────────────────────────────────────────────────────────
if not st.session_state.get("_autentificeret_v2"):
    st.switch_page("app.py")
    st.stop()

inject_css()

# ── Konstanter ─────────────────────────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOK_DIR = os.path.join(_ROOT, "boeger")

IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".avif", ".bmp"}
ARCHIVE_EXT = {".cbz", ".zip"}
PDF_EXT = {".pdf"}

ACCENT = "#8C1C2E"


# ── Hjælpere ───────────────────────────────────────────────────────────────────
def _natural_key(navn: str):
    """Sortér 'side2' før 'side10' (naturlig/menneskelig sortering)."""
    import re

    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", navn)]


def _data_url_from_bytes(raw: bytes, filnavn: str) -> str:
    mime = mimetypes.guess_type(filnavn)[0]
    if mime is None:
        if filnavn.lower().endswith(".svg"):
            mime = "image/svg+xml"
        else:
            mime = "application/octet-stream"
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
    """Forsidebillede (første side) til biblioteks-grid. None for PDF."""
    if bog["type"] != "images":
        return None
    return load_cover(bog["path"])


# ── Upload-håndtering (session) ─────────────────────────────────────────────────
def _process_upload(uploaded) -> dict | None:
    """Konvertér en uploadet fil til en bog-dict med sider i session_state."""
    navn = uploaded.name
    ext = os.path.splitext(navn)[1].lower()
    titel = os.path.splitext(navn)[0]
    raw = uploaded.getvalue()
    bid = "up_" + _book_id(navn)

    if ext in PDF_EXT:
        return {
            "id": bid,
            "title": titel,
            "type": "pdf",
            "n_pages": None,
            "kilde": "upload",
            "_pdf": _data_url_from_bytes(raw, navn),
        }
    if ext in ARCHIVE_EXT:
        sider = []
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
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
        if sider:
            return {
                "id": bid,
                "title": titel,
                "type": "images",
                "n_pages": len(sider),
                "kilde": "upload",
                "_pages": sider,
            }
    if ext in IMG_EXT:
        return {
            "id": bid,
            "title": titel,
            "type": "images",
            "n_pages": 1,
            "kilde": "upload",
            "_pages": [_data_url_from_bytes(raw, navn)],
        }
    return None


# ── Læser-komponenten (HTML/JS) ──────────────────────────────────────────────────
def render_reader(bog: dict, pages: list[str] | None, pdf_url: str | None):
    cfg = {
        "id": bog["id"],
        "title": bog["title"],
        "type": bog["type"],
        "pages": pages or [],
        "pdf": pdf_url or "",
    }
    cfg_json = json.dumps(cfg)

    html = """
<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
  :root { --accent:#8C1C2E; }
  * { box-sizing:border-box; -webkit-tap-highlight-color:transparent; }
  html,body { margin:0; padding:0; height:100%; font-family:Inter,system-ui,-apple-system,sans-serif; }
  #app { position:relative; width:100%; height:100%; background:#0b0f1a; color:#e2e8f0;
         display:flex; flex-direction:column; overflow:hidden; user-select:none; }
  #app.fs { position:fixed; inset:0; z-index:99999; }

  #bar { display:flex; align-items:center; gap:10px; padding:8px 14px; background:rgba(15,23,42,.96);
         border-bottom:1px solid #1e293b; font-size:12px; flex:0 0 auto; z-index:5;
         transition:opacity .25s; }
  #bar .title { font-weight:600; color:#f1f5f9; white-space:nowrap; overflow:hidden;
                text-overflow:ellipsis; max-width:30%; }
  #bar .spacer { flex:1; }
  #bar .ind { font-variant-numeric:tabular-nums; color:#94a3b8; font-weight:600; min-width:74px; text-align:center;}
  .btn { background:#1e293b; color:#cbd5e1; border:1px solid #334155; border-radius:6px;
         padding:5px 9px; font-size:12px; cursor:pointer; font-family:inherit; line-height:1;
         transition:background .12s,color .12s; white-space:nowrap; }
  .btn:hover { background:#334155; color:#fff; }
  .btn.on { background:var(--accent); border-color:var(--accent); color:#fff; }

  #stage { position:relative; flex:1; overflow:auto; display:flex; align-items:flex-start;
           justify-content:center; scroll-behavior:smooth; -webkit-overflow-scrolling:touch; }
  #stage.center { align-items:center; }
  #pageimg { display:block; max-width:none; transition:opacity .12s; }
  #pagecanvas { display:block; }

  /* tap-zoner til bladring */
  .nav { position:absolute; top:0; bottom:0; width:22%; z-index:3; cursor:pointer;
         display:flex; align-items:center; opacity:0; transition:opacity .2s; }
  .nav.left { left:0; justify-content:flex-start; }
  .nav.right { right:0; justify-content:flex-end; }
  .nav:hover { opacity:1; }
  .nav .chev { font-size:34px; color:#fff; padding:0 14px; text-shadow:0 1px 6px rgba(0,0,0,.7); }

  #loader { position:absolute; inset:0; display:flex; align-items:center; justify-content:center;
            color:#64748b; font-size:13px; z-index:2; }

  #foot { display:flex; align-items:center; gap:12px; padding:8px 16px; background:rgba(15,23,42,.96);
          border-top:1px solid #1e293b; flex:0 0 auto; z-index:5; }
  #slider { flex:1; -webkit-appearance:none; height:4px; border-radius:4px; background:#334155; outline:none; }
  #slider::-webkit-slider-thumb { -webkit-appearance:none; width:14px; height:14px; border-radius:50%;
            background:var(--accent); cursor:pointer; border:2px solid #fff; }
  #slider::-moz-range-thumb { width:14px; height:14px; border-radius:50%; background:var(--accent);
            cursor:pointer; border:2px solid #fff; }
  #foot .pct { font-size:11px; color:#94a3b8; min-width:38px; text-align:right; font-variant-numeric:tabular-nums; }

  .hint { position:absolute; bottom:60px; left:50%; transform:translateX(-50%); background:rgba(15,23,42,.92);
          color:#cbd5e1; font-size:11px; padding:6px 12px; border-radius:20px; border:1px solid #334155;
          z-index:6; pointer-events:none; transition:opacity .4s; }
</style></head>
<body>
<div id="app">
  <div id="bar">
    <span class="title" id="t"></span>
    <button class="btn" id="dir" title="Læseretning">→ V→H</button>
    <span class="spacer"></span>
    <button class="btn" id="zfw" title="Tilpas bredde">↔ Bredde</button>
    <button class="btn" id="zfh" title="Tilpas højde">↕ Højde</button>
    <button class="btn" id="zout">−</button>
    <span class="ind" id="zind">100%</span>
    <button class="btn" id="zin">+</button>
    <span class="spacer"></span>
    <span class="ind" id="ind">– / –</span>
    <button class="btn" id="fs" title="Fuldskærm">⛶</button>
  </div>

  <div id="stage">
    <div class="nav left" id="navL"><span class="chev">‹</span></div>
    <div class="nav right" id="navR"><span class="chev">›</span></div>
    <div id="loader">Indlæser…</div>
    <img id="pageimg" style="display:none">
    <canvas id="pagecanvas" style="display:none"></canvas>
  </div>
  <div class="hint" id="hint">Bladr med ← →, swipe eller klik i siderne · dobbeltklik zoomer</div>

  <div id="foot">
    <input type="range" id="slider" min="0" max="0" value="0">
    <span class="pct" id="pct">0%</span>
  </div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"></script>
<script>
const CFG = __CFG__;
const KEY = "harald_book_" + CFG.id;
const KEY_DIR = "harald_reader_dir";
const KEY_ZOOM = "harald_reader_zoom";

const stage = document.getElementById('stage');
const img = document.getElementById('pageimg');
const canvas = document.getElementById('pagecanvas');
const loader = document.getElementById('loader');
const indEl = document.getElementById('ind');
const sliderEl = document.getElementById('slider');
const pctEl = document.getElementById('pct');
const zindEl = document.getElementById('zind');
const hintEl = document.getElementById('hint');
document.getElementById('t').textContent = CFG.title;

let total = 0;            // antal sider
let cur = 0;              // nuværende sideindeks (0-baseret)
let zoomMode = localStorage.getItem(KEY_ZOOM) || 'width';  // 'width' | 'height' | <number>
let rtl = localStorage.getItem(KEY_DIR) === 'rtl';         // højre→venstre (manga)
let pdfDoc = null;

// ── PDF eller billeder ──────────────────────────────────────────────────────
async function init() {
  // gem-position
  const saved = parseInt(localStorage.getItem(KEY) || "0", 10);

  if (CFG.type === 'pdf') {
    if (!window.pdfjsLib) { loader.textContent = "Kunne ikke indlæse PDF-motor (ingen netværk?)"; return; }
    pdfjsLib.GlobalWorkerOptions.workerSrc =
      "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
    try {
      pdfDoc = await pdfjsLib.getDocument(CFG.pdf).promise;
      total = pdfDoc.numPages;
    } catch (e) { loader.textContent = "Kunne ikke åbne PDF: " + e; return; }
    img.style.display = 'none'; canvas.style.display = 'block';
  } else {
    total = CFG.pages.length;
    canvas.style.display = 'none'; img.style.display = 'block';
  }

  sliderEl.max = Math.max(0, total - 1);
  applyDir();
  cur = Math.min(Math.max(saved, 0), total - 1);
  await show(cur);
  setTimeout(() => { hintEl.style.opacity = '0'; }, 4200);
}

function applyDir() {
  document.getElementById('dir').textContent = rtl ? "← H→V" : "→ V→H";
}

async function renderPdfPage(n) {
  const page = await pdfDoc.getPage(n + 1);
  const base = page.getViewport({ scale: 1 });
  let scale;
  if (zoomMode === 'width')      scale = (stage.clientWidth - 4) / base.width;
  else if (zoomMode === 'height')scale = (stage.clientHeight - 4) / base.height;
  else                            scale = parseFloat(zoomMode) *
                                          ((stage.clientWidth - 4) / base.width);
  const vp = page.getViewport({ scale: scale * (window.devicePixelRatio || 1) });
  canvas.width = vp.width; canvas.height = vp.height;
  canvas.style.width = (vp.width / (window.devicePixelRatio || 1)) + 'px';
  canvas.style.height = (vp.height / (window.devicePixelRatio || 1)) + 'px';
  await page.render({ canvasContext: canvas.getContext('2d'), viewport: vp }).promise;
}

function applyImgZoom() {
  if (zoomMode === 'width')        { img.style.width = '100%'; img.style.height = 'auto'; }
  else if (zoomMode === 'height')  { img.style.height = (stage.clientHeight - 4) + 'px'; img.style.width = 'auto'; }
  else { img.style.width = (stage.clientWidth * parseFloat(zoomMode)) + 'px'; img.style.height = 'auto'; }
}

async function show(n) {
  if (total === 0) { loader.textContent = "Ingen sider"; return; }
  n = Math.min(Math.max(n, 0), total - 1);
  cur = n;
  loader.style.display = 'flex';
  if (CFG.type === 'pdf') {
    await renderPdfPage(n);
  } else {
    await new Promise((res) => {
      img.onload = res; img.onerror = res; img.src = CFG.pages[n];
    });
    applyImgZoom();
    // preload nabo-sider
    [n + 1, n - 1].forEach((k) => { if (k >= 0 && k < total) { const p = new Image(); p.src = CFG.pages[k]; } });
  }
  loader.style.display = 'none';
  stage.scrollTop = 0; stage.scrollLeft = 0;
  updateHud();
  localStorage.setItem(KEY, String(n));
}

function updateHud() {
  indEl.textContent = (cur + 1) + " / " + total;
  sliderEl.value = cur;
  pctEl.textContent = Math.round(((cur + 1) / total) * 100) + "%";
  updateZoomInd();
}
function updateZoomInd() {
  zindEl.textContent = (zoomMode === 'width') ? 'Bredde'
                      : (zoomMode === 'height') ? 'Højde'
                      : Math.round(parseFloat(zoomMode) * 100) + '%';
}

// ── Navigation (respekterer læseretning) ─────────────────────────────────────
function next() { show(cur + 1); }
function prev() { show(cur - 1); }
function advance() { rtl ? prev() : next(); }   // "fremad i bogen"
function back()    { rtl ? next() : prev(); }

// ── Zoom-styring ─────────────────────────────────────────────────────────────
function setZoom(mode) {
  zoomMode = mode;
  localStorage.setItem(KEY_ZOOM, String(mode));
  if (CFG.type === 'pdf') renderPdfPage(cur); else applyImgZoom();
  stage.classList.toggle('center', mode === 'height');
  updateZoomInd();
}
function zoomBy(f) {
  let base = (zoomMode === 'width' || zoomMode === 'height') ? 1 : parseFloat(zoomMode);
  setZoom(Math.min(4, Math.max(0.25, +(base * f).toFixed(2))));
}

// ── Knapper ──────────────────────────────────────────────────────────────────
document.getElementById('zfw').onclick = () => setZoom('width');
document.getElementById('zfh').onclick = () => setZoom('height');
document.getElementById('zin').onclick = () => zoomBy(1.25);
document.getElementById('zout').onclick = () => zoomBy(0.8);
document.getElementById('navL').onclick = () => (rtl ? next() : prev());
document.getElementById('navR').onclick = () => (rtl ? prev() : next());
document.getElementById('dir').onclick = () => {
  rtl = !rtl; localStorage.setItem(KEY_DIR, rtl ? 'rtl' : 'ltr'); applyDir();
};
sliderEl.oninput = () => show(parseInt(sliderEl.value, 10));

const app = document.getElementById('app');
document.getElementById('fs').onclick = () => {
  if (document.fullscreenElement) document.exitFullscreen();
  else if (app.requestFullscreen) app.requestFullscreen();
  else app.classList.toggle('fs');   // fallback
};

// ── Tastatur ─────────────────────────────────────────────────────────────────
window.addEventListener('keydown', (e) => {
  if (['ArrowRight', 'PageDown', ' '].includes(e.key)) { e.preventDefault(); advance(); }
  else if (['ArrowLeft', 'PageUp'].includes(e.key)) { e.preventDefault(); back(); }
  else if (e.key === 'Home') show(0);
  else if (e.key === 'End') show(total - 1);
  else if (e.key === '+' || e.key === '=') zoomBy(1.25);
  else if (e.key === '-') zoomBy(0.8);
  else if (e.key.toLowerCase() === 'f') document.getElementById('fs').click();
  else if (e.key.toLowerCase() === 'w') setZoom('width');
  else if (e.key.toLowerCase() === 'h') setZoom('height');
});

// ── Touch: swipe + dobbelt-tap ───────────────────────────────────────────────
let tx = 0, ty = 0, tt = 0, lastTap = 0;
stage.addEventListener('touchstart', (e) => {
  if (e.touches.length === 1) { tx = e.touches[0].clientX; ty = e.touches[0].clientY; tt = Date.now(); }
}, { passive: true });
stage.addEventListener('touchend', (e) => {
  const dt = Date.now() - tt;
  const dx = (e.changedTouches[0].clientX - tx);
  const dy = (e.changedTouches[0].clientY - ty);
  // dobbelt-tap zoom
  const now = Date.now();
  if (Math.abs(dx) < 12 && Math.abs(dy) < 12) {
    if (now - lastTap < 320) { setZoom((zoomMode === 'width') ? 1.6 : 'width'); lastTap = 0; return; }
    lastTap = now;
  }
  // swipe (kun hvis ikke zoomet ud over skærmen vandret)
  if (dt < 600 && Math.abs(dx) > 55 && Math.abs(dx) > Math.abs(dy) * 1.4) {
    if (stage.scrollWidth <= stage.clientWidth + 8) {
      if (dx < 0) advance(); else back();
    }
  }
}, { passive: true });

// dobbeltklik (mus) zoomer
stage.addEventListener('dblclick', () => setZoom((zoomMode === 'width') ? 1.6 : 'width'));

window.addEventListener('resize', () => { if (CFG.type === 'pdf') renderPdfPage(cur); else applyImgZoom(); });

init();
</script>
</body></html>
"""
    html = html.replace("__CFG__", cfg_json)
    st.components.v1.html(html, height=840, scrolling=False)


# ── Sidebar ──────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        f'<div class="h-brand-wrap"><div class="h-logo-box">{logo(120, dark=True)}</div></div>',
        unsafe_allow_html=True,
    )
sidebar_log_ud()

# session-uploads
if "_uploadede_boeger" not in st.session_state:
    st.session_state["_uploadede_boeger"] = {}


# ── Hoved-UI ───────────────────────────────────────────────────────────────────
valgt_id = st.session_state.get("_aktiv_bog")

if valgt_id:
    # ── Læser-visning ──────────────────────────────────────────────────────────
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

    c1, c2 = st.columns([1, 5])
    with c1:
        if st.button("← Bibliotek", use_container_width=True):
            st.session_state.pop("_aktiv_bog", None)
            st.rerun()
    with c2:
        st.markdown(
            f"<div style='font-weight:700;font-size:1.05rem;color:#0f172a;"
            f"padding-top:.35rem;'>{bog['title']}</div>",
            unsafe_allow_html=True,
        )

    render_reader(bog, pages, pdf_url)
    st.caption(
        "Tastatur: ← → bladr · +/− zoom · F fuldskærm · W bredde · H højde. "
        "Appen husker automatisk hvor du kom til."
    )

else:
    # ── Biblioteks-visning ───────────────────────────────────────────────────────
    st.markdown(
        f"""
<div style="padding:2.5rem 0 1.5rem;">
  <div style="font-family:'Inter',system-ui,sans-serif;font-size:clamp(1.4rem,2.4vw,1.9rem);
              font-weight:700;color:#0f172a;letter-spacing:-0.5px;">Bibliotek</div>
  <div style="height:2px;width:30px;background:{ACCENT};border-radius:2px;margin:.7rem 0 1rem;"></div>
  <div style="font-size:13px;color:#64748b;max-width:60ch;line-height:1.6;">
    Læs bøger, manga og dokumenter. Vælg en bog for at fortsætte hvor du slap.
    Tilføj bøger ved at lægge dem i mappen <code>boeger/</code> i projektet, eller upload herunder.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    # Upload
    with st.expander("➕ Upload en bog (billeder, CBZ/ZIP eller PDF)", expanded=False):
        up = st.file_uploader(
            "Vælg fil",
            type=["pdf", "cbz", "zip", "jpg", "jpeg", "png", "webp", "gif", "avif", "bmp"],
            accept_multiple_files=False,
            label_visibility="collapsed",
        )
        if up is not None:
            try:
                bog = _process_upload(up)
                if bog:
                    st.session_state["_uploadede_boeger"][bog["id"]] = bog
                    st.success(f"„{bog['title']}” er klar i biblioteket nedenfor.")
                else:
                    st.warning("Filtypen kunne ikke læses som en bog.")
            except Exception as e:
                st.error(f"Kunne ikke behandle filen: {e}")

    repo_boeger = scan_books()
    upload_boeger = list(st.session_state["_uploadede_boeger"].values())
    alle = upload_boeger + repo_boeger

    if not alle:
        st.info(
            "Ingen bøger fundet endnu. Læg en mappe med billedsider (eller en .cbz/.pdf-fil) "
            "i `boeger/`-mappen, eller upload en fil ovenfor."
        )
    else:
        kolonner = st.columns(4, gap="medium")
        for i, bog in enumerate(alle):
            with kolonner[i % 4]:
                cover = bog.get("_pages", [None])[0] if bog["kilde"] == "upload" else load_first_page(bog)
                badge = {
                    "pdf": "PDF",
                    "arkiv": "CBZ",
                    "mappe": "Manga",
                    "upload": "Upload",
                }.get(bog["kilde"], "Bog")
                sider_txt = f"{bog['n_pages']} sider" if bog.get("n_pages") else "PDF"

                if cover:
                    cover_html = (
                        f"<img src='{cover}' style='width:100%;aspect-ratio:3/4;object-fit:cover;"
                        f"border-radius:6px 6px 0 0;display:block;background:#0f172a;'/>"
                    )
                else:
                    cover_html = (
                        "<div style='width:100%;aspect-ratio:3/4;border-radius:6px 6px 0 0;"
                        "background:linear-gradient(135deg,#1e293b,#0f172a);display:flex;"
                        "align-items:center;justify-content:center;font-size:34px;color:#475569;'>📕</div>"
                    )

                st.markdown(
                    f"""
<div style="border:1px solid #eef1f6;border-radius:8px 8px 0 0;border-bottom:none;overflow:hidden;background:#fff;">
  {cover_html}
  <div style="padding:.7rem .8rem .2rem;">
    <div style="font-size:9px;font-weight:700;color:{ACCENT};text-transform:uppercase;
                letter-spacing:.6px;margin-bottom:3px;">{badge} · {sider_txt}</div>
    <div style="font-size:12.5px;font-weight:600;color:#0f172a;line-height:1.35;
                white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="{bog['title']}">{bog['title']}</div>
  </div>
</div>
""",
                    unsafe_allow_html=True,
                )
                if st.button("Læs", key=f"open_{bog['id']}", use_container_width=True):
                    st.session_state["_aktiv_bog"] = bog["id"]
                    st.rerun()
