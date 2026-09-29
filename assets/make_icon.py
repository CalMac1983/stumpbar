"""Draw the app icon: a red cricket ball on a green rounded square.

Writes assets/icon.png (1024px) and assets/CricketTray.icns.
Needs Pillow and numpy:  .venv/bin/pip install pillow numpy
"""

import math
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).parent
SIZE = 1024
SS = 4  # supersampling factor for smooth edges
S = SIZE * SS

# macOS icon grid: 824px body inset 100px, ~185px corner radius.
BODY = 824 * SS
INSET = (S - BODY) // 2
RADIUS = 185 * SS

BALL_R = 250 * SS
BALL_C = (S / 2, S / 2 - 6 * SS)


def hex_rgb(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], dtype=float)


def rounded_mask(size, box, radius):
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle(box, radius, fill=255)
    return m


def background():
    top, bottom = hex_rgb("#2E8B57"), hex_rgb("#0E4A2E")
    t = np.linspace(0, 1, S)[:, None, None]
    grad = (top * (1 - t) + bottom * t).repeat(S, axis=1)
    img = Image.fromarray(grad.astype(np.uint8), "RGB").convert("RGBA")

    mask = rounded_mask(S, (INSET, INSET, INSET + BODY, INSET + BODY), RADIUS)
    img.putalpha(mask)
    return img


def ball():
    cx, cy = BALL_C
    yy, xx = np.mgrid[0:S, 0:S].astype(float)
    dx, dy = (xx - cx) / BALL_R, (yy - cy) / BALL_R
    r2 = dx ** 2 + dy ** 2
    inside = r2 <= 1

    # Sphere normal for simple lighting from the top-left.
    z = np.sqrt(np.clip(1 - r2, 0, 1))
    light = np.array([-0.45, -0.55, 0.70])
    light /= np.linalg.norm(light)
    lambert = np.clip(dx * light[0] + dy * light[1] + z * light[2], 0, 1)

    dark, lit = hex_rgb("#7A1512"), hex_rgb("#E0473B")
    col = dark + (lit - dark) * lambert[..., None] ** 0.9

    # Soft specular highlight.
    spec = np.clip(lambert, 0, 1) ** 40 * 70
    col = np.clip(col + spec[..., None], 0, 255)

    alpha = np.where(inside, 255, 0).astype(np.uint8)
    img = Image.fromarray(col.astype(np.uint8), "RGB").convert("RGBA")
    img.putalpha(Image.fromarray(alpha))
    return img


def seam(img):
    """Seam and stitches, placed in 3D on the sphere and projected to 2D."""
    d = ImageDraw.Draw(img)
    cx, cy = BALL_C

    n = np.array([0.42, -0.78, 0.46])  # normal of the seam's great circle
    n /= np.linalg.norm(n)
    u = np.cross(n, [0, 0, 1.0])
    u /= np.linalg.norm(u)
    v = np.cross(n, u)

    def to_screen(p):
        return (cx + p[0] * BALL_R, cy + p[1] * BALL_R)

    def on_sphere(p):
        return p / np.linalg.norm(p)

    steps = 720
    ts = np.linspace(0, 2 * math.pi, steps, endpoint=False)

    # Central raised seam: a slightly darker band.
    for offset, colour, width in ((0.0, (120, 22, 18, 255), 16), (0.0, (160, 34, 28, 255), 8)):
        pts = []
        for t in ts:
            p = on_sphere(math.cos(t) * u + math.sin(t) * v + offset * n)
            if p[2] > 0.02:
                pts.append(to_screen(p))
            elif len(pts) > 1:
                d.line(pts, fill=colour, width=width * SS // 4, joint="curve")
                pts = []
        if len(pts) > 1:
            d.line(pts, fill=colour, width=width * SS // 4, joint="curve")

    # Two rows of angled stitches either side of the seam.
    stitches = 52
    for side in (-1, 1):
        for i in range(stitches):
            t = 2 * math.pi * i / stitches
            p = math.cos(t) * u + math.sin(t) * v
            tangent = -math.sin(t) * u + math.cos(t) * v
            a = on_sphere(p + side * 0.07 * n - side * 0.02 * tangent)
            b = on_sphere(p + side * 0.14 * n + side * 0.02 * tangent)
            if min(a[2], b[2]) <= 0.08:
                continue
            fade = min(1.0, (min(a[2], b[2]) - 0.08) * 4)  # soften near the edge
            colour = (245, 236, 220, int(235 * fade))
            d.line([to_screen(a), to_screen(b)], fill=colour, width=4 * SS)


def shadow():
    """Soft ground shadow under the ball."""
    sh = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    cx, cy = BALL_C
    w, h = BALL_R * 0.95, BALL_R * 0.22
    top = cy + BALL_R * 0.88
    ImageDraw.Draw(sh).ellipse((cx - w, top - h, cx + w, top + h), fill=(0, 20, 8, 110))
    return sh.filter(ImageFilter.GaussianBlur(28 * SS))


def main():
    icon = background()

    body_mask = rounded_mask(S, (INSET, INSET, INSET + BODY, INSET + BODY), RADIUS)
    sh = shadow()
    sh.putalpha(Image.fromarray(np.minimum(np.array(sh.getchannel("A")), np.array(body_mask))))
    icon = Image.alpha_composite(icon, sh)

    b = ball()
    seam_layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    seam(seam_layer)
    seam_layer.putalpha(Image.fromarray(np.minimum(np.array(seam_layer.getchannel("A")),
                                                   np.array(b.getchannel("A")))))
    b = Image.alpha_composite(b, seam_layer)
    icon = Image.alpha_composite(icon, b)

    icon = icon.resize((SIZE, SIZE), Image.LANCZOS)
    png = HERE / "icon.png"
    icon.save(png)

    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "CricketTray.iconset"
        iconset.mkdir()
        for px in (16, 32, 128, 256, 512):
            icon.resize((px, px), Image.LANCZOS).save(iconset / f"icon_{px}x{px}.png")
            icon.resize((px * 2, px * 2), Image.LANCZOS).save(iconset / f"icon_{px}x{px}@2x.png")
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(HERE / "CricketTray.icns")], check=True)

    print(f"Wrote {png} and {HERE / 'CricketTray.icns'}")


if __name__ == "__main__":
    main()
