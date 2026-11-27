"""Сажетак: само изабрани подаци, по целинама и странкама; КОНТРОЛА, радње и непроверено."""

from __future__ import annotations

from ceklista import logika as L, sazetak as S

from .conftest import JELENA, PETAR


def popuni(c):
    L.postavi_popunio(c, "Мила")
    L.odgovori(c, "forma", "јавнобележнички запис")
    L.odgovori(c, "cena", "85.000")
    L.odgovori(c, "1.brak", "у браку")
    L.odgovori(c, "2.brak", "није у браку")
    L.odgovori(c, "2.nastup", oznaka=L.RADNJA)
    L.odgovori(c, "2.nastup", napomena="прибавити оверено пуномоћје")
    L.odgovori(c, "zabelezba", oznaka=L.NIJE_PRIMENLJIVO)
    return c


def test_samo_izabrani_podaci_po_strankama(prodaja):
    s = S.sazetak(popuni(prodaja))
    t = S.kao_tekst(s)
    assert "Предмет: ОПУ 12/2026" in t and "Правни посао: продаја" in t and "Попунио/ла: Мила" in t
    assert f"{PETAR} — продавац (располаже)" in t and f"{JELENA} — купац (стиче)" in t
    assert "Врста исправе: јавнобележнички запис" in t and "Купопродајна цена: 85.000" in t
    b = next(o for o in s["odeljci"] if o["naslov"].startswith("Б."))
    assert [x["ime"] for x in b["po_licima"]] == [PETAR, JELENA]
    assert b["po_licima"][0]["redovi"][0]["odgovor"] == "у браку"
    sve = [r["pitanje"] for o in s["odeljci"] for r in o["redovi"] + [y for x in o["po_licima"] for y in x["redovi"]]]
    assert "Достављено" not in sve  # без одговора — није изабрано
    assert "Странке захтевају да нотар не доставља" not in sve  # неозначена кућица није избор


def test_radnja_nije_primenljivo_i_neprovereno(prodaja):
    s = S.sazetak(popuni(prodaja))
    assert {"pitanje": f"Наступа ({JELENA})", "sta": "прибавити оверено пуномоћје"} in s["radnje"]
    assert "Забележба уговора" in s["oznaceno_np"]
    grupe = {(g["odeljak"][:2], g["stranka"]): g["pitanja"] for g in s["neprovereno"]}
    assert "Цена у целости исплаћена (обавезно)" in grupe[("В.", "")]
    assert "Основ стицања имовине" in grupe[("Б.", PETAR)]
    t = S.kao_tekst(s)
    assert "ПОТРЕБНА РАДЊА (1)" in t and "НИЈЕ ПРОВЕРЕНО (" in t


def test_kontrola_u_sazetku(prodaja):
    c = popuni(prodaja)
    L.odgovori(c, "pranje_novca", "ДА")
    L.odgovori(c, "pranje_novca", napomena="поверљива напомена о странци")
    t = S.kao_tekst(S.sazetak(c))
    assert "Црвена заставица: сумња у вези прања новца" in t
    assert "Спремно за читање: не" in t
    assert "поверљива напомена" not in t  # напомена о сумњи у прање новца не иде у сажетак
    assert "Постоји сумња у прање новца или финансирање тероризма?: ДА" in t


def test_posledice_i_word(prodaja):
    L.odgovori(prodaja, "cena_isplacena", "не")
    s = S.sazetak(prodaja)
    assert any("ручна измена у Word-у" in x for x in s["upozorenja"]["word"])
    assert any("Цена у целости исплаћена" in x for x in s["upozorenja"]["nedostaje"])


def test_prazna_cek_lista():
    t = S.kao_tekst(S.sazetak(L.nova()))
    assert "Странке нису унете." in t and "Још ниједно питање нема одговор." in t
    assert "Правни посао: још није одређен" in t


def test_zavrsena_u_zaglavlju(prodaja):
    L.zavrsi(prodaja)
    assert "Стање: завршена (" in S.kao_tekst(S.sazetak(prodaja))


def test_grupno_potvrdjeni_predlozi_su_u_sazetku(prodaja):
    L.grupna_potvrda(prodaja, L.stanje(prodaja)["grupna"])
    t = S.kao_tekst(S.sazetak(prodaja))
    assert "Цена у целости исплаћена: да" in t and "Место овере: канцеларија" in t


def test_lista_23_u_sazetku():
    c = L.nova()
    L.postavi_posao(c, "друго")
    for k, v in (("posao_drugo", "уговор о грађењу"), ("kupac_prihvata_rizik", "да"), ("telefon", "060 000 000")):
        L.odgovori(c, k, v)
    t = S.kao_tekst(S.sazetak(c))
    assert "Правни посао: друго (уговор о грађењу)" in t
    assert "ЛИСТ 23.1 — ОСТАЛЕ СТАВКЕ" in t and "Купац прихвата ризик: важи" in t and "Телефон: 060 000 000" in t
    assert "Купац није у браку" not in t.split("НИЈЕ ПРОВЕРЕНО")[0]  # неозначена кућица није избор


def test_unapred_oznaceno_u_sazetku_samo_za_prodaju():
    c = L.nov_list()
    L.postavi_posao(c, "поклон")
    assert "Посед предат" not in S.kao_tekst(S.sazetak(c))
    L.postavi_posao(c, "продаја")
    t = S.kao_tekst(S.sazetak(c))
    assert "Посед предат: да" in t and "Порез на пренос апсолутних права сноси (договор странака): купац" in t
