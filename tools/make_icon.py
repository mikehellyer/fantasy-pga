"""Draw the Fantasy PGA app icon (pixel art) and export it for every platform.

    .venv/bin/python tools/make_icon.py

Writes packaging/icon.png (1024px), icon.icns (macOS), icon.ico (Windows) and
src/fantasy_pga/assets/icon.png (the in-game window icon). Needs Pillow,
which is in requirements-dev.txt.
"""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
N = 32  # drawn at 32x32, then scaled up with hard pixel edges

BORDER = (120, 105, 196)  # C64 light blue
SKY = (64, 49, 141)  # C64 blue
GREEN = (85, 160, 73)
LIGHT_GREEN = (148, 224, 137)
RED = (220, 40, 40)
YELLOW = (191, 206, 114)
WHITE = (255, 255, 255)
GREY = (159, 159, 159)
BLACK = (0, 0, 0)


def draw() -> Image.Image:
    img = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # rounded tile with a light-blue C64 border, night-blue sky and a green
    d.rounded_rectangle((0, 0, N - 1, N - 1), radius=6, fill=BORDER)
    d.rounded_rectangle((2, 2, N - 3, N - 3), radius=5, fill=SKY)
    d.rectangle((3, 21, N - 4, N - 4), fill=GREEN)
    d.ellipse((5, 19, 27, 26), fill=LIGHT_GREEN)
    d.ellipse((14, 21, 17, 23), fill=BLACK)  # the hole
    # the pin and its flag
    d.line((15, 5, 15, 22), fill=WHITE)
    d.polygon([(16, 5), (25, 8), (16, 11)], fill=RED)
    d.line((16, 5, 16, 11), fill=YELLOW)
    # a golf ball on the lip
    d.ellipse((19, 19, 23, 23), fill=WHITE, outline=GREY)
    return img


def main():
    icon = draw()
    big = icon.resize((1024, 1024), Image.NEAREST)
    pack = ROOT / "packaging"
    pack.mkdir(exist_ok=True)
    big.save(pack / "icon.png")
    big.save(pack / "icon.icns")
    big.save(pack / "icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    icon.resize((64, 64), Image.NEAREST).save(ROOT / "src" / "fantasy_pga" / "assets" / "icon.png")
    print("icons written to", pack)


if __name__ == "__main__":
    main()
