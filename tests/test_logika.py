"""Правила чек-листе: видљивост и применљивост, пет статуса, предлози, групна потврда, упозорења, КОНТРОЛА, парафи."""

from __future__ import annotations

import pytest

from ceklista import logika as L, pitanja as P

from .conftest import JELENA, PETAR


def stavka(c, oznaka):
    s = L.nadji(L.stanje(c), oznaka)
    assert s is not None, oznaka
    return s


# ---------------------------------------------------------------- применљивост

def test_cena_samo_za_prodaju_a_bez_posla_za_proveru():
    c = L.nova()
    assert stavka(c, "cena")["primenljivost"] == "nepoznato"  # посао није одређен: не крије се, за проверу
    assert "правни посао још није одређен" in stavka(c, "cena")["razlog"]
    L.postavi_posao(c, "поклон")
    assert stavka(c, "cena")["primenljivost"] == "ne"
    assert stavka(c, "motiv")["primenljivost"] == "da"
    L.postavi_posao(c, "продаја")
    assert stavka(c, "cena")["primenljivost"] == "da"
    assert stavka(c, "motiv")["primenljivost"] == "ne"


def test_pitanja_po_stranci_prate_brak_i_stranu(prodaja):
    c = prodaja
    assert stavka(c, "1.vreme_sticanja")["primenljivost"] == "ceka"  # брачни статус још без одговора
    L.odgovori(c, "1.brak", "у браку")
    assert stavka(c, "1.vreme_sticanja")["primenljivost"] == "da"
    assert stavka(c, "1.saglasnost_supruznika")["primenljivost"] == "da"  # продавац располаже
    L.odgovori(c, "2.brak", "у браку")
    assert stavka(c, "2.saglasnost_supruznika")["primenljivost"] == "ne"  # купац стиче
    assert stavka(c, "2.upis_sticaoca")["primenljivost"] == "da"
    L.odgovori(c, "1.brak", "није у браку")
    assert stavka(c, "1.vreme_sticanja")["primenljivost"] == "ne"


def test_stranka_bez_svojstva_vidi_obe_strane_za_proveru():
    c = L.nova(posao="продаја")
    L.dodaj_lice(c, PETAR)
    L.odgovori(c, "1.brak", "у браку")
    for k in ("saglasnost_supruznika", "upis_sticaoca"):
        s = stavka(c, f"1.{k}")
        assert s["primenljivost"] == "nepoznato" and "страна у послу" in s["razlog"]


def test_strana_iz_svojstva():
    assert L.strana({"svojstvo": "продавац"}) == "располаже"
    assert L.strana({"svojstvo": "купац"}) == "стиче"
    assert L.strana({"svojstvo": "уговарач"}) == "располаже и стиче"
    assert L.strana({"svojstvo": "продавац; купац"}) == "располаже и стиче"
    assert L.strana({"svojstvo": ""}) == P.NEODREDJENA


def test_odgovor_ostaje_kad_pitanje_prestane_da_vazi_i_vraca_se(prodaja):
    c = prodaja
    L.odgovori(c, "cena", "85.000")
    L.postavi_posao(c, "поклон")
    assert stavka(c, "cena")["primenljivost"] == "ne"
    L.postavi_posao(c, "продаја")
    assert stavka(c, "cena")["vrednost"] == "85.000"


# ---------------------------------------------------------------- пет статуса

