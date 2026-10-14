"""Turn a portrait photo into the ASCII art shown on the profile card.

Run it once, and again whenever the photo changes:

    pip install pillow "rembg[cpu]"
    python scripts/ascii_art.py photo.jpg

It writes assets/ascii_dark.txt (light glyphs on a dark card) and
assets/ascii_light.txt (dark glyphs on a light card). rembg removes the
background so only the person is drawn; pass --keep-bg to skip it.
"""

import argparse
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent.parent

# The art block on the card is COLS x ROWS characters. A character cell is
# 7.2px wide (12px monospace, size-adjusted) and 14.2px tall (line height),
# matching ART_FONT / ART_LINE in build_card.py.
COLS, ROWS = 52, 35
CELL_W, CELL_H = 7.2, 14.2

# Sparse to dense.
RAMP = " .'`,:;!|ijlLtfkmwM%N@"


def remove_background(img, model="isnet-general-use"):
    try:
        from rembg import new_session, remove
    except ImportError:
        print("rembg is not installed, keeping the background")
        return img
    return remove(img, session=new_session(model))


def fit_to_block(img):
    """Crop to the subject, then to the aspect ratio of the art block around the head."""
    solid = img.getchannel("A").point(lambda a: 255 if a > 32 else 0)
    bbox = solid.getbbox()
    if bbox:
        img, solid = img.crop(bbox), solid.crop(bbox)
    target = (COLS * CELL_W) / (ROWS * CELL_H)
    w, h = img.size
    if w / h > target:
        # Wider than the block: trim the shoulders, keep the head in the middle.
        new_w = round(h * target)
        head = solid.crop((0, 0, w, h * 2 // 5)).getbbox() or (0, 0, w, h)
        left = min(max(0, (head[0] + head[2]) // 2 - new_w // 2), w - new_w)
        return img.crop((left, 0, left + new_w, h))
    new_w = round(h * target)
    canvas = Image.new("RGBA", (new_w, h), (0, 0, 0, 0))
    canvas.paste(img, ((new_w - w) // 2, 0))
    return canvas


def subject_cells(alpha):
    """Cells that are solid enough and part of the biggest blob, so stray bits of background drop out."""
    solid = {(x, y) for y in range(ROWS) for x in range(COLS) if alpha.getpixel((x, y)) >= 110}
    best, seen = set(), set()
    for start in solid:
        if start in seen:
            continue
        blob, stack = set(), [start]
        while stack:
            cell = stack.pop()
            if cell in seen or cell not in solid:
                continue
            seen.add(cell)
            blob.add(cell)
            x, y = cell
            stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        if len(blob) > len(best):
            best = blob
    return best


def prepare(photo, keep_bg=False):
    """Return the block-sized luminance image and the cells that belong to the person."""
    img = ImageOps.exif_transpose(Image.open(photo)).convert("RGBA")
    if not keep_bg:
        img = remove_background(img)
    img = fit_to_block(img)

    cells = subject_cells(img.resize((COLS, ROWS), Image.Resampling.BOX).getchannel("A"))
    mask = Image.new("L", (COLS, ROWS), 0)
    for cell in cells:
        mask.putpixel(cell, 255)

    lum = img.convert("L").filter(ImageFilter.UnsharpMask(radius=3, percent=180, threshold=2))
    lum = ImageOps.equalize(lum.resize((COLS, ROWS), Image.Resampling.BOX), mask=mask)
    return lum, cells


def to_ascii(lum, cells, invert, ramp=RAMP):
    rows = []
    levels = len(ramp) - 1
    for y in range(ROWS):
        line = []
        for x in range(COLS):
            if (x, y) not in cells:
                line.append(" ")
                continue
            v = lum.getpixel((x, y)) / 255
            if invert:
                v = 1 - v
            # Never drop a subject cell to a blank, so the silhouette stays whole.
            line.append(ramp[max(1, round(v * levels))])
        rows.append("".join(line).rstrip())
    return "\n".join(rows) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("photo", type=Path)
    parser.add_argument("--keep-bg", action="store_true")
    parser.add_argument("--out", type=Path, default=ROOT / "assets")
    args = parser.parse_args()

    lum, cells = prepare(args.photo, args.keep_bg)
    args.out.mkdir(parents=True, exist_ok=True)
    # Dark card: bright skin gets dense glyphs. Light card: dark hair gets them.
    (args.out / "ascii_dark.txt").write_text(to_ascii(lum, cells, invert=False), encoding="utf-8")
    (args.out / "ascii_light.txt").write_text(to_ascii(lum, cells, invert=True), encoding="utf-8")
    print(f"wrote {args.out / 'ascii_dark.txt'} and {args.out / 'ascii_light.txt'}")


if __name__ == "__main__":
    main()
