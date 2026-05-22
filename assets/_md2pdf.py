#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Render the ichosynth Italian manuals (Markdown) to polished PDFs.

- embeds the SVG infographics as PNG (assets/_preview/*.png)
- replaces ```mermaid blocks with the locally-rendered diagram PNGs
- handles headings, paragraphs, lists, tables, blockquote callouts, code,
  horizontal rules and inline **bold** / *italic* / `code` / [links]

Pure reportlab (+ resvg already used to make the PNGs). Run:
    python assets/_md2pdf.py
"""
import os
import re
import struct
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, Image, HRFlowable, KeepTogether,
                                Preformatted)
from reportlab.lib.enums import TA_CENTER, TA_LEFT

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PREVIEW = os.path.join(HERE, "_preview")

# palette
INK = colors.HexColor("#1f2328")
SUB = colors.HexColor("#57606a")
ACCENT = colors.HexColor("#1f6feb")
GREEN = colors.HexColor("#2ea44f")
RULE = colors.HexColor("#d0d7de")
CODEBG = colors.HexColor("#f0f3f6")
THEAD = colors.HexColor("#0d1117")
TROW = colors.HexColor("#f6f8fa")

CALLOUT = {  # emoji -> (border, bg, label)
    "⚠️": (colors.HexColor("#d29922"), colors.HexColor("#fff8e6"), "ATTENZIONE"),
    "⚠": (colors.HexColor("#d29922"), colors.HexColor("#fff8e6"), "ATTENZIONE"),
    "💡": (ACCENT, colors.HexColor("#eaf2ff"), "TIP"),
    "ℹ️": (SUB, colors.HexColor("#f2f4f7"), "NOTA"),
    "🆕": (GREEN, colors.HexColor("#eafaf0"), "FORK"),
    "💾": (ACCENT, colors.HexColor("#eaf2ff"), "SALVATAGGIO"),
    "📁": (SUB, colors.HexColor("#f2f4f7"), "FILE"),
}
DEFAULT_CALLOUT = (SUB, colors.HexColor("#f2f4f7"), None)

USABLE = A4[0] - 36 * mm  # margins 18mm each side

KEEP = {0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x2022, 0x2026,
        0x20AC, 0x2122}
REPL = {"→": "->", "←": "<-", "↑": "su", "↓": "giu", "⇄": "<->",
        "≥": ">=", "≤": "<=", "≈": "~", "▼": "", "▶": "", "✅": "",
        "🔧": "", "🎮": "", "🧠": "", "🎧": ""}


def deemoji(s):
    for k, v in REPL.items():
        s = s.replace(k, v)
    out = []
    for ch in s:
        o = ord(ch)
        if o <= 0xFF or o in KEEP:
            out.append(ch)
        # else: drop (emoji / symbols / geometric)
    return "".join(out).strip()


def first_emoji(s):
    for token in CALLOUT:
        if token in s:
            return token
    return None


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    w, h = struct.unpack(">II", head[16:24])
    return w, h


def img_flowable(name, max_w=USABLE, scale=1.0):
    path = os.path.join(PREVIEW, name + ".png")
    w, h = png_size(path)
    target = min(max_w, w * 0.75) * scale  # 0.75: px(110dpi)->pt approx
    ratio = h / w
    return Image(path, width=target, height=target * ratio)


# ---- inline ----------------------------------------------------------------
def inline(s):
    s = deemoji(s)
    s = (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", s)
    s = re.sub(r"`(.+?)`", r'<font face="Courier" size="9">\1</font>', s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)",
               lambda m: f'<font color="#1f6feb"><u>{m.group(1)}</u></font>', s)
    return s


def cell_para(s, style):
    return Paragraph(inline(s), style)


def main():
    styles = make_styles()
    for src, out, title in [
        ("MANUALE_USO.md", "MANUALE_USO.pdf", "NI404 - Manuale d'Uso"),
        ("MANUALE_COSTRUZIONE.md", "MANUALE_COSTRUZIONE.pdf", "NI404 - Manuale di Costruzione"),
    ]:
        story = build(os.path.join(ROOT, src), styles)
        doc = SimpleDocTemplate(
            os.path.join(ROOT, out), pagesize=A4,
            leftMargin=18 * mm, rightMargin=18 * mm,
            topMargin=16 * mm, bottomMargin=16 * mm, title=title,
            author="luigismith", subject="ichosynth")
        doc.build(story)
        print("wrote", out)


def make_styles():
    ss = getSampleStyleSheet()
    s = {}
    s["title"] = ParagraphStyle("t", parent=ss["Title"], textColor=INK,
                                fontSize=26, leading=30, alignment=TA_CENTER,
                                spaceAfter=2, fontName="Helvetica-Bold")
    s["subtitle"] = ParagraphStyle("st", parent=ss["Normal"], textColor=ACCENT,
                                   fontSize=13, leading=17, alignment=TA_CENTER,
                                   spaceAfter=6, fontName="Helvetica-Bold")
    s["tag"] = ParagraphStyle("tg", parent=ss["Normal"], textColor=SUB,
                              fontSize=10.5, leading=15, alignment=TA_CENTER,
                              spaceAfter=4)
    s["h1"] = ParagraphStyle("h1", parent=ss["Heading1"], textColor=INK,
                             fontSize=18, leading=22, spaceBefore=14, spaceAfter=4,
                             fontName="Helvetica-Bold")
    s["h2"] = ParagraphStyle("h2", parent=ss["Heading2"], textColor=INK,
                             fontSize=14.5, leading=18, spaceBefore=12, spaceAfter=3,
                             fontName="Helvetica-Bold")
    s["h3"] = ParagraphStyle("h3", parent=ss["Heading3"], textColor=colors.HexColor("#39414a"),
                             fontSize=12, leading=16, spaceBefore=8, spaceAfter=2,
                             fontName="Helvetica-Bold")
    s["body"] = ParagraphStyle("b", parent=ss["Normal"], textColor=INK,
                               fontSize=10.2, leading=15, spaceAfter=5)
    s["li"] = ParagraphStyle("li", parent=s["body"], leftIndent=12, spaceAfter=2,
                             bulletIndent=2)
    s["cell"] = ParagraphStyle("c", parent=ss["Normal"], textColor=INK,
                               fontSize=8.8, leading=12)
    s["cellh"] = ParagraphStyle("ch", parent=s["cell"], textColor=colors.white,
                                fontName="Helvetica-Bold")
    s["co"] = ParagraphStyle("co", parent=s["body"], spaceAfter=0)
    s["colab"] = ParagraphStyle("col", parent=s["body"], fontSize=8,
                                textColor=SUB, fontName="Helvetica-Bold", spaceAfter=1)
    s["code"] = ParagraphStyle("code", parent=ss["Code"], fontSize=8.3,
                               leading=11, textColor=colors.HexColor("#0a3069"))
    return s


# ---- mermaid mapping -------------------------------------------------------
def mermaid_png(srclower):
    if "slave" in srclower or "master" in srclower:
        return "midi-clock"
    if "statediagram" in srclower:
        return "modes-map"
    if "matrice" in srclower or "pronto" in srclower:
        return "assembly-flow"
    if "resamplingreader" in srclower or "usb type" in srclower:
        return "flash-flow"
    return None


def colwidths(rows):
    n = max(len(r) for r in rows)
    maxlen = [1] * n
    for r in rows:
        for i in range(n):
            cell = r[i] if i < len(r) else ""
            maxlen[i] = max(maxlen[i], len(re.sub(r"[*`\[\]]", "", cell)))
    minw = 18.0  # pt floor so padding never exceeds the column
    rem = max(0.0, USABLE - minw * n)
    tot = sum(maxlen)
    return [minw + rem * (maxlen[i] / tot) for i in range(n)]


def build(path, st):
    lines = open(path, encoding="utf-8").read().split("\n")
    story = []
    i, n = 0, len(lines)

    def flush_para(buf):
        if buf:
            txt = " ".join(buf).strip()
            if txt:
                story.append(Paragraph(inline(txt), st["body"]))

    while i < n:
        ln = lines[i]
        s = ln.strip()

        # centered div block (hero / footer)
        if s.startswith("<div align"):
            i += 1
            blk = []
            while i < n and "</div>" not in lines[i].strip():
                blk.append(lines[i])
                i += 1
            i += 1
            for b in blk:
                bs = b.strip()
                if not bs or bs.startswith("[!["):
                    continue
                if bs.startswith("# "):
                    story.append(Paragraph(inline(bs[2:]), st["title"]))
                elif bs.startswith("### "):
                    story.append(Paragraph(inline(bs[4:]), st["subtitle"]))
                elif bs.startswith("#"):
                    story.append(Paragraph(inline(bs.lstrip("# ")), st["subtitle"]))
                else:
                    story.append(Paragraph(inline(bs), st["tag"]))
            story.append(Spacer(1, 6))
            continue

        # centered image  <p align="center"> <img ...> </p>
        if s.startswith("<p align") or s.startswith("<img"):
            block = s
            while "/>" not in block and "</p>" not in block and i + 1 < n:
                i += 1
                block += " " + lines[i].strip()
            m = re.search(r'src="assets/([\w-]+)\.svg"', block)
            if m:
                story.append(Spacer(1, 4))
                story.append(img_flowable(m.group(1)))
                story.append(Spacer(1, 6))
            i += 1
            continue

        # horizontal rule
        if s == "---":
            story.append(Spacer(1, 2))
            story.append(HRFlowable(width="100%", thickness=0.7, color=RULE,
                                    spaceBefore=2, spaceAfter=6))
            i += 1
            continue

        # headings
        if s.startswith("### "):
            story.append(Paragraph(inline(s[4:]), st["h3"])); i += 1; continue
        if s.startswith("## "):
            story.append(Paragraph(inline(s[3:]), st["h2"])); i += 1; continue
        if s.startswith("# "):
            story.append(Paragraph(inline(s[2:]), st["h1"])); i += 1; continue

        # code fence
        if s.startswith("```"):
            lang = s[3:].strip().lower()
            i += 1
            code = []
            while i < n and not lines[i].strip().startswith("```"):
                code.append(lines[i]); i += 1
            i += 1
            if lang == "mermaid":
                name = mermaid_png("\n".join(code).lower())
                if name:
                    story.append(Spacer(1, 4))
                    story.append(img_flowable(name, scale=0.92))
                    story.append(Spacer(1, 6))
            else:
                # Preformatted renders text verbatim (no XML markup parsing),
                # so raw <, >, & are fine and must NOT be entity-escaped.
                txt = deemoji("\n".join(code))
                tbl = Table([[Preformatted(txt, st["code"])]], colWidths=[USABLE])
                tbl.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), CODEBG),
                    ("BOX", (0, 0), (-1, -1), 0.5, RULE),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
                story.append(tbl)
                story.append(Spacer(1, 4))
            continue

        # blockquote callout
        if s.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip()[1:].strip())
                i += 1
            text = " ".join(x for x in buf if x).strip()
            token = first_emoji(text)
            border, bg, label = CALLOUT.get(token, DEFAULT_CALLOUT)
            body = deemoji(text)
            inner = []
            if label:
                inner.append(Paragraph(label, st["colab"]))
            inner.append(Paragraph(inline(body), st["co"]))
            tbl = Table([[inner]], colWidths=[USABLE])
            tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), bg),
                ("LINEBEFORE", (0, 0), (0, -1), 3, border),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
            story.append(tbl)
            story.append(Spacer(1, 5))
            continue

        # table
        if s.startswith("|"):
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                rows.append(cells)
                i += 1
            if len(rows) >= 2 and set(rows[1][0].replace(":", "").strip()) <= {"-", ""}:
                header = rows[0]
                data = rows[2:]
            else:
                header = None
                data = rows
            allrows = ([header] if header else []) + data
            cw = colwidths(allrows)
            trows = []
            if header:
                trows.append([cell_para(c, st["cellh"]) for c in header])
            for r in data:
                r = r + [""] * (len(cw) - len(r))
                trows.append([cell_para(c, st["cell"]) for c in r])
            tbl = Table(trows, colWidths=cw, repeatRows=1 if header else 0)
            style = [
                ("GRID", (0, 0), (-1, -1), 0.4, RULE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1),
                 [colors.white, TROW]),
            ]
            if header:
                style.append(("BACKGROUND", (0, 0), (-1, 0), THEAD))
            tbl.setStyle(TableStyle(style))
            story.append(tbl)
            story.append(Spacer(1, 7))
            continue

        # lists
        if re.match(r"^(\d+\.|-)\s", s):
            items = []
            while i < n and re.match(r"^(\s*)(\d+\.|-)\s", lines[i]):
                raw = lines[i]
                indent = len(raw) - len(raw.lstrip())
                m = re.match(r"^\s*(\d+\.|-)\s+(.*)$", raw)
                bullet = "•" if m.group(1) == "-" else m.group(1)
                style = ParagraphStyle("li_d", parent=st["li"],
                                       leftIndent=12 + (18 if indent >= 2 else 0))
                items.append(Paragraph(f"{bullet}&nbsp;&nbsp;{inline(m.group(2))}", style))
                i += 1
            story.extend(items)
            story.append(Spacer(1, 4))
            continue

        # blank
        if not s:
            i += 1
            continue

        # paragraph (gather until blank / structural)
        buf = []
        while i < n and lines[i].strip() and not re.match(
                r"^(#|>|\||```|---|<div|<p align|<img|-\s|\d+\.\s)", lines[i].strip()):
            buf.append(lines[i].strip())
            i += 1
        flush_para(buf)

    return story


if __name__ == "__main__":
    main()