def test_pet_statusa(prodaja):
    c = prodaja
    assert stavka(c, "dok_kompletna")["status"] == L.NIJE_PROVERENO  # празно никад није „да“ ни „не“
    L.odgovori(c, "dok_kompletna", "да")
    assert stavka(c, "dok_kompletna")["status"] == L.DA
    L.odgovori(c, "dok_kompletna", "не")
    assert stavka(c, "dok_kompletna")["status"] == L.NE
    L.odgovori(c, "cena", "85.000")
    assert stavka(c, "cena")["status"] == L.DA  # унет податак
    L.odgovori(c, "dok_kompletna", oznaka=L.NIJE_PRIMENLJIVO)
    s = stavka(c, "dok_kompletna")
    assert s["status"] == L.NIJE_PRIMENLJIVO and s["vrednost"] is None and "dok_kompletna" not in c["odgovori"]
    L.odgovori(c, "dok_kompletna", oznaka=L.RADNJA)
    L.odgovori(c, "dok_kompletna", napomena="тражити извод из катастра")
    s = stavka(c, "dok_kompletna")
    assert s["status"] == L.RADNJA and s["napomena"] == "тражити извод из катастра"
    L.odgovori(c, "dok_kompletna", oznaka="")
    assert stavka(c, "dok_kompletna")["status"] == L.NIJE_PROVERENO
    L.odgovori(c, "dok_kompletna", "да")
    L.odgovori(c, "dok_kompletna", None)
    assert stavka(c, "dok_kompletna")["status"] == L.NIJE_PROVERENO


def test_kucica_neoznacena_ne_vazi_i_ne_broji_se(prodaja):
    c = prodaja
    s = stavka(c, "ne_dostavlja")
    assert s["status"] == L.NE  # одговор бележника 14: неозначена кућица — „не важи“
    pre = L.stanje(c)["brojaci"][L.NE]
    L.odgovori(c, "ne_dostavlja", "да")
    st = L.stanje(c)
    assert L.nadji(st, "ne_dostavlja")["status"] == L.DA and st["brojaci"][L.NE] == pre


def test_nesigurni_odgovori_nisu_odgovor(prodaja):
    with pytest.raises(L.GreskaUnosa, match="Потребна радња"):
        L.odgovori(prodaja, "dok_kompletna", "није утврђено")
    assert "није утврђено" not in L.opcije(L.OPSTA["dok_kompletna"][1])


@pytest.mark.parametrize("oznaka,vrednost,poruka", [
    ("cena", "много", "износ бројем"),
    ("cena", "-5", "износ бројем"),
    ("valuta", "динар", "непознат одговор"),
    ("termin", "сутра", "датум и време"),
    ("termin", "31.02.2026 10:00", "не постоји"),
    ("1.supruznik_lice", "1", "странку са списка"),  # не може сам себи супружник
    ("ne_dostavlja", "не", "само означава"),
    ("prenos_obuhvata", ["кућа"], "непознат избор"),
])
def test_pogresan_unos_se_odbija_i_nista_ne_upisuje(prodaja, oznaka, vrednost, poruka):
    c = prodaja
    if oznaka == "prenos_obuhvata":
        L.postavi_posao(c, "доживотно издржавање")
    pre = repr(c["odgovori"]) + repr(c["stranke"])
    with pytest.raises(L.GreskaUnosa, match=poruka):
        L.odgovori(c, oznaka, vrednost)
    assert repr(c["odgovori"]) + repr(c["stranke"]) == pre


@pytest.mark.parametrize("unos", ["26.11.2026 14:30", "26.11.2026. у 14.30", "2026-11-26T14:30", "26. 11. 2026, 14:30"])
def test_termin(unos, prodaja):
    L.odgovori(prodaja, "termin", unos)
    s = stavka(prodaja, "termin")
    assert s["vrednost"] == "2026-11-26T14:30" and s["prikaz"] == "26.11.2026. у 14:30"


def test_supruznik_je_druga_stranka(prodaja):
    L.odgovori(prodaja, "1.brak", "у браку")
    L.odgovori(prodaja, "1.supruznik_lice", "2")
    assert stavka(prodaja, "1.supruznik_lice")["prikaz"] == JELENA


# ---------------------------------------------------------------- предлози и групна потврда

