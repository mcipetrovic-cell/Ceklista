"""Позадина почетног екрана data/livada.png из исте слике коју има Сава (static/slike/sisli_livada_1875.jpg):
Алфред Сисле, „Ливада“ (1875), National Gallery of Art, Вашингтон — јавно власништво (CC0). Као у Сави
(sava.css): крем вео 80 % преко слике, исечак „cover“ око 30 % висине. Tk чита PNG (не JPG), па се слика
унапред смањује, прекрива велом и своди на 256 боја (мања датотека). Покреће се само при изради (Pillow):

    python scripts/napravi_pozadinu.py <Сава>/sava_app/static/slike/sisli_livada_1875.jpg
"""

import sys
from pathlib import Path

from PIL import Image

SIRINA, VISINA = 1920, 1200
KREM = (251, 248, 239)
VEO = 0.80
IZLAZ = Path(__file__).resolve().parent.parent / "data" / "livada.png"


def main(izvor: str) -> None:
    slika = Image.open(izvor).convert("RGB")
    razmera = max(SIRINA / slika.width, VISINA / slika.height)
    slika = slika.resize((round(slika.width * razmera), round(slika.height * razmera)), Image.LANCZOS)
    x = (slika.width - SIRINA) // 2
    y = max(0, min(slika.height - VISINA, round((slika.height - VISINA) * 0.30)))
    slika = slika.crop((x, y, x + SIRINA, y + VISINA))
    slika = Image.blend(slika, Image.new("RGB", slika.size, KREM), VEO)
    slika.quantize(colors=96, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(IZLAZ, optimize=True)
    print(IZLAZ, IZLAZ.stat().st_size)


if __name__ == "__main__":
    main(sys.argv[1])
