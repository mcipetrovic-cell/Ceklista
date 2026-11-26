"""Преузимање питања и правила чек-листе из Саве у `ceklista/pitanja.py`.

Један извор питања остаје Сава (`sava_app/cek_lista.py`, `cek_lista_modul.py`, `uop.py`); овај програм носи
њихов препис. Кад се питања у Сави промене, препис се прави поново:

    python scripts/preuzmi_iz_save.py <фасцикла Саве>

(покреће се Python-ом у коме Сава ради, нпр. `<Сава>\\.venv\\Scripts\\python`). Проба `tests/test_isto_kao_sava.py`
пада кад препис и Сава више нису исти (покреће се кад постоји променљива SAVA_PUT или фасцикла ../sava).
"""

from __future__ import annotations

import pprint
import subprocess
import sys
from pathlib import Path

IZLAZ = Path(__file__).resolve().parent.parent / "ceklista" / "pitanja.py"

# (модул Саве, име) — само подаци; правила (функције) су пренета у ceklista/logika.py
IZ_CEK_LISTE = (
    "DEFINICIJA", "TRI", "NEODREDJENA", "RASPOLAZE", "STICE", "NIJE_LICNO", "NEISPLACENO", "PRENOS",
    "RASPOLAGAC", "STICALAC", "RASPOLAGAC_OSTALI", "STICALAC_OSTALI", "OBE_STRANE", "POLOZAJ_STICAOCA", "NIVOI",
    "PREDLOZI", "PREDLOZI_OPSTI", "REDOVNO", "REDOVNO_STRANKA", "PISMENOST", "NAPOMENA", "NESIGURNO", "UTICAJ",
    "OBAVEZNA", "OBAVEZNA_STRANKA", "WORD_RUCNO", "KONTROLA_LISTA", "CRVENE", "CRVENA_DOKUMENTACIJA",
    "ZA_SPREMNO", "NAPOMENA_OBAVEZNA", "DOPUNE_2020", "LIST_2020", "UZ_ZAPIS_2020", "SAMO_ZAPIS", "POTVRDE",
    "POTVRDE_POSLE_BROJA", "POVERLJIVO", "UKINUTA",
)
IZ_MODULA = ("STATUSI", "PROVERE_NEPOKRETNOSTI")


def _sredi(x):
    """frozenset → сортиран tuple (исти текст при сваком препису); остало непромењено."""
    if isinstance(x, (set, frozenset)):
        return tuple(sorted(x))
    if isinstance(x, dict):
        return {k: _sredi(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_sredi(v) for v in x]
    if isinstance(x, tuple):
        return tuple(_sredi(v) for v in x)
    return x


def podaci(sava: Path) -> dict:
    sys.path.insert(0, str(sava))
    from sava_app import cek_lista as CL, cek_lista_modul as M, obrasci, uop

    obrasci.postavi(sava / "obrasci")
    out = {ime: _sredi(getattr(CL, ime)) for ime in IZ_CEK_LISTE}
    out["STATUSI_MODULA"] = dict(M.STATUSI)
    out["PROVERE_NEPOKRETNOSTI"] = dict(M.PROVERE_NEPOKRETNOSTI)
    out["POSLOVI"] = M.poslovi()
    out["SVOJSTVA_PO_POSLU"] = _sredi(uop.SVOJSTVA_PO_POSLU)
    # дозвољене форме по правном послу, већ израчунате (Сава уз табелу чита и план образаца канцеларије)
    out["FORME"] = {p: {f: list(CL.forma_dozvoljena(p, f)) for f in ("јавнобележнички запис", "солемнизација")}
                    for p in out["POSLOVI"]}
    return out


def zaglavlje(sava: Path) -> str:
    try:
        komit = subprocess.run(["git", "-C", str(sava), "rev-parse", "--short", "HEAD"], capture_output=True,
                               text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        komit = "непознат"
    return (f'"""Питања и правила чек-листе — ПРЕПИС ИЗ САВЕ (комит {komit}), не мењати руком.\n\n'
            "Направљено: python scripts/preuzmi_iz_save.py <Сава>. Извор: sava_app/cek_lista.py (DEFINICIJA и правила),\n"
            "sava_app/cek_lista_modul.py (пет статуса, провера непокретности), sava_app/uop.py (својства странака) и\n"
            'план образаца канцеларије (правни послови, дозвољене форме)."""\n\n'
            "# ruff: noqa: E501\n")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    sava = Path(argv[1]).resolve()
    tekst = zaglavlje(sava)
    for ime, vrednost in podaci(sava).items():
        tekst += f"\n{ime} = " + pprint.pformat(vrednost, width=118, sort_dicts=False) + "\n"
    IZLAZ.write_text(tekst, encoding="utf-8")
    print(f"Уписано: {IZLAZ}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
