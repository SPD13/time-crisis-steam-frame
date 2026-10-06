"""Steam library artwork for the Steam Frame devkit title, from three source pictures:
the cover, an in-game screenshot and the logo on white. Adds "VR" beside the logo and a
"STEAM FRAME EDITION" badge under it. Output (installed by frame/install-library-art.py):

    capsule.png  600x900    library grid (portrait capsule)   -> <appid>p.png
    wide.png     920x430    recently played / wide capsule    -> <appid>.png
    hero.png     3840x1240  banner at the top of the game page -> <appid>_hero.png
    logo.png     1280 wide  transparent logo drawn over hero  -> <appid>_logo.png
    icon.png     256x256    small icon

Needs Pillow and NumPy:  python3 -m venv build/artenv && build/artenv/bin/pip install pillow numpy
    build/artenv/bin/python tools/make_library_art.py --cover C.jpeg --ingame I.jpeg --logo L.jpeg
"""
from pathlib import Path
import argparse
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops

ROOT = Path(__file__).resolve().parents[1]
EDITION = 'STEAM FRAME EDITION'
FONTS = ['/System/Library/Fonts/Supplemental/Arial Black.ttf', '/System/Library/Fonts/Supplemental/Impact.ttf',
         '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', r'C:\Windows\Fonts\ariblk.ttf']
# Palette of the Time Crisis logo: chrome blue letters, red rim, navy outline, yellow crosshair.
NAVY = (16, 22, 74)
BLUE = (34, 52, 168)
RED = (214, 28, 36)
YELLOW = (250, 214, 24)


def font(size):
    return ImageFont.truetype(next(f for f in FONTS if Path(f).exists()), size)


def cut_logo(path):
    """The logo on white: remove only the white connected to the border, keep white highlights inside letters."""
    rgb = Image.open(path).convert('RGB')
    w, h = rgb.size
    big = rgb.resize((w * 4, h * 4), Image.LANCZOS)
    a = np.asarray(big).astype(int)
    white = (a.min(axis=2) > 225)
    # flood fill from the border through near-white pixels
    from collections import deque
    H, W = white.shape
    outside = np.zeros_like(white)
    q = deque()
    for x in range(W):
        for y in (0, H - 1):
            if white[y, x] and not outside[y, x]: outside[y, x] = True; q.append((y, x))
    for y in range(H):
        for x in (0, W - 1):
            if white[y, x] and not outside[y, x]: outside[y, x] = True; q.append((y, x))
    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < H and 0 <= nx < W and white[ny, nx] and not outside[ny, nx]:
                outside[ny, nx] = True; q.append((ny, nx))
    alpha = Image.fromarray(np.where(outside, 0, 255).astype(np.uint8))
    # Pull the edge in by one source pixel and soften it, so no white fringe remains.
    alpha = alpha.filter(ImageFilter.MinFilter(5)).filter(ImageFilter.GaussianBlur(1.6))
    im = big.convert('RGBA'); im.putalpha(alpha)
    return im.crop(im.getbbox())


def chrome_text(text, height):
    """Italic chrome lettering in the logo's style: blue-white-blue fill, red rim, navy outline."""
    f = font(400)
    l, t, r, b = f.getbbox(text)
    tw, th = r - l, b - t
    pad = 60
    mask = Image.new('L', (tw + 2 * pad, th + 2 * pad))
    ImageDraw.Draw(mask).text((pad - l, pad - t), text, font=f, fill=255)
    # slant like the logo (about 14 degrees)
    shear = 0.25
    W = mask.width + int(mask.height * shear)
    mask = mask.transform((W, mask.height), Image.AFFINE, (1, shear, -mask.height * shear, 0, 1, 0), Image.BICUBIC)
    fill_h = mask.height
    rows = []
    for y in range(fill_h):
        v = (y - pad) / th
        if v < .42: c = tuple(int(BLUE[i] + (255 - BLUE[i]) * max(0, v) / .42) for i in range(3))
        elif v < .55: c = (255, 255, 255)
        else: c = tuple(int(255 + (BLUE[i] * .8 - 255) * min(1, (v - .55) / .45)) for i in range(3))
        rows.append(c)
    grad = Image.new('RGB', (1, fill_h)); grad.putdata(rows); grad = grad.resize(mask.size)
    rim = mask.filter(ImageFilter.MaxFilter(17))
    outline = rim.filter(ImageFilter.MaxFilter(17))
    out = Image.new('RGBA', mask.size)
    out.paste(NAVY + (255,), (0, 0), outline)
    out.paste(RED + (255,), (0, 0), rim)
    out.paste(grad, (0, 0), mask)
    out = out.crop(out.getbbox())
    return out.resize((round(out.width * height / out.height), height), Image.LANCZOS)