def test_predlog_nije_odgovor_dok_se_ne_prihvati(prodaja):
    c = prodaja
    s = stavka(c, "cena_isplacena")
    assert s["predlog"]["v"] == "да" and s["status"] == L.NIJE_PROVERENO and "cena_isplacena" not in c["odgovori"]
    assert "продаја" in s["predlog"]["osnov"] or "лев" in s["predlog"]["osnov"]
    L.odgovori(c, "cena_isplacena", prihvati=True)
    s = stavka(c, "cena_isplacena")
    assert s["status"] == L.DA and s["predlog"] is None
    assert c["trag"]["cena_isplacena"]["nacin"] == "pojedinacno"
    assert c["trag"]["cena_isplacena"]["poreklo"] == "podrazumevano"


def test_licne_karte_se_ne_predlazu_bez_podataka_isprava(prodaja):
    """Сава „да“ предлаже само кад су исправе свих лица уписане; програм их не види."""
    assert stavka(prodaja, "lk_ugovaraca")["predlog"] is None


def test_pravno_lice_predlaze_firmu():
    c = L.nova(posao="продаја")
    L.dodaj_lice(c, "ПРОБА ДОО", "купац", pravno_lice=True)
    s = stavka(c, "firma_ucesnik")
    assert s["predlog"]["v"] == "да" and s["predlog"]["poreklo"] == "uneto"


def test_punomocnik_na_listu_prati_odgovor_po_stranci(prodaja):
    assert stavka(prodaja, "k_punomocnik")["predlog"]["v"] == "НЕ"
    L.odgovori(prodaja, "2.nastup", "преко пуномоћника")
    p = stavka(prodaja, "k_punomocnik")["predlog"]
    assert p["v"] == "ДА" and p["poreklo"] == "uneto"


def test_grupna_potvrda_samo_vidjenog_spiska(prodaja):
    c = prodaja
    spisak = L.stanje(c)["grupna"]
    assert spisak and all(x["v"] for x in spisak)
    with pytest.raises(L.SpisakSePromenio):
        L.grupna_potvrda(c, None)  # без виђеног списка — ништа
    L.odgovori(c, "2.nastup", "преко пуномоћника")  # мења предлог „заступа пуномоћник“
    with pytest.raises(L.SpisakSePromenio) as e:
        L.grupna_potvrda(c, [{"k": x["k"], "v": x["v"]} for x in spisak])
    assert any(x["k"] == "k_punomocnik" and x["v"] == "ДА" for x in e.value.spisak)
    assert "k_punomocnik" not in c["odgovori"]  # ништа није уписано
    n = L.grupna_potvrda(c, e.value.spisak)
    assert n == len(e.value.spisak)
    assert c["odgovori"]["k_punomocnik"] == "ДА" and c["trag"]["k_punomocnik"]["nacin"] == "grupno"
    assert L.stanje(c)["grupna"] == []
    assert stavka(c, "dok_kompletna")["status"] == L.NIJE_PROVERENO  # питање без предлога остаје


# ---------------------------------------------------------------- упозорења и КОНТРОЛА

def poruke(c, vrsta=None):
    return [u["poruka"] for u in L.provera(c) if vrsta is None or u["vrsta"] == vrsta]


def test_posledica_i_crvena_zastavica(prodaja):
    c = prodaja
    L.odgovori(c, "cena_ok", "НЕ")
    s = stavka(c, "cena_ok")
    assert "одбија се овера" in s["uticaj"]
    assert any("цена / мотив" in x["poruka"] for x in L.kontrola(c)["crvene"])
    L.odgovori(c, "pranje_novca", "ДА")
    assert len(L.kontrola(c)["crvene"]) == 2


def test_doslednost_cene(prodaja):
    c = prodaja
    for k, v in (("cena", "100.000"), ("cena_isplacena", "не"), ("isplaceno", "50.000"), ("preostalo", "40.000")):
        L.odgovori(c, k, v)
    assert any("не дају цену" in x for x in poruke(c, "doslednost"))
    L.odgovori(c, "preostalo", "50.000")
    assert not any("не дају цену" in x for x in poruke(c, "doslednost"))


