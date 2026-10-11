"""Renderiza o vídeo estilo Pokérap com uma carta por Pokémon.

Uso: python3 -I render.py <timeline.json> <saida.mp4> <audio_ref.mp4>
"""
import json, math, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops

W, H, FPS = 720, 1280, 30
HERE = sys.argv[0].rsplit("/", 1)[0]
FONT = f"{HERE}/fonts/LuckiestGuy.ttf"
YEL, BLUE = (255, 203, 5), (42, 117, 187)
DARKBLUE = (24, 52, 110)

tl = json.load(open(sys.argv[1]))
OUT, AUDIO = sys.argv[2], sys.argv[3]
T0, T1 = tl["start"], tl["end"]


def ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))


# ---------- fundo: raios de luz girando ----------
def make_burst(outer, glow, size=1500):
    y, x = np.mgrid[0:size, 0:size].astype(np.float32)
    cx = cy = size / 2
    dx, dy = x - cx, y - cy
    r = np.sqrt(dx * dx + dy * dy) / (size / 2)
    ang = np.arctan2(dy, dx)
    rays = (np.sin(ang * 36) > 0.55).astype(np.float32) * np.clip(r * 1.4 - 0.25, 0, 1) * 0.10
    core = np.clip(1 - r * 1.25, 0, 1) ** 1.6
    o, g = np.array(outer, np.float32), np.array(glow, np.float32)
    img = o[None, None] * (1 - core[..., None]) + g[None, None] * core[..., None]
    img = img + rays[..., None] * 255
    hot = np.clip(1 - r * 3.2, 0, 1) ** 2
    img = img * (1 - hot[..., None]) + 255 * hot[..., None]
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


_bursts = {}


def background(t, colors):
    key = tuple(map(tuple, colors))
    if key not in _bursts:
        _bursts[key] = make_burst(*colors)
    b = _bursts[key].rotate(t * 6, resample=Image.BILINEAR)
    s = b.size[0]
    return b.crop(((s - W) // 2, (s - H) // 2, (s + W) // 2, (s + H) // 2))


# ---------- cartas ----------
CW = 520
CH = int(CW * 825 / 600)


def rounded(img, rad):
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, img.size[0] - 1, img.size[1] - 1), rad, fill=255)
    img = img.convert("RGBA")
    img.putalpha(ImageChops.multiply(img.getchannel("A"), m))
    return img


_cards = {}


def card(path, w=CW):
    k = (path, w)
    if k not in _cards:
        im = Image.open(path).convert("RGB").resize((w, int(w * 825 / 600)), Image.LANCZOS)
        _cards[k] = rounded(im, int(w * 0.045))
    return _cards[k]