def badge(width, text=EDITION):
    """Navy pill with a yellow rim and white capitals."""
    f = font(100)
    l, t, r, b = f.getbbox(text)
    f = font(round(100 * width * .80 / (r - l)))
    l, t, r, b = f.getbbox(text)
    h = round((b - t) * 2.0)
    rim = max(2, round(h * .09))
    im = Image.new('RGBA', (width, h))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, width - 1, h - 1], radius=h // 2, fill=YELLOW + (255,))
    d.rounded_rectangle([rim, rim, width - 1 - rim, h - 1 - rim], radius=h // 2 - rim, fill=NAVY + (255,))
    d.text(((width - (r - l)) / 2 - l, (h - (b - t)) / 2 - t), text, font=f, fill=(255, 255, 255, 255))
    return im


def shadow(im, radius, opacity=.75):
    a = im.getchannel('A').filter(ImageFilter.GaussianBlur(radius)).point(lambda v: int(v * opacity))
    s = Image.new('RGBA', im.size, (0, 0, 0, 255)); s.putalpha(a)
    return s


def title(logo, width, with_badge=True):
    """Logo + "VR" to the right of CRISIS (+ edition badge under it), on transparency, 'width' wide."""
    vr = chrome_text('VR', round(logo.height * .52))
    gap = round(logo.height * .02)
    # VR sits at the lower right, on the CRISIS line, just past the crosshair's lower arm.
    w = logo.width + gap + vr.width
    im = Image.new('RGBA', (w, logo.height))
    im.alpha_composite(logo, (0, 0))
    im.alpha_composite(vr, (logo.width + gap, logo.height - vr.height - round(logo.height * .04)))
    if with_badge:
        b = badge(round(w * .70))
        overlap = b.height // 5
        full = Image.new('RGBA', (w, im.height + b.height - overlap))
        full.alpha_composite(im, (0, 0))
        full.alpha_composite(b, ((w - b.width) // 2, im.height - overlap))
        im = full
    scale = width / im.width
    im = im.resize((width, round(im.height * scale)), Image.LANCZOS)
    pad = max(8, width // 40)
    out = Image.new('RGBA', (im.width + 2 * pad, im.height + 2 * pad))
    out.alpha_composite(shadow(im, pad / 2), (pad, pad + pad // 3))
    out.alpha_composite(im, (pad, pad))
    return out


def cover_fill(src, size):
    """Scale to cover 'size', centred crop."""
    w, h = size
    s = max(w / src.width, h / src.height)
    im = src.resize((round(src.width * s), round(src.height * s)), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def vertical_fade(size, top, bottom):
    w, h = size
    col = Image.new('L', (1, h)); col.putdata([int(top + (bottom - top) * y / (h - 1)) for y in range(h)])
    return col.resize(size)


FADE = 110  # rows over which the cover's top edge fades into the rebuilt sky


def cover_without_logo(cover, size, cut):
    """The cover below its own logo ('cut': first source row free of it), under a rebuilt sky.
    The sky keeps the cover's own colours: a per-row median of its right edge, where the logo
    covers only thin crosshair lines."""
    w, h = size
    s = w / cover.width
    body = cover.crop((0, cut, cover.width, cover.height))
    body = body.resize((w, round(body.height * s)), Image.LANCZOS)
    top = h - body.height
    a = np.asarray(cover).astype(float)
    rows = np.median(a[:cut, int(cover.width * .88):], axis=1)              # cut x 3
    sky = Image.fromarray(np.repeat(rows[:, None, :], 8, axis=1).astype(np.uint8))
    sky = sky.resize((w, top + FADE), Image.BICUBIC).filter(ImageFilter.GaussianBlur(3))
    # The cover's film grain, so the rebuilt sky does not look flat next to the original.
    grain = Image.effect_noise((w, top + FADE), 6).convert('RGB')
    sky = ImageChops.add(sky, grain, scale=1, offset=-128)     # noise is centred on 128
    out = Image.new('RGB', size)
    out.paste(sky, (0, 0))
    fade = vertical_fade((w, FADE), 0, 255)
    band = Image.composite(body.crop((0, 0, w, FADE)), sky.crop((0, top, w, top + FADE)), fade)
    out.paste(body, (0, top))
    out.paste(band, (0, top))
    return out, top


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--cover', type=Path, required=True)
    p.add_argument('--ingame', type=Path, required=True)
    p.add_argument('--logo', type=Path, required=True)
    p.add_argument('--out', type=Path, default=ROOT / 'frame/library-art')
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    logo = cut_logo(args.logo)
    cover = Image.open(args.cover).convert('RGB')
    ingame = Image.open(args.ingame).convert('RGB')

    # logo.png: drawn by Steam over the hero.
    title(logo, 1240).save(args.out / 'logo.png')

    # capsule.png: the cover below its logo, under a rebuilt sky with the VR / Steam Frame Edition title.
    cap, top = cover_without_logo(cover, (600, 900), cut=216)
    cap = cap.convert('RGBA')
    t = title(logo, 580)
    cap.alpha_composite(t, ((600 - t.width) // 2, max(6, (top - t.height) // 2)))
    cap.convert('RGB').save(args.out / 'capsule.png')

    # wide.png: the arcade scene, darkened on the left behind the title.
    wide = cover_fill(ingame, (920, 430)).filter(ImageFilter.GaussianBlur(1.2)).convert('RGBA')
    shade = Image.new('RGBA', wide.size, (6, 8, 26, 255))
    # Dark behind the title on the left, clear from about 80% of the width.
    ramp = Image.new('L', (920, 1)); ramp.putdata([230 if x < 300 else int(230 * max(0, 1 - (x - 300) / 460)) for x in range(920)]); ramp = ramp.resize(wide.size)
    wide.alpha_composite(Image.composite(shade, Image.new('RGBA', wide.size), ramp))
    t = title(logo, 500)
    wide.alpha_composite(t, (14, (430 - t.height) // 2))
    wide.convert('RGB').save(args.out / 'wide.png')

    # hero.png: the scene, softened (it is scaled ~6x), darker at the bottom where Steam draws the logo.
    hero = cover_fill(ingame, (3840, 1240)).filter(ImageFilter.GaussianBlur(5)).convert('RGBA')
    fade = vertical_fade(hero.size, 40, 190)
    hero.alpha_composite(Image.composite(Image.new('RGBA', hero.size, (6, 8, 26, 255)), Image.new('RGBA', hero.size), fade))
    hero.convert('RGB').save(args.out / 'hero.png')

    # icon.png: logo and VR on navy.
    icon = Image.new('RGBA', (256, 256))
    ImageDraw.Draw(icon).rounded_rectangle([0, 0, 255, 255], radius=44, fill=NAVY + (255,))
    t = title(logo, 250, with_badge=False)
    icon.alpha_composite(t, ((256 - t.width) // 2, (256 - t.height) // 2))
    icon.save(args.out / 'icon.png')
    for name in ('capsule', 'wide', 'hero', 'logo', 'icon'):
        im = Image.open(args.out / f'{name}.png'); print(f'{name}.png {im.size[0]}x{im.size[1]}')


if __name__ == '__main__':
    main()