def test_napomena_uz_odstupanje(prodaja):
    L.odgovori(prodaja, "posed_predat", "не")
    assert any("Посед предат" in x and "напомену" in x for x in poruke(prodaja, "napomena"))
    L.odgovori(prodaja, "posed_predat", napomena="посед по исплати")
    assert not any("Посед предат" in x for x in poruke(prodaja, "napomena"))


def test_forma_koja_za_posao_ne_postoji():
    c = L.nova(posao="завештање")
    L.odgovori(c, "forma", "солемнизација")
    assert any("не сачињава као солемнизација" in x for x in poruke(c, "doslednost"))


def test_svedok_kad_stranka_ne_cita(prodaja):
    L.odgovori(prodaja, "1.cita", "не")
    assert any(PETAR in x and "сведок" in x for x in poruke(prodaja))
    L.odgovori(prodaja, "1.potrebna_lica", ["сведок"])
    assert not any(PETAR in x and "сведок није" in x for x in poruke(prodaja))


def test_kontrola_spremno_kad_je_list_odgovoren(prodaja):
    c = prodaja
    assert not L.kontrola(c)["spremno"]
    L.grupna_potvrda(c, L.stanje(c)["grupna"])
    L.odgovori(c, "lk_ugovaraca", "да")
    L.odgovori(c, "forma", "солемнизација")  # без „Имамо број парцеле“ (само за запис)
    k = L.kontrola(c)
    assert k["spremno"], k


# ---------------------------------------------------------------- провера непокретности

def test_provera_nepokretnosti():
    c = L.nova(posao="закуп")
    assert L.nadji(L.stanje(c), "nep_imaoci") is None  # закупом се не располаже
    L.postavi_posao(c, "продаја")
    s = stavka(c, "nep_imaoci")
    assert s["primenljivost"] == "nepoznato" and "катастра" in s["razlog"] and s["predlog"] is None
    L.odgovori(c, "nep_imaoci", "да")
    assert stavka(c, "nep_imaoci")["status"] == L.DA and c["modul"]["nep_imaoci"] == L.DA
    L.odgovori(c, "nep_prece_pravo", oznaka=L.NIJE_PRIMENLJIVO)
    assert stavka(c, "nep_prece_pravo")["status"] == L.NIJE_PRIMENLJIVO


# ---------------------------------------------------------------- парафи и стање

def test_paraf_trazi_ime_i_ne_ponistava_se(prodaja):
    c = prodaja
    with pytest.raises(L.GreskaUnosa, match="Попунио"):
        L.potvrdi(c, "citao")
    L.postavi_popunio(c, "Мила")
    prvi = L.potvrdi(c, "citao")
    L.postavi_popunio(c, "Јана")
    assert L.potvrdi(c, "citao") == prvi and prvi["ime"] == "Мила"


def test_paraf_spremno_samo_kad_kontrola_prolazi(prodaja):
    c = prodaja
    L.postavi_popunio(c, "Мила")
    with pytest.raises(L.GreskaUnosa, match="не може на читање"):
        L.potvrdi(c, "spremno")
    assert "spremno" not in c["potvrde"]


def test_paraf_primio_potvrdjuje_vidjeni_spisak(prodaja):
    c = prodaja
    L.postavi_popunio(c, "Мила")
    with pytest.raises(L.SpisakSePromenio):
        L.potvrdi(c, "primio", None)
    assert "primio" not in c["potvrde"]
    L.potvrdi(c, "primio", L.stanje(c)["grupna"])
    assert c["potvrde"]["primio"]["ime"] == "Мила" and c["odgovori"]["cena_ok"] == "ДА"
    assert L.stanje(c)["grupna"] == []  # после парафа ништа се више не нуди


def test_paraf_spakovan_kad_spisi_nisu_slozeni(prodaja):
    L.postavi_popunio(prodaja, "Мила")
    L.odgovori(prodaja, "spisi_slozeni", "не")
    with pytest.raises(L.GreskaUnosa, match="сложени"):
        L.potvrdi(prodaja, "spakovan")


