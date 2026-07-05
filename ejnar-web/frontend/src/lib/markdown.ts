// TS-port af backend/app/core/text.py::md_til_html — samme markdown-undermængde
// (## overskrifter, **fed**, *kursiv*, lister, --- linjer). HTML-escaper al
// tekst FØR der indsættes tags, så kun vores egne whitelisted tags kan opstå
// — outputtet er trygt at rendere med dangerouslySetInnerHTML.
function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function inline(raw: string): string {
  let t = escapeHtml(raw);
  t = t.replace(/`([^`]+)`/g, "<code>$1</code>");
  t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  t = t.replace(/__([^_]+)__/g, "<strong>$1</strong>");
  t = t.replace(/(?<![*\w])\*([^*\n]+)\*(?!\*|\w)/g, "<em>$1</em>");
  return t;
}

export function mdToHtml(md: string): string {
  if (!md) return "";
  const lines = md.replace(/\r\n/g, "\n").split("\n");
  const out: string[] = [];
  let para: string[] = [];
  let listMode: "ul" | "ol" | null = null;

  const flushPara = () => {
    if (para.length) {
      out.push(`<p>${para.join(" ").trim()}</p>`);
      para = [];
    }
  };
  const closeList = () => {
    if (listMode) {
      out.push(`</${listMode}>`);
      listMode = null;
    }
  };

  for (const raw of lines) {
    const s = raw.trim();
    if (!s) {
      flushPara();
      closeList();
      continue;
    }
    if (/^(-{3,}|\*{3,}|_{3,})$/.test(s)) {
      flushPara();
      closeList();
      out.push("<hr>");
      continue;
    }
    const h = s.match(/^(#{1,4})\s+(.*)$/);
    if (h) {
      flushPara();
      closeList();
      const tag = h[1].length <= 2 ? "h2" : h[1].length === 3 ? "h3" : "h4";
      out.push(`<${tag}>${inline(h[2].trim())}</${tag}>`);
      continue;
    }
    const ul = s.match(/^[-*]\s+(.*)$/);
    if (ul) {
      flushPara();
      if (listMode !== "ul") {
        closeList();
        out.push("<ul>");
        listMode = "ul";
      }
      out.push(`<li>${inline(ul[1].trim())}</li>`);
      continue;
    }
    const ol = s.match(/^\d+[.)]\s+(.*)$/);
    if (ol) {
      flushPara();
      if (listMode !== "ol") {
        closeList();
        out.push("<ol>");
        listMode = "ol";
      }
      out.push(`<li>${inline(ol[1].trim())}</li>`);
      continue;
    }
    if (listMode) closeList();
    para.push(inline(s));
  }
  flushPara();
  closeList();
  return out.join("");
}

/** Erstat [Kilde N] / [Kilde N, M] med klikbare spans (data-kilde="N"). */
export function erstatKildeRefs(html: string, kilder: { sagsnummer: string; dato: string | null }[]): string {
  return html.replace(/\[Kilde\s+([\d,\s]+)\]/g, (_match, nums: string) => {
    const spans = nums
      .split(",")
      .map((n) => parseInt(n.trim(), 10))
      .filter((n) => n >= 1 && n <= kilder.length)
      .map((n) => {
        const k = kilder[n - 1];
        const år = k.dato ? k.dato.slice(0, 4) : "";
        const label = `${k.sagsnummer || "Kilde"} ${år}`.trim();
        return `<span class="cite-ref" data-kilde="${n}" style="color:var(--accent);font-weight:600;cursor:pointer;white-space:nowrap;">[${label}]</span>`;
      });
    return spans.length ? spans.join(" ") : _match;
  });
}
