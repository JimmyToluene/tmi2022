"""Tile consecutive frames into labelled strips for visual annotation.

Usage: python make_strips.py <frames_dir> <out_dir> [per_strip=6] [tile_w=360]
Each strip is a 3x2 grid of consecutive frames with frame number + timestamp burned in.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FPS = 30.0


def main(frames_dir, out_dir, per=6, tw=360):
    frames = sorted(Path(frames_dir).glob("f*.jpg"))
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    th = tw * 16 // 9
    cols, rows = 3, (per + 2) // 3
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    for s in range(0, len(frames), per):
        chunk = frames[s:s + per]
        sheet = Image.new("RGB", (cols * tw + (cols - 1) * 6, rows * th + (rows - 1) * 6), (255, 255, 255))
        for k, fp in enumerate(chunk):
            n = int(fp.stem[1:])
            im = Image.open(fp).convert("RGB").resize((tw, th), Image.LANCZOS)
            d = ImageDraw.Draw(im)
            label = f"#{n}  {(n - 1) / FPS:.3f}s"
            d.rectangle([0, th - 34, tw, th], fill=(0, 0, 0))
            d.text((8, th - 30), label, fill=(255, 255, 0), font=font)
            sheet.paste(im, ((k % cols) * (tw + 6), (k // cols) * (th + 6)))
        a, b = int(chunk[0].stem[1:]), int(chunk[-1].stem[1:])
        sheet.save(out / f"strip_{a:04d}-{b:04d}.jpg", quality=88)
    print(len(list(out.glob("strip_*.jpg"))), "strips")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], *(int(x) for x in sys.argv[3:5]))
