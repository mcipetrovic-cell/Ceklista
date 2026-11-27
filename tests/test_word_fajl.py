"""Word документ сажетка (без спољних библиотека) и датотека чек-листе (.ceklista)."""

from __future__ import annotations

import json
import shutil
import subprocess
import zipfile
from xml.etree import ElementTree

import pytest

from ceklista import fajl, logika as L, sazetak as S, word

from .conftest import JELENA, PETAR


# ---------------------------------------------------------------- Word

def test_docx_je_ispravan_i_sadrzi_sazetak(prodaja, tmp_path):
    L.dodaj_lice(prodaja, 'ПРОБА <ДОО> & „СИН“', "купац", pravno_lice=True)  # знакови које XML мора да избегне
    L.odgovori(prodaja, "cena", "85.000")
    p = word.sacuvaj(S.sazetak(prodaja), tmp_path / "sazetak.docx")
    with zipfile.ZipFile(p) as z:
        assert z.testzip() is None
        imena = set(z.namelist())
        assert {"[Content_Types].xml", "_rels/.rels", "word/document.xml", "word/styles.xml",
                "word/_rels/document.xml.rels"} <= imena
        for ime in imena:
            if ime.endswith((".xml", ".rels")):
                ElementTree.fromstring(z.read(ime))  # исправан XML
        tekst = "".join(ElementTree.fromstring(z.read("word/document.xml")).itertext())
    assert PETAR in tekst and "Купопродајна цена: 85.000" in tekst and 'ПРОБА <ДОО> & „СИН“' in tekst


@pytest.mark.skipif(not shutil.which("soffice"), reason="LibreOffice није инсталиран")
def test_docx_otvara_kancelarijski_program(prodaja, tmp_path):
    p = word.sacuvaj(S.sazetak(prodaja), tmp_path / "sazetak.docx")
    subprocess.run(["soffice", "--headless", "--convert-to", "txt:Text (encoded):UTF8", "--outdir", str(tmp_path), str(p)],
                   check=True, capture_output=True, timeout=120)
    tekst = (tmp_path / "sazetak.txt").read_text(encoding="utf-8-sig")
    assert "ЧЕК-ЛИСТА — САЖЕТАК" in tekst and PETAR in tekst


def test_docx_python_docx(prodaja, tmp_path):
    docx = pytest.importorskip("docx")
    p = word.sacuvaj(S.sazetak(prodaja), tmp_path / "sazetak.docx")
    d = docx.Document(str(p))
    assert d.paragraphs[0].style.name == "Title"
    assert any(x.style.name == "Heading 1" and x.text == "Странке" for x in d.paragraphs)


# ---------------------------------------------------------------- датотека чек-листе

def test_cuvanje_i_ucitavanje(prodaja, tmp_path):
    L.odgovori(prodaja, "1.brak", "у браку")
    L.odgovori(prodaja, "zabelezba", oznaka=L.RADNJA)
    p = fajl.sacuvaj(prodaja, tmp_path / "a.ceklista")
    c = fajl.ucitaj(p)
    assert c["odgovori"] == prodaja["odgovori"] and c["stranke"] == prodaja["stranke"]
    assert c["lica"] == prodaja["lica"] and c["oznake"] == prodaja["oznake"]
    assert S.kao_tekst(S.sazetak(c)) == S.kao_tekst(S.sazetak(prodaja))
    assert [x.name for x in tmp_path.iterdir()] == ["a.ceklista"]  # без заосталих привремених датотека


def test_novo_ime_bezbedno_i_jedinstveno(prodaja):
    L.postavi_naziv(prodaja, 'ОПУ 12/2026: "Петровић"')
    a = fajl.novo_ime(prodaja)
    assert a.parent == fajl.fascikla() and a.suffix == ".ceklista"
    assert "/" not in a.name.replace(".ceklista", "") and ":" not in a.name and '"' not in a.name
    fajl.sacuvaj(prodaja, a)
    assert fajl.novo_ime(prodaja) != a


@pytest.mark.parametrize("sadrzaj,poruka", [
    (b"{nije json", "оштећена"),
    (json.dumps({"format": "drugo"}).encode(), "није датотека чек-листе"),
    (json.dumps({"format": "ceklista", "verzija_formata": 99}).encode(), "новијом верзијом"),
    (b"\xff\xfe\x00", "оштећена"),
])
def test_losa_datoteka(tmp_path, sadrzaj, poruka):
    p = tmp_path / "x.ceklista"
    p.write_bytes(sadrzaj)
    with pytest.raises(L.GreskaUnosa, match=poruka):
        fajl.ucitaj(p)


def test_sredjivanje_procitanog(tmp_path):
    d = {"format": "ceklista", "verzija_formata": 1, "stanje": "nesto", "lica": [{"id": "1", "ime": "А"}, {"ime": "без броја"},
         {"id": "2.3", "ime": "тачка"}], "oznake": {"cena": "lose", "valuta": "potrebna_radnja"}, "odgovori": []}
    p = tmp_path / "x.ceklista"
    p.write_text(json.dumps(d), encoding="utf-8")
    c = fajl.ucitaj(p)
    assert c["stanje"] == "u_radu" and [x["id"] for x in c["lica"]] == ["1"]
    assert c["oznake"] == {"valuta": "potrebna_radnja"} and c["odgovori"] == {}
    L.stanje(c)  # прочитана чек-листа се приказује


def test_spisak_zapocetih(prodaja, tmp_path):
    """Почетни екран: чек-листе из фасцикле, новије прве, по стању; оштећена датотека се прескаче."""
    assert fajl.spisak() == []
    a = fajl.sacuvaj(prodaja, fajl.novo_ime(prodaja))
    druga = L.nova("ОПУ 13/2026", "поклон")
    L.dodaj_lice(druga, JELENA, "поклонопримац")
    L.zavrsi(druga)
    b = fajl.sacuvaj(druga, fajl.fascikla() / "b.ceklista")
    (fajl.fascikla() / "losa.ceklista").write_text("{", encoding="utf-8")
    u_radu = fajl.spisak()
    assert [x["putanja"] for x in u_radu] == [a]
    x = u_radu[0]
    assert x["naziv"] == "ОПУ 12/2026" and x["stranke"] == [PETAR, JELENA] and x["posao"] == "продаја"
    assert x["stanje_naziv"] == "у раду"
    assert [x["putanja"] for x in fajl.spisak("zavrsena")] == [b]
    assert {x["putanja"] for x in fajl.spisak("sve")} == {a, b}
    assert fajl.spisak("sve")[0]["putanja"] == b  # новија прва


def test_otvorena_cek_lista(prodaja):
    """Ознака отворене чек-листе: наставак при новом покретању само за постојећу чек-листу у раду."""
    assert fajl.otvorena() is None
    p = fajl.sacuvaj(prodaja, fajl.novo_ime(prodaja))
    fajl.zapamti_otvorenu(p)
    assert fajl.otvorena() == p.resolve()
    assert fajl.spisak() and len(fajl.spisak()) == 1  # ознака није чек-листа
    L.zavrsi(prodaja)
    fajl.sacuvaj(prodaja, p)
    assert fajl.otvorena() is None  # завршена се не наставља сама
    L.vrati_u_rad(prodaja)
    fajl.sacuvaj(prodaja, p)
    assert fajl.otvorena() == p.resolve()
    p.unlink()
    assert fajl.otvorena() is None  # обрисана
    fajl.zapamti_otvorenu(None)
    assert not (fajl.fascikla() / fajl.OTVORENA).exists()
