"""Controlla i link relativi dei .md del repo: file esistenti e ancore (#titolo).

    python tools/checklinks.py        # exit 1 se c'è un link rotto
"""
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from urllib.parse import unquote

REPO = Path(__file__).resolve().parent.parent
files = subprocess.run(["git", "ls-files", "-co", "--exclude-standard", "*.md"], cwd=REPO,
                       capture_output=True, text=True, encoding="utf-8").stdout.split()
files = [f for f in files if not f.startswith(("emulator/toern-src", "sdcard/samples"))]
PAT = re.compile(r'(?:\]\(|src="|href=")(?!https?:|mailto:|data:)([^)"\s]+)')


def slug(h):
    h = h.strip().lower()
    h = re.sub(r"<[^>]+>", "", h)
    out = []
    for ch in h:
        if ch.isalnum() or ch in "-_":
            out.append(ch)
        elif ch == " ":
            out.append("-")
        elif unicodedata.category(ch).startswith(("L", "N")):
            out.append(ch)
    return "".join(out)


def anchors(p):
    s = p.read_text(encoding="utf-8", errors="replace")
    s = re.sub(r"```.*?```", "", s, flags=re.S)
    a, seen = set(), {}
    for h in re.findall(r"^#{1,6}\s+(.+?)\s*#*$", s, flags=re.M):
        h = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", h).replace("`", "").replace("*", "")
        b = slug(h)
        n = seen.get(b, 0)
        seen[b] = n + 1
        a.add(b if n == 0 else f"{b}-{n}")
    a |= set(re.findall(r'(?:id|name)="([^"]+)"', s))
    return a


bad = 0
for f in files:
    p = REPO / f
    s = p.read_text(encoding="utf-8", errors="replace")
    s = re.sub(r"```.*?```", "", s, flags=re.S)
    s = re.sub(r"`[^`\n]*`", "", s)
    for t in PAT.findall(s):
        path, _, anc = t.partition("#")
        dest = p if not path else (p.parent / unquote(path)).resolve()
        if path and not dest.exists():
            print(f"MISSING  {f}: {t}")
            bad += 1
        elif anc and dest.suffix == ".md" and anc not in anchors(dest):
            print(f"ANCHOR   {f}: {t}")
            bad += 1
print(f"{len(files)} file, link rotti: {bad}")
sys.exit(1 if bad else 0)
