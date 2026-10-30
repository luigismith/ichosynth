// Regenerate the ichosynth manual PDFs from their Markdown sources.
//
// Pipeline: markdown-it (MD -> HTML, GitHub-ish CSS) -> headless Chrome (puppeteer-core
// driving the system Chrome) -> PDF. Mermaid code-fences are rendered client-side via
// mermaid from a CDN; relative image paths (assets/*.svg) resolve against the repo root
// through a <base href>. Run with: node scripts/pdf/build-pdfs.mjs
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import MarkdownIt from "markdown-it";
import puppeteer from "puppeteer-core";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "..", "..");

const PAIRS = [
  "BUILD_MANUAL", "MANUALE_COSTRUZIONE",
  "USAGE_MANUAL", "MANUALE_USO",
  "DEV_ENVIRONMENT", "MANUALE_AMBIENTE",
];

const CHROME_CANDIDATES = [
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  "/usr/bin/google-chrome", "/usr/bin/chromium-browser",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
];
const chrome = CHROME_CANDIDATES.find((p) => fs.existsSync(p));
if (!chrome) { console.error("No Chrome/Edge found."); process.exit(1); }

const md = new MarkdownIt({ html: true, linkify: true });
// Turn ```mermaid fences into <pre class="mermaid"> so mermaid.js can render them.
const defFence = md.renderer.rules.fence.bind(md.renderer.rules);
md.renderer.rules.fence = (tokens, idx, opts, env, self) => {
  if (tokens[idx].info.trim() === "mermaid")
    return `<pre class="mermaid">${md.utils.escapeHtml(tokens[idx].content)}</pre>`;
  return defFence(tokens, idx, opts, env, self);
};

const CSS = `
  body{font-family:'Segoe UI',Helvetica,Arial,sans-serif;color:#1f2328;line-height:1.55;
       max-width:820px;margin:0 auto;padding:8px 24px;font-size:13.5px;}
  body::before{content:"";display:block;height:6px;margin:0 -24px 14px;
       background:linear-gradient(90deg,#E83A3A 0 12.5%,#3A6BE8 0 25%,#E8D23A 0 37.5%,#36C24A 0 50%,
       #E83AA6 0 62.5%,#A6E03A 0 75%,#FF7A1A 0 87.5%,#2AD4B8 0);}
  h1{font-size:28px;font-weight:800;margin-top:.6em;}
  h2{font-size:20px;font-weight:800;border-left:6px solid #FF8A1A;padding:.1em 0 .1em .5em;margin-top:1.6em;
     break-after:avoid;}
  h3{font-size:16px;font-weight:800;break-after:avoid;} h4{font-size:14px;}
  .svgwrap{display:inline-block;text-align:center;} p[align=center] .svgwrap{display:block;}
  td img, td .svgwrap svg{max-width:100%;} table{break-inside:avoid;}
  blockquote{background:#f6f8fa;border-left:4px solid #FF8A1A !important;border-radius:4px;}
  code{background:#eff1f3;padding:.15em .4em;border-radius:5px;font-size:85%;
       font-family:'JetBrains Mono','Consolas',monospace;}
  pre{background:#f6f8fa;padding:12px;border-radius:8px;overflow:auto;}
  pre code{background:none;padding:0;}
  pre.mermaid{background:none;text-align:center;}
  table{border-collapse:collapse;width:100%;margin:1em 0;font-size:12.5px;}
  th,td{border:1px solid #d0d7de;padding:6px 10px;} th{background:#f6f8fa;}
  tr:nth-child(2n){background:#f6f8fa;}
  img{max-width:100%;} a{color:#0969da;text-decoration:none;}
  blockquote{border-left:3px solid #d0d7de;color:#57606a;margin:1em 0;padding:.2em 1em;}
  hr{border:none;border-top:1px solid #d0d7de;margin:1.5em 0;}
  @page{margin:14mm 0;}
`;

// Inline local SVGs: Chrome blocks file:// subresources from a setContent page, so
// embed the <svg> markup directly (robust, no file-access policy, scales to page width).
function inlineSvgs(body) {
  return body.replace(/<img([^>]*)\ssrc="([^"]+\.(svg|jpe?g|png))"([^>]*)>/g, (m, pre, rel, ext, post) => {
    if (/^[a-z]+:/i.test(rel)) return m;                      // http(s)/data: lasciali stare
    const fp = path.join(REPO, rel);
    if (!fs.existsSync(fp)) return m;
    const width = (pre + post).match(/\swidth="(\d+)"/);
    const maxw = width ? `max-width:min(100%,${width[1]}px)` : "max-width:100%";
    if (ext === "svg") {
      const svg = fs.readFileSync(fp, "utf8").replace(/<svg /, `<svg style="${maxw};height:auto" `);
      return `<span class="svgwrap">${svg}</span>`;
    }
    // JPG/PNG: Chrome blocca i file:// da una pagina setContent -> data URI
    const mime = ext === "png" ? "image/png" : "image/jpeg";
    const b64 = fs.readFileSync(fp).toString("base64");
    return `<img${pre} src="data:${mime};base64,${b64}"${post} style="${maxw};height:auto">`;
  });
}

const html = (body, hasMermaid) => `<!doctype html><html><head><meta charset="utf-8">
<base href="${pathToFileURL(REPO).href}/"><style>${CSS}</style></head>
<body>${inlineSvgs(body)}
${hasMermaid ? `<script type="module">
  import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
  mermaid.initialize({startOnLoad:false, theme:'default'});
  try { await mermaid.run(); } catch(e) {}
  window.__done = true;
</script>` : `<script>window.__done=true;</script>`}
</body></html>`;

const browser = await puppeteer.launch({ executablePath: chrome, headless: "new",
  args: ["--no-sandbox", "--allow-file-access-from-files"] });

for (const name of PAIRS) {
  const src = path.join(REPO, name + ".md");
  if (!fs.existsSync(src)) { console.warn("skip (missing):", name); continue; }
  const text = fs.readFileSync(src, "utf8");
  const hasMermaid = text.includes("```mermaid");
  const page = await browser.newPage();
  await page.setContent(html(md.render(text), hasMermaid), { waitUntil: "networkidle0", timeout: 60000 });
  await page.waitForFunction("window.__done === true", { timeout: 30000 }).catch(() => {});
  await new Promise((r) => setTimeout(r, hasMermaid ? 1500 : 200));
  const out = path.join(REPO, name + ".pdf");
  await page.pdf({ path: out, format: "A4", printBackground: true,
    margin: { top: "14mm", bottom: "14mm", left: "14mm", right: "14mm" } });
  await page.close();
  console.log("wrote", path.relative(REPO, out));
}
await browser.close();
console.log("done.");
