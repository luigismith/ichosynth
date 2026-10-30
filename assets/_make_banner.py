"""Banner del README e anteprima social (1280x640) dal render principale del case.

    python assets/_make_banner.py      # -> assets/banner.jpg, assets/social-preview.jpg

Rilanciarlo dopo aver rifatto i render (case/render/render.ps1 + make_guide.py).
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
HERO = ROOT / "case" / "img" / "hero.jpg"
OUT = ROOT / "assets"
FONTS = Path(r"C:\Windows\Fonts")
INK, SUB = (31, 35, 40), (87, 96, 106)
# colori delle 8 voci campione di TŒRN (le stesse dei diagrammi)
VOICES = ["#E83A3A", "#3A6BE8", "#E8D23A", "#36C24A", "#E83AA6", "#A6E03A", "#FF7A1A", "#2AD4B8"]


def font(name, size):
    for n in name:
        p = FONTS / n
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default(size)


def stripe(d, x, y, w, h):
    seg = w / len(VOICES)
    for i, c in enumerate(VOICES):
        d.rounded_rectangle([x + i * seg + 2, y, x + (i + 1) * seg - 2, y + h], radius=h // 2, fill=c)


def backdrop(hero, w, h, y_top, y_bot):
    """Sfondo del render (gradiente verticale preso dal bordo sinistro) esteso a tutto il banner."""
    ys = [min(hero.height - 1, max(0, int(y_top + (y_bot - y_top) * k / (h - 1)))) for k in range(h)]
    col = [hero.getpixel((4, y)) for y in ys]
    bg = Image.new("RGB", (1, h))
    bg.putdata(col)
    return bg.resize((w, h))


def make(w, h, title_px, tag_px, path, tagline):
    hero = Image.open(HERO).convert("RGB")
    box = (160, 250, 2120, 1360)                  # il case con un po' d'aria intorno
    scale = min(h * 0.96 / (box[3] - box[1]), w * 0.6 / (box[2] - box[0]))   # testo a sinistra, libero
    dev = hero.crop(box)
    dev = dev.resize((int(dev.width * scale), int(dev.height * scale)), Image.LANCZOS)
    canvas = backdrop(hero, w, h, box[1] - (h / scale - (box[3] - box[1])) / 2,
                      box[3] + (h / scale - (box[3] - box[1])) / 2)
    # bordi sfumati: il ritaglio si fonde nello sfondo, nessuna cucitura
    m = Image.new("L", dev.size, 0)
    f = int(dev.height * 0.05)
    ImageDraw.Draw(m).rectangle([f, f, dev.width - f, dev.height - f], fill=255)
    m = m.filter(ImageFilter.GaussianBlur(f * 0.6))
    canvas.paste(dev, (w - dev.width + int(w * 0.02), (h - dev.height) // 2), m)
    d = ImageDraw.Draw(canvas)
    x0 = int(w * 0.05)
    y0 = int(h * 0.5 - (title_px * 1.25 + h * 0.075 + tag_px * 2.7) / 2)   # blocco centrato in verticale
    ft = font(["segoeuib.ttf", "arialbd.ttf"], title_px)
    fs = font(["segoeui.ttf", "arial.ttf"], tag_px)
    d.text((x0, y0), "ichosynth", font=ft, fill=INK)
    tb = d.textbbox((x0, y0), "ichosynth", font=ft)
    stripe(d, x0 + 4, tb[3] + int(h * 0.03), int((tb[2] - x0) * 0.98), max(6, h // 80))
    ty = tb[3] + int(h * 0.075)
    for line in tagline:
        d.text((x0 + 2, ty), line, font=fs, fill=SUB)
        ty += int(tag_px * 1.35)
    canvas.save(path, quality=90, optimize=True, progressive=True)
    print("scritto", path.relative_to(ROOT), canvas.size)


TAG = ["TŒRN, hand-soldered.", "Teensy 4.1 groovebox · 3D-printed case"]
make(1280, 640, 96, 28, OUT / "social-preview.jpg", TAG)
make(1800, 760, 128, 36, OUT / "banner.jpg", TAG)
