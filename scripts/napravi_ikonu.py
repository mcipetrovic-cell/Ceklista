"""Иконица програма data/Ceklista.ico: светла картица са тегет квачицом и три реда листе (Pillow, само при изради)."""

from pathlib import Path

from PIL import Image, ImageDraw

IZLAZ = Path(__file__).resolve().parent.parent / "data" / "Ceklista.ico"


def slika(n: int = 256) -> Image.Image:
    s = n / 256
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([8 * s, 8 * s, 248 * s, 248 * s], radius=44 * s, fill=(247, 243, 234), outline=(201, 191, 168),
                        width=max(1, round(6 * s)))
    for i, y in enumerate((70, 128, 186)):
        d.rounded_rectangle([110 * s, (y - 9) * s, 214 * s, (y + 9) * s], radius=9 * s,
                            fill=(79, 111, 154) if i < 2 else (201, 191, 168))
        d.rounded_rectangle([44 * s, (y - 20) * s, 84 * s, (y + 20) * s], radius=8 * s, outline=(31, 42, 68),
                            width=max(1, round(6 * s)), fill=(255, 255, 255))
        if i < 2:
            d.line([(50 * s, y * s), (62 * s, (y + 12) * s), (90 * s, (y - 22) * s)], fill=(47, 107, 61),
                   width=max(2, round(10 * s)), joint="curve")
    return im


if __name__ == "__main__":
    IZLAZ.parent.mkdir(exist_ok=True)
    slika().save(IZLAZ, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    slika().save(IZLAZ.with_suffix(".png"))
    print(IZLAZ)