def test_zavrsena_je_samo_za_citanje(prodaja):
    c = prodaja
    L.zavrsi(c)
    for radnja in (lambda: L.odgovori(c, "cena", "1"), lambda: L.dodaj_lice(c, "НОВО ЛИЦЕ"),
                   lambda: L.postavi_posao(c, "поклон"), lambda: L.grupna_potvrda(c, [])):
        with pytest.raises(L.GreskaUnosa, match="завршена"):
            radnja()
    assert L.stanje(c)["samo_citanje"]
    L.vrati_u_rad(c)
    L.odgovori(c, "cena", "1")


def test_uklanjanje_stranke_brise_njene_odgovore_i_veze(prodaja):
    c = prodaja
    L.odgovori(c, "1.brak", "у браку")
    L.odgovori(c, "1.supruznik_lice", "2")
    L.odgovori(c, "2.nastup", oznaka=L.RADNJA)
    L.ukloni_lice(c, "2")
    assert "2" not in c["stranke"] and "supruznik_lice" not in c["stranke"]["1"]
    assert not any(k.startswith("2.") for k in c["oznake"])
    assert L.dodaj_lice(c, "НОВО ЛИЦЕ")["id"] == "2"


def test_nepoznat_posao(prodaja):
    with pytest.raises(L.GreskaUnosa):
        L.postavi_posao(prodaja, "крађа")
    L.postavi_posao(prodaja, L.NEODREDJEN)
    assert "posao" not in prodaja["odgovori"]


def test_sva_pitanja_iz_save_su_u_programu():
    st = L.stanje(L.nova())
    kljucevi = {s["k"] for s in st["sve"]}
    opsta = {q["k"] for o in P.DEFINICIJA for q in o.get("pitanja", [])}
    assert opsta <= kljucevi and set(P.PROVERE_NEPOKRETNOSTI) <= kljucevi
    assert sum(len(o.get("pitanja", [])) + len(o.get("po_stranci", [])) for o in P.DEFINICIJA) == 95


# ---------------------------------------------------------------- лист 23.1 (налог 27.11.2026)

def test_stavke_lista_23(prodaja):
    """Ставке листа 23.1 којих у Сави нема су питања као и остала: кућица, линија, избор; без услова приказа."""
    c = prodaja
    for k, v in (("primljeno", "27.11.2026 09:30"), ("kontakt", "ПЕТАР ПЕТРОВИЋ"),
                 ("kupac_prihvata_rizik", "да"), ("kupac_prvi_stan", "не"), ("sacinio_list", "ми")):
        L.odgovori(c, k, v)
    assert c["odgovori"]["primljeno"] == "2026-11-27T09:30"
    assert stavka(c, "kupac_prihvata_rizik")["status"] == L.DA and stavka(c, "susvojina_pola")["status"] == L.NE
    assert stavka(c, "sacinio_list")["primenljivost"] == "da"
    with pytest.raises(L.GreskaUnosa):
        L.odgovori(c, "sacinio_list", "нотар")


def test_dato_uputstvo_uklonjeno():
    """Налог 27.11.2026: „Дато им кратко упутство“ се избацује — нема питања ни предлога."""
    assert "dato_uputstvo" not in L.OPSTA
    assert not any(x["k"] == "dato_uputstvo" for x in L.stanje(L.nov_list())["grupna"])


def test_kontrola_ista_kao_sava_i_sa_listom_23(prodaja):
    """Нова ставка листа не мења КОНТРОЛУ из Саве (спремно за читање)."""
    L.grupna_potvrda(prodaja, L.stanje(prodaja)["grupna"])
    L.odgovori(prodaja, "lk_ugovaraca", "да")
    L.odgovori(prodaja, "forma", "солемнизација")
    assert L.kontrola(prodaja)["spremno"]


