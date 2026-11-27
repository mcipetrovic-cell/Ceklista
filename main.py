"""Покретање програма „Чек-листа“ (Ceklista.exe).

    Ceklista.exe                      — отвара последњу чек-листу (или нову)
    Ceklista.exe <датотека>.ceklista  — отвара ту чек-листу (двоклик на датотеку)
    Ceklista.exe --provera <излаз>    — самопровера пакета (за GitHub Actions): питања, сажетак, Word, датотеке, прозор
"""

from __future__ import annotations

import sys


def provera(izlaz: str | None) -> int:
    """Самопровера направљеног програма: ништа не дира у фасцикли корисника (све у привременој фасцикли)."""
    import os
    import tempfile
    import traceback
    import zipfile
    from pathlib import Path

    redovi, ok = [], True

    def korak(naziv, fn):
        nonlocal ok
        try:
            rezultat = fn()
            redovi.append(f"OK   {naziv}" + (f": {rezultat}" if rezultat else ""))
        except Exception:  # noqa: BLE001 — извештај самопровере набраја сваки неуспех
            ok = False
            redovi.append(f"ПАЛО {naziv}\n{traceback.format_exc()}")

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["CEKLISTA_FASCIKLA"] = str(Path(tmp) / "cekliste")
        os.environ["CEKLISTA_LOKALNO"] = str(Path(tmp) / "lokalno")
        from ceklista import VERZIJA, fajl, logika as L, pitanja as P, sazetak as S, word

        stanje = {}

        def pitanja():
            n = sum(len(o.get("pitanja", [])) + len(o.get("po_stranci", [])) for o in P.DEFINICIJA)
            assert n > 90, n
            return f"{n} питања у {len(P.DEFINICIJA)} целина, верзија {VERZIJA}"

        def primer():
            c = L.nova("ПРОБА 1/2026", "продаја")
            L.dodaj_lice(c, "ПЕТАР ПЕТРОВИЋ", "продавац")
            L.dodaj_lice(c, "ЈЕЛЕНА ЈОВАНОВИЋ", "купац")
            L.odgovori(c, "forma", "јавнобележнички запис")
            L.odgovori(c, "1.brak", "у браку")
            L.odgovori(c, "cena", "85.000")
            L.grupna_potvrda(c, L.stanje(c)["grupna"])
            stanje["c"] = c
            return f"{L.stanje(c)['brojaci']}"

        def sazetak():
            t = S.kao_tekst(S.sazetak(stanje["c"]))
            assert "ПЕТАР ПЕТРОВИЋ" in t and "Купопродајна цена: 85.000" in t, t
            return f"{len(t)} знакова"

        def docx():
            p = word.sacuvaj(S.sazetak(stanje["c"]), Path(tmp) / "sazetak.docx")
            with zipfile.ZipFile(p) as z:
                assert "word/document.xml" in z.namelist()
                assert "ПЕТАР ПЕТРОВИЋ" in z.read("word/document.xml").decode("utf-8")
            return f"{p.stat().st_size} бајтова"

        def datoteka():
            p = fajl.sacuvaj(stanje["c"], fajl.novo_ime(stanje["c"]))
            assert fajl.ucitaj(p)["odgovori"] == stanje["c"]["odgovori"]
            return p.name

        def prozor():
            import tkinter as tk

            from ceklista import gui

            koren = tk.Tk()
            koren.withdraw()
            app = gui.Aplikacija(koren)
            for oid in [x[0] for x in L.ODELJCI] + [gui.POTVRDE, gui.SAZETAK, gui.LICA]:
                app.idi(oid)
            koren.update()
            koren.destroy()
            return "сви делови прозора"

        for naziv, fn in (("питања", pitanja), ("пример чек-листе", primer), ("сажетак", sazetak), ("Word", docx),
                          ("датотека .ceklista", datoteka), ("прозор", prozor)):
            korak(naziv, fn)
    izvestaj = "\n".join(redovi) + ("\nСВЕ ЈЕ У РЕДУ\n" if ok else "\nПРОВЕРА НИЈЕ ПРОШЛА\n")
    if izlaz:
        Path(izlaz).write_text(izvestaj, encoding="utf-8")
    elif sys.stdout is not None:  # Ceklista.exe без конзоле нема stdout
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        print(izvestaj)
    return 0 if ok else 1


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "--provera":
        return provera(sys.argv[2] if len(sys.argv) > 2 else None)
    from ceklista import gui

    return gui.main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
