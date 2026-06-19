# Manual PDF generation

Regenerates the manual PDFs (`BUILD_MANUAL.pdf`, `USAGE_MANUAL.pdf`, `DEV_ENVIRONMENT.pdf`
and their Italian counterparts) from the Markdown sources in the repo root, so the PDFs
stay in sync with the `.md` files.

Pipeline: `markdown-it` (Markdown → HTML) → headless Chrome (via `puppeteer-core`,
driving the system Chrome/Edge) → PDF. Mermaid code-fences render client-side; the
`assets/*.svg` diagrams are inlined directly into the HTML so they always embed.

## Usage

```sh
cd scripts/pdf
npm install            # once (markdown-it + puppeteer-core)
node build-pdfs.mjs    # writes the six *.pdf in the repo root
```

Needs Node.js and an installed Chrome or Edge (auto-detected). `node_modules/` is
git-ignored; the committed `*.pdf` are the shipped output.
