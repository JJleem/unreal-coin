"""
Sign faces for the reimagined Hongdae, drawn at 250 px per metre with real fonts (Malgun Gothic for Korean, Arial for
Latin) instead of the blurred photo crops: light box faces, blade signs, posters and logo discs. The wording follows
what the scan's facade photos show (SOLB, 전자담배, ZERO, VAPE, BIBIANG, Tax-Free Shop, BLUE ELEPHANT, The Coffee Bean)
or, where the photos are unreadable, plausible Hongdae shop signs.

Each face gets light wear: a slightly uneven fill, dirt collecting at the bottom edge, faded highlights.
"""

import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONTS = "/mnt/c/Windows/Fonts"
KO = os.path.join(FONTS, "malgunbd.ttf")
KO_LIGHT = os.path.join(FONTS, "malgun.ttf")
LATIN = os.path.join(FONTS, "arialbd.ttf")
ZH = os.path.join(FONTS, "msyhbd.ttc")
SERIF = os.path.join(FONTS, "times.ttf") if os.path.exists(os.path.join(FONTS, "times.ttf")) else os.path.join(FONTS, "batang.ttc")
PPM = 250


def _wear(im, seed, dirt=0.25):
    rng = np.random.default_rng(seed)
    a = np.asarray(im, float) / 255.0
    h, w = a.shape[:2]
    noise = rng.normal(0, 1, (max(2, h // 40), max(2, w // 40)))
    noise = np.asarray(Image.fromarray(((noise - noise.min()) / (np.ptp(noise) + 1e-9) * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC), float) / 255.0
    shade = 0.93 + 0.07 * noise
    grime = 1.0 - dirt * np.clip((np.linspace(0, 1, h)[:, None] - 0.75) / 0.25, 0, 1) ** 2
    a = a * shade[..., None] * grime[..., None]
    a = 0.04 + a * 0.92   # nothing printed is pure black or white
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))


def _fit(draw, text, font_path, max_w, max_h):
    size = int(max_h)
    while size > 6:
        font = ImageFont.truetype(font_path, size)
        l, t, r, b = draw.textbbox((0, 0), text, font=font)
        if r - l <= max_w and b - t <= max_h:
            return font, (l, t, r, b)
        size = int(size * 0.93)
    font = ImageFont.truetype(font_path, 6)
    return font, draw.textbbox((0, 0), text, font=font)


def text_face(path, w_m, h_m, bg, items, border=None, seed=0, vertical=False):
    """items: (text, font, colour, centre x 0..1, centre y 0..1, max width 0..1, max height 0..1)."""
    w, h = int(w_m * PPM), int(h_m * PPM)
    im = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(im)
    if border:
        bw = max(4, int(0.03 * PPM))
        d.rectangle((bw // 2, bw // 2, w - bw // 2, h - bw // 2), outline=border, width=bw)
    for text, font_path, colour, cx, cy, mw, mh in items:
        if vertical:
            # one character per line, stacked
            chars = list(text)
            cell = mh * h / len(chars)
            for k, ch in enumerate(chars):
                font, (l, t, r, b) = _fit(d, ch, font_path, mw * w, cell * 0.86)
                yc = cy * h - mh * h / 2 + cell * (k + 0.5)
                d.text((cx * w - (l + r) / 2, yc - (t + b) / 2), ch, font=font, fill=colour)
        else:
            font, (l, t, r, b) = _fit(d, text, font_path, mw * w, mh * h)
            d.text((cx * w - (l + r) / 2, cy * h - (t + b) / 2), text, font=font, fill=colour)
    im = _wear(im, seed)
    im.save(path)
    return path


def logo_disc(path, size_m, bg, ring, text, colour, seed=0):
    s = int(size_m * PPM)
    im = Image.new("RGB", (s, s), bg)
    d = ImageDraw.Draw(im)
    d.ellipse((4, 4, s - 4, s - 4), fill=ring)
    inner = int(s * 0.12)
    d.ellipse((inner, inner, s - inner, s - inner), fill=bg)
    font, (l, t, r, b) = _fit(d, text, SERIF, s * 0.62, s * 0.5)
    d.text((s / 2 - (l + r) / 2, s / 2 - (t + b) / 2), text, font=font, fill=colour)
    _wear(im, seed, 0.1).save(path)
    return path


def poster(path, w_m, h_m, top, bottom, title, sub, seed=0):
    """Shop window poster: a colour gradient with a title and a line of small print."""
    w, h = int(w_m * PPM), int(h_m * PPM)
    t = np.linspace(0, 1, h)[:, None, None]
    a = np.array(top)[None, None] * (1 - t) + np.array(bottom)[None, None] * t
    im = Image.fromarray(np.repeat(a, w, axis=1).astype(np.uint8))
    d = ImageDraw.Draw(im)
    # graphic layout: a bold diagonal band, a thin frame, a big season number
    d = ImageDraw.Draw(im)
    d.polygon([(0, h * 0.42), (w, h * 0.22), (w, h * 0.36), (0, h * 0.56)], fill=tuple(min(255, int(c * 1.35) + 30) for c in bottom))
    d.rectangle((w * 0.06, h * 0.04, w * 0.94, h * 0.96), outline=(255, 255, 255), width=max(2, int(w * 0.012)))
    font, (l, tt, r, b) = _fit(d, "26", LATIN, w * 0.7, h * 0.24)
    d.text((w / 2 - (l + r) / 2, h * 0.2 - (tt + b) / 2), "26", font=font, fill=(255, 255, 255))
    font, (l, tt, r, b) = _fit(d, title, LATIN, w * 0.8, h * 0.1)
    d.text((w / 2 - (l + r) / 2, h * 0.76 - (tt + b) / 2), title, font=font, fill=(255, 255, 255))
    font, (l, tt, r, b) = _fit(d, sub, KO_LIGHT, w * 0.7, h * 0.045)
    d.text((w / 2 - (l + r) / 2, h * 0.86 - (tt + b) / 2), sub, font=font, fill=(235, 235, 235))
    _wear(im, seed, 0.1).save(path)
    return path


def make_all(out):
    """All sign faces of the reimagined buildings; returns name -> file."""
    os.makedirs(out, exist_ok=True)
    f = {}
    P = lambda name: os.path.join(out, f"sign_{name}.png")
    # ---- SOLB building
    f["solb_vape"] = text_face(P("solb_vape"), 2.0, 0.62, (240, 140, 30), [("전자담배", KO, (120, 20, 15), 0.5, 0.52, 0.9, 0.72)], border=(150, 30, 20), seed=1)
    f["solb_zero"] = text_face(P("solb_zero"), 1.1, 0.42, (190, 25, 30), [("ZERO", LATIN, (255, 230, 120), 0.5, 0.52, 0.86, 0.7)], border=(240, 200, 90), seed=2)
    f["solb_vape_cn"] = text_face(P("solb_vape_cn"), 0.9, 0.55, (245, 160, 40), [("VAPE", LATIN, (150, 25, 20), 0.5, 0.3, 0.8, 0.36),
                                                                                    ("电子烟", ZH, (150, 25, 20), 0.5, 0.72, 0.8, 0.38)], border=(150, 30, 20), seed=3)
    f["solb_blade_a"] = _blade(P("solb_blade_a"), 0.62, 2.2, (200, 25, 35), "전자담배", "ZERO", (255, 255, 255), (255, 225, 110), 4)
    # ---- BIBIANG corner building
    f["bibiang_tarot"] = text_face(P("bibiang_tarot"), 2.6, 0.55, (250, 248, 240), [("사주 · 타로", KO, (190, 30, 110), 0.5, 0.52, 0.9, 0.72)], border=(190, 30, 110), seed=5)
    f["bibiang_blade"] = _blade(P("bibiang_blade"), 0.55, 2.4, (40, 30, 90), "타로카페", "2F", (255, 220, 120), (255, 255, 255), 6)
    f["bibiang_hair"] = text_face(P("bibiang_hair"), 2.4, 0.5, (30, 30, 32), [("헤어 스튜디오  4F", KO, (240, 240, 240), 0.5, 0.52, 0.9, 0.62)], seed=7)
    f["bibiang_poster"] = poster(P("bibiang_poster"), 0.6, 1.5, (210, 190, 200), (90, 70, 90), "BIBIANG", "2026 F/W 신상품 입고", seed=8)
    # ---- Blue Elephant / Coffee Bean
    f["cbtl_logo"] = logo_disc(P("cbtl_logo"), 0.8, (238, 232, 220), (85, 40, 110), "CB", (85, 40, 110), seed=9)
    f["be_poster"] = poster(P("be_poster"), 1.0, 2.0, (40, 60, 120), (10, 15, 40), "BLUE ELEPHANT", "NEW SUNGLASSES COLLECTION", seed=10)
    f["be_menu"] = text_face(P("be_menu"), 0.5, 0.7, (28, 28, 28), [("TODAY", LATIN, (240, 240, 240), 0.5, 0.15, 0.8, 0.12),
                                                                    ("아메리카노 4,800", KO_LIGHT, (230, 230, 230), 0.5, 0.4, 0.86, 0.1),
                                                                    ("카페라떼 5,300", KO_LIGHT, (230, 230, 230), 0.5, 0.55, 0.86, 0.1),
                                                                    ("콜드브루 5,500", KO_LIGHT, (230, 230, 230), 0.5, 0.7, 0.86, 0.1)], seed=11)
    # small stickers / notices on the walls
    f["notice_rent"] = text_face(P("notice_rent"), 0.42, 0.3, (250, 250, 245), [("임대문의", KO, (200, 20, 20), 0.5, 0.35, 0.86, 0.36),
                                                                                ("010-0000-0000", LATIN, (30, 30, 30), 0.5, 0.75, 0.86, 0.22)], seed=12)
    f["notice_cctv"] = text_face(P("notice_cctv"), 0.3, 0.2, (250, 210, 0), [("CCTV 녹화중", KO, (20, 20, 20), 0.5, 0.5, 0.9, 0.5)], seed=13)
    return f


def _blade(path, w_m, h_m, bg, text, sub, colour, sub_colour, seed):
    """Vertical blade sign face: Korean characters stacked, a small Latin/number line at the bottom."""
    w, h = int(w_m * PPM), int(h_m * PPM)
    im = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(im)
    bw = max(4, int(0.025 * PPM))
    d.rectangle((bw, bw, w - bw, h - bw), outline=(245, 245, 245), width=bw)
    chars = list(text)
    area = h * 0.8
    cell = area / len(chars)
    for k, ch in enumerate(chars):
        font, (l, t, r, b) = _fit(d, ch, KO, w * 0.72, cell * 0.84)
        yc = h * 0.06 + cell * (k + 0.5)
        d.text((w / 2 - (l + r) / 2, yc - (t + b) / 2), ch, font=font, fill=colour)
    font, (l, t, r, b) = _fit(d, sub, LATIN, w * 0.8, h * 0.07)
    d.text((w / 2 - (l + r) / 2, h * 0.92 - (t + b) / 2), sub, font=font, fill=sub_colour)
    _wear(im, seed).save(path)
    return path


if __name__ == "__main__":
    import sys
    print(make_all(sys.argv[1]))
