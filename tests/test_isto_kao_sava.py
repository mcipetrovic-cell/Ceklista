"""Препис из Саве је исти као Сава, а правила дају исте исходе као модул Чек-листе у Сави.

Покреће се кад је Сава при руци: променљива SAVA_PUT (фасцикла Саве) или фасцикла ../sava поред овог програма,
Python-ом у коме Сава ради. Иначе се прескаче (нпр. на GitHub-у, где Саве нема)."""

from __future__ import annotations

import itertools
import os
import sys
from pathlib import Path

import pytest

from ceklista import logika as L, pitanja as P

KOREN = Path(__file__).resolve().parent.parent
SAVA = Path(os.environ.get("SAVA_PUT") or KOREN.parent / "sava")

if not (SAVA / "sava_app" / "cek_lista.py").is_file():
    pytest.skip("Сава није при руци (SAVA_PUT)", allow_module_level=True)
sys.path.insert(0, str(SAVA))
try:
    from sava_app import cek_lista as CL, cek_lista_modul as M  # noqa: E402
except ImportError as e:  # Python без библиотека Саве
    pytest.skip(f"Сава се не може учитати: {e}", allow_module_level=True)

sys.path.insert(0, str(KOREN / "scripts"))
import preuzmi_iz_save  # noqa: E402


def test_prepis_je_isti_kao_sava():
    try:
        iz_save = preuzmi_iz_save.podaci(SAVA)
    except ImportError as e:  # план образаца Саве тражи њене библиотеке (lxml…)
        pytest.skip(f"покрените Python-ом Саве: {e}")
    razlike = [ime for ime, vrednost in iz_save.items() if getattr(P, ime) != vrednost]
    assert not razlike, f"Питања у Сави су промењена — покрените scripts/preuzmi_iz_save.py: {razlike}"


ODGOVORI = {
    "posao": ["", "продаја", "поклон", "доживотно издржавање", "друго"],
    "forma": ["", "јавнобележнички запис", "солемнизација", "није утврђено"],
    "cena_isplacena": ["", "да", "не", "није утврђено"],
    "nacin_prijema": ["", "друго"],
    "tereti": ["", "да"],
    "mesto": ["", "терен"],
}
STRANKA = {"brak": ["", "у браку", "није у браку", "није утврђено"], "nastup": ["", "лично", "преко пуномоћника"],
           "potrebna_lica": [[], ["сведок"]], "strana": ["располаже", "стиче", "није одређено"]}


def _kombinacije(izbor):
    kljucevi = list(izbor)
    for vrednosti in itertools.product(*(izbor[k] for k in kljucevi)):
        yield {k: v for k, v in zip(kljucevi, vrednosti) if v not in ("", [])}


def test_primenljivost_ista_kao_u_savi():
    n = 0
    for odg in _kombinacije(ODGOVORI):
        for o in P.DEFINICIJA:
            for q in o.get("pitanja", []):
                assert L.primenljivost(o, q, odg, None, {}) == M.primenljivost(o, q, odg, None, {}), (q["k"], odg)
                n += 1
            for polja in _kombinacije(STRANKA):
                for q in o.get("po_stranci", []):
                    assert L.primenljivost(o, q, polja, odg, {}, "1") == M.primenljivost(o, q, polja, odg, {}, "1"), (q["k"], polja)
                    n += 1
    assert n > 10000


def test_oznake_utichu_isto():
    o, q = L.PO_STRANCI["vreme_sticanja"]
    for oz in (L.NIJE_PRIMENLJIVO, L.RADNJA):
        oznake = {"1.brak": oz}
        assert L.primenljivost(o, q, {}, {}, oznake, "1") == M.primenljivost(o, q, {}, {}, oznake, "1")


def test_statusi_odstupanje_i_kontrola_isti():
    for k, (o, q) in list(L.OPSTA.items()) + list(L.PO_STRANCI.items()):
        for v in [None, "", "да", "не", "ДА", "НЕ", "није утврђено", "потребна провера", *(q.get("o") or [])]:
            assert L.status_vrednosti(q, v) == M.status_vrednosti(q, v), (k, v)
            assert L.odstupa(k, v) == CL.odstupa(k, v) and L.odstupa(k, v, True) == CL.odstupa(k, v, True)
    for odg in _kombinacije({**ODGOVORI, "pranje_novca": ["", "ДА"], "dok_za_vracanje": ["", "ДА"]}):
        nasa, njihova = L.kontrola({"odgovori": odg}), CL.kontrola({"odgovori": odg})
        assert (nasa["crvene"], nasa["nedostaje"], nasa["spremno"]) == \
            (njihova["crvene"], njihova["nedostaje"], njihova["spremno"]), odg
        assert L.podrazumevano({}, odg, []) == CL.podrazumevano({}, odg, [])