def make_back(w=CW):
    h = int(w * 825 / 600)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rad = int(w * 0.045)
    d.rounded_rectangle((0, 0, w - 1, h - 1), rad, fill=(250, 214, 60))
    m = int(w * 0.05)
    d.rounded_rectangle((m, m, w - 1 - m, h - 1 - m), rad, fill=DARKBLUE)
    # brilho radial no verso
    glow = make_burst((24, 52, 110), (70, 140, 230), size=max(w, h) * 2).resize((w - 2 * m, h - 2 * m))
    mask = Image.new("L", glow.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, glow.size[0] - 1, glow.size[1] - 1), rad, fill=255)
    im.paste(glow, (m, m), mask)
    # pokébola
    cx, cy, R = w // 2, h // 2, int(w * 0.24)
    d.ellipse((cx - R - 8, cy - R - 8, cx + R + 8, cy + R + 8), fill=(20, 20, 28))
    d.pieslice((cx - R, cy - R, cx + R, cy + R), 180, 360, fill=(222, 40, 40))
    d.pieslice((cx - R, cy - R, cx + R, cy + R), 0, 180, fill=(245, 245, 245))
    band = int(R * 0.16)
    d.rectangle((cx - R, cy - band // 2, cx + R, cy + band // 2), fill=(20, 20, 28))
    r2 = int(R * 0.34)
    d.ellipse((cx - r2, cy - r2, cx + r2, cy + r2), fill=(20, 20, 28))
    r3 = int(R * 0.22)
    d.ellipse((cx - r3, cy - r3, cx + r3, cy + r3), fill=(245, 245, 245))
    return im


BACK = make_back()


def shadow_of(img, blur=18, alpha=150):
    a = img.getchannel("A").point(lambda v: v * alpha // 255)
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sh.putalpha(a)
    pad = blur * 3
    big = Image.new("RGBA", (img.size[0] + 2 * pad, img.size[1] + 2 * pad), (0, 0, 0, 0))
    big.paste(sh, (pad, pad))
    return big.filter(ImageFilter.GaussianBlur(blur)), pad


def place(frame, img, cx, cy, sx=1.0, sy=1.0, shadow=True):
    w, h = max(1, int(img.size[0] * sx)), max(1, int(img.size[1] * sy))
    im = img.resize((w, h), Image.BILINEAR) if (w, h) != img.size else img
    if shadow:
        sh, pad = shadow_of(im)
        frame.alpha_composite(sh, (int(cx - w / 2 - pad + 10), int(cy - h / 2 - pad + 22)))
    frame.alpha_composite(im, (int(cx - w / 2), int(cy - h / 2)))


# ---------- texto ----------
_fonts = {}


def font(sz):
    if sz not in _fonts:
        _fonts[sz] = ImageFont.truetype(FONT, sz)
    return _fonts[sz]


def title(frame, text, cy, maxw=660, size=86, alpha=1.0, scale=1.0):
    sz = size
    while font(sz).getlength(text) > maxw and sz > 30:
        sz -= 2
    sz = max(10, int(sz * scale))
    f = font(sz)
    stroke = max(3, sz // 9)
    tw = f.getlength(text)
    layer = Image.new("RGBA", (W, 240), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x, y = (W - tw) / 2, 120 - sz / 2
    d.text((x + 4, y + 7), text, font=f, fill=(10, 25, 60, 170), stroke_width=stroke, stroke_fill=(10, 25, 60, 170))
    d.text((x, y), text, font=f, fill=YEL, stroke_width=stroke, stroke_fill=BLUE)
    if alpha < 1:
        layer.putalpha(layer.getchannel("A").point(lambda v: int(v * alpha)))
    frame.alpha_composite(layer, (0, int(cy - 120)))


# ---------- cenas ----------
CARD_CY = 700
NAME_CY = 205


def draw_beat(frame, t, beat):
    s, r, e = beat["s"], beat["r"], beat["e"]
    flip = 0.07
    if t < r:
        # verso entra com um pop e vira no fim
        k = ease_out((t - s) / 0.12)
        sc = 0.88 + 0.12 * k
        sx = sc
        if t > r - flip:
            sx = sc * max(0.02, (r - t) / flip)
        place(frame, BACK, W / 2, CARD_CY, sx, sc)
    else:
        u = t - r
        sx = min(1.0, max(0.02, u / flip))
        pop = 1.0 + 0.06 * (1 - ease_out((u - flip) / 0.15)) if u > flip else 1.0
        img = card(beat["file"])
        place(frame, img, W / 2, CARD_CY, sx * pop, pop)
        # flash branco na virada
        fl = max(0.0, 1 - u / 0.12)
        if fl > 0:
            ov = Image.new("RGBA", (W, H), (255, 255, 255, int(110 * fl)))
            frame.alpha_composite(ov)
        k = ease_out(u / 0.1)
        title(frame, beat["name"].upper(), NAME_CY + (1 - k) * -30, alpha=k)


GCOLS, GROWS = 13, 12
GW = 50
GH = int(GW * 825 / 600)
GX0 = (W - GCOLS * (GW + 3)) // 2
GY0 = 330


def draw_grid(frame, t, chant, caught, new_from):
    dim = int(120 * ease_out((t - chant["start"]) / 0.2))
    frame.alpha_composite(Image.new("RGBA", (W, H), (10, 20, 50, dim)))
    slot = Image.new("RGBA", (GW, GH), (0, 0, 0, 0))
    ImageDraw.Draw(slot).rounded_rectangle((0, 0, GW - 1, GH - 1), 4, fill=(255, 255, 255, 40), outline=(255, 255, 255, 140))
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for i in range(GCOLS * GROWS):
        x = GX0 + (i % GCOLS) * (GW + 3)
        y = GY0 + (i // GCOLS) * (GH + 3)
        layer.alpha_composite(slot, (x, y))
    tg = chant["start"]
    for i, path in enumerate(caught):
        x = GX0 + (i % GCOLS) * (GW + 3) + GW // 2
        y = GY0 + (i // GCOLS) * (GH + 3) + GH // 2
        if i >= new_from:
            appear = tg + 0.05 + (i - new_from) * 0.035
            if t < appear:
                continue
            k = ease_out((t - appear) / 0.12)
            sc = 1.6 - 0.6 * k
        else:
            sc = 1.0
        place(layer, card(path, GW), x, y, sc, sc, shadow=False)
    # entrada da grade
    k = ease_out((t - tg) / 0.2)
    if k < 1:
        layer = layer.resize((W, H)).rotate(0)
        layer.putalpha(layer.getchannel("A").point(lambda v: int(v * k)))
    frame.alpha_composite(layer)
    # texto do refrão, palavra por palavra
    txt = None
    for ev in chant["text"]:
        if t >= ev["t"]:
            txt = ev
    if txt:
        words = txt["words"].split()
        n = min(len(words), 1 + int((t - txt["t"]) / txt.get("step", 0.13)))
        pop = 1 + 0.15 * (1 - ease_out((t - txt["t"]) / 0.15))
        title(frame, " ".join(words[:n]), 210, size=96, scale=pop)


def render():
    beats, chants, colors = tl["beats"], tl["chants"], tl["colors"]
    caught_all = [b["file"] for b in beats]
    ff = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-ss", str(T0), "-t", str(T1 - T0), "-i", AUDIO,
         "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", OUT],
        stdin=subprocess.PIPE)
    n = int(round((T1 - T0) * FPS))
    for i in range(n):
        t = T0 + i / FPS
        seg = max([c for c in colors if c["t"] <= t], key=lambda c: c["t"])
        frame = background(t, seg["c"]).convert("RGBA")
        ch = next((c for c in chants if c["start"] <= t < c["end"]), None)
        if ch:
            idx = sum(1 for b in beats if b["r"] < ch["start"])
            draw_grid(frame, t, ch, caught_all[:idx], ch["new_from"])
        else:
            b = next((b for b in beats if b["s"] <= t < b["e"]), None)
            if b:
                draw_beat(frame, t, b)
        # fade de saída
        fo = tl.get("fade_out")
        if fo and t > T1 - fo:
            a = int(255 * (t - (T1 - fo)) / fo)
            frame.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, a)))
        ff.stdin.write(frame.convert("RGB").tobytes())
    ff.stdin.close()
    ff.wait()


if __name__ == "__main__":
    render()