def test_poreske_prijave_uklonjene():
    """Налог 27.11.2026: ставка „Дате су им пор. пријаве да попуне“ се брише са листа."""
    assert "poreske_prijave" not in L.OPSTA
    with pytest.raises(L.GreskaUnosa):
        L.odgovori(L.nova(), "poreske_prijave", "да")


def test_nov_list_unapred_oznaceno():
    """Налог 27.11.2026: исплата цене „Да“, посед „Да“, порез „Купац“ су на новом листу унапред означени — као
    одговори (мењају се кликом), са трагом „унапред означено“; за посао који није продаја не важе."""
    c = L.nov_list()
    assert c["odgovori"] == {"cena_isplacena": "да", "posed_predat": "да", "porez_snosi": "купац", "posao": "продаја", "valuta": "EUR",
                               "dok_za_vracanje": "НЕ", "sacinio_list": "ми"}
    assert c["trag"]["porez_snosi"]["nacin"] == "predefinisano" and "posao" not in c["trag"]
    assert stavka(c, "dok_za_vracanje")["status"] == L.NE and stavka(c, "valuta")["prikaz"] == "EUR"
    assert stavka(c, "cena_isplacena")["status"] == L.DA and stavka(c, "porez_snosi")["predlog"] is None
    assert not any(x["k"] in c["odgovori"] for x in L.stanje(c)["grupna"])
    L.odgovori(c, "posed_predat", "не")
    assert c["odgovori"]["posed_predat"] == "не"
    L.postavi_posao(c, "поклон")
    assert stavka(c, "cena_isplacena")["primenljivost"] == "ne"


def test_parafi_ponistavanje(prodaja):
    """Налог 27.11.2026: параф без питања — поновни клик поништава (ponisti_potvrdu)."""
    L.postavi_popunio(prodaja, "Мила")
    L.potvrdi(prodaja, "citao")
    L.ponisti_potvrdu(prodaja, "citao")
    assert "citao" not in prodaja["potvrde"]
    L.ponisti_potvrdu(prodaja, "citao")  # већ поништен — ништа
    with pytest.raises(L.GreskaUnosa):
        L.ponisti_potvrdu(prodaja, "nepoznat")
    L.potvrdi(prodaja, "citao")
    L.zavrsi(prodaja)
    with pytest.raises(L.GreskaUnosa, match="завршена"):
        L.ponisti_potvrdu(prodaja, "citao")


def test_list_23_prati_pravni_posao():
    """Налог 27.11.2026 (динамичан лист): ставке листа 23.1 о супружницима важе за послове којима се располаже
    непокретношћу, „Купац првог стана“ само за продају — као сродна питања у Сави."""
    c = L.nov_list()
    for posao, vazi, ne_vazi in (
            ("продаја", {"kupac_prvi_stan", "prodavac_nije_u_braku", "nasledio"}, set()),
            ("поклон", {"prodavac_nije_u_braku", "nasledio", "motiv"},
             {"kupac_prvi_stan", "cena", "sup_kupca_dolazi", "kupac_nije_u_braku", "susvojina_pola"}),
            ("доживотно издржавање", {"sup_prodavca_dolazi", "dom_iskljucen"},
             {"nasledio", "oba_supruznika", "kupac_prvi_stan", "sup_kupca_dolazi"}),
            ("уступање и расподела", {"prodavac_nije_u_braku"}, {"sup_kupca_dolazi", "kupac_nije_u_braku"}),
            ("завештање", set(), {"prodavac_nije_u_braku", "susvojina_pola", "kupac_prvi_stan", "nasledio"})):
        L.postavi_posao(c, posao)
        for k in vazi:
            assert stavka(c, k)["primenljivost"] == "da", (posao, k)
        for k in ne_vazi:
            assert stavka(c, k)["primenljivost"] == "ne", (posao, k)
    L.postavi_posao(c, "")
    assert stavka(c, "susvojina_pola")["primenljivost"] == "nepoznato"  # посао није одређен: за проверу
