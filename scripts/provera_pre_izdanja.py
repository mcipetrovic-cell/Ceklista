"""Контрола пре издања: верзија је уписана у CHANGELOG.md, а у Git-у нема база, снимака HAR ни нечега што личи на
прави ЈМБГ (13 цифара) или број рачуна. Пробе користе само измишљена лица и не уносе ЈМБГ."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

KOREN = Path(__file__).resolve().parent.parent
ZABRANJENE = (".db", ".sqlite", ".har", ".ceklista", ".docx", ".xlsx", ".pdf")
JMBG = re.compile(r"(?<!\d)\d{13}(?!\d)")
RACUN = re.compile(r"(?<!\d)\d{3}-\d{13}-\d{2}(?!\d)")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows конзола (cp1252) не исписује ћирилицу
    greske = []
    sys.path.insert(0, str(KOREN))
    import ceklista

    if f"## {ceklista.VERZIJA_BROJ} " not in (KOREN / "CHANGELOG.md").read_text(encoding="utf-8"):
        greske.append(f"CHANGELOG.md нема ставку за верзију {ceklista.VERZIJA_BROJ}")
    try:
        datoteke = subprocess.run(["git", "ls-files"], cwd=KOREN, capture_output=True, text=True, check=True).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        datoteke = [str(p.relative_to(KOREN)) for p in KOREN.rglob("*") if p.is_file() and ".git" not in p.parts]
    for ime in datoteke:
        if ime.lower().endswith(ZABRANJENE):
            greske.append(f"у Git-у не сме бити: {ime}")
            continue
        p = KOREN / ime
        if p.suffix.lower() in (".ico", ".png") or not p.is_file():
            continue
        tekst = p.read_text(encoding="utf-8", errors="ignore")
        for obrazac, naziv in ((JMBG, "13 цифара (ЈМБГ?)"), (RACUN, "број рачуна")):
            if obrazac.search(tekst):
                greske.append(f"{ime}: {naziv}")
    for g in greske:
        print("ГРЕШКА:", g)
    print("Контрола пре издања:", "није прошла" if greske else "у реду")
    return 1 if greske else 0


if __name__ == "__main__":
    raise SystemExit(main())
