"""Прозор (прави Tk; на Linux-у под Xvfb): лист 23.1 као почетак, унос странака, одговор кликом, поља за текст, групна потврда, точкић
миша изнад падајућег списка, сажетак, Word, ново покретање. Поруке (messagebox) се бележе уместо да чекају клик."""

from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk

import pytest

from ceklista import fajl, gui, logika as L

from .conftest import JELENA, PETAR, ima_ekran

pytestmark = pytest.mark.skipif(not ima_ekran(), reason="нема екрана (на Linux-у: xvfb-run)")


@pytest.fixture
def poruke(monkeypatch):
    zapis = []
    for ime in ("showwarning", "showerror", "showinfo"):
        monkeypatch.setattr(gui.messagebox, ime, lambda naslov, poruka, **kw: zapis.append(poruka))
    monkeypatch.setattr(gui.messagebox, "askyesno", lambda naslov, poruka, **kw: zapis.append(poruka) or True)
    monkeypatch.setattr(gui, "otvori_spolja", lambda p: zapis.append(f"отворено: {p}"))
    return zapis


def novi_tk() -> tk.Tk:
    """Tk на Windows машини GitHub-а повремено не нађе своје датотеке при поновљеном покретању („Can't find a usable
    tk.tcl“, 27.11.2026) — то није грешка програма; проба покушава поново."""
    for pokusaj in range(5):
        try:
            return tk.Tk()
        except tk.TclError:
            if pokusaj == 4:
                raise
            time.sleep(1 + pokusaj)


@pytest.fixture
def koren():
    k = novi_tk()
    k.geometry("1280x800+0+0")
    yield k
    try:
        k.destroy()
    except tk.TclError:
        pass


def svi(w):
    for x in w.winfo_children():
        yield x
        yield from svi(x)


def dugme(koren, klasa, tekst, n=0):
    nadjeni = [w for w in svi(koren) if isinstance(w, klasa) and str(w.cget("text")) == tekst]
    assert len(nadjeni) > n, (tekst, len(nadjeni))
    return nadjeni[n]


def polje_za(app, oznaka):
    """Поље за унос текста уз питање."""
    return app._polja[oznaka]


def klikni(koren, w):
    """Клик мишем на део листа: страна се прво помери до њега (ван видљивог дела платна Tk га не приказује)."""
    app_platno = next(x for x in svi(koren) if isinstance(x, tk.Canvas) and x.winfo_ismapped())
    unutra = app_platno.nametowidget(app_platno.itemcget(app_platno.find_all()[0], "window"))
    y = w.winfo_rooty() - unutra.winfo_rooty()
    app_platno.yview_moveto(max(0.0, (y - 150) / max(1, unutra.winfo_height())))
    koren.update()
    w.event_generate("<Button-1>")
    koren.update()


def klik(koren, natpis, n=0):
    """Клик на кућицу, ћелију или „парафирај“ на листу (натпис као на папиру)."""
    nadjeni = [w for w in svi(koren) if isinstance(w, tk.Label) and str(w.cget("text")) == natpis]
    assert len(nadjeni) > n, (natpis, len(nadjeni))
    klikni(koren, nadjeni[n])


def kucica(koren, natpis, n=0) -> str:
    """☑ или ☐ поред натписа на листу."""
    w = [w for w in svi(koren) if isinstance(w, tk.Label) and str(w.cget("text")) == natpis][n]
    return w.master.kucica.cget("text")


def zapocni(koren, posao="Продаја"):
    """Као корисник: програм почиње празним листом 23.1; правни посао кликом на листу."""
    app = gui.Aplikacija(koren)
    koren.update()
    assert app.rad.winfo_ismapped() and app.izbor == gui.LIST and not app.ulaz.platno.winfo_ismapped()
    if posao and posao != "Продаја":  # продаја је унапред означена (налог 27.11.2026)
        klik(koren, posao)
    return app


def sa_strankama(koren):
    app = zapocni(koren)
    app.radi(L.dodaj_lice, app.c, PETAR, "продавац")
    app.radi(L.dodaj_lice, app.c, JELENA, "купац")
    koren.update()
    return app


def test_pocetak_je_prazan_list(koren, poruke):
    """Верзија 1.1 (налог 27.11.2026): програм почиње празним листом „Чек листа 23.1“ (као на папиру) — једини улаз у
    чек-листу предмета; без менија „Датотека“. Верзија 1.2 (налог 27.11.2026): исплата цене „Да“, посед „Да“ и порез
    „Купац“ су унапред означени; чек-листа која није била отворена при затварању се не отвара сама."""
    c = L.nova("ОПУ 12/2026", "продаја")
    L.dodaj_lice(c, PETAR, "продавац")
    fajl.sacuvaj(c, fajl.novo_ime(c))  # сачувана, али није била отворена у програму
    app = gui.Aplikacija(koren)
    koren.update()
    assert app.izbor == gui.LIST and app.putanja is None and app.c["lica"] == []
    assert app.c["odgovori"] == {"cena_isplacena": "да", "posed_predat": "да", "porez_snosi": "купац", "posao": "продаја", "valuta": "EUR",
                               "dok_za_vracanje": "НЕ", "sacinio_list": "ми"}
    assert "још није сачувана" in app.l_stanje.cget("text")
    assert not app.levo.winfo_ismapped() and str(koren.cget("menu")) == ""
    assert app._papir.winfo_ismapped()
    for natpis in ("Лично", "Мејлом", "Запис", "Солемнизација", "Поклон", "Имамо ЛК уговарача и супружника",
                   "Купац прихвата ризик", "Стичу сусвојину са уделима од по 1/2"):
        assert kucica(koren, natpis) == "☐"
    assert kucica(koren, "Продаја") == "☑"  # унапред означено (налог 27.11.2026)
    # налог 27.11.2026 („избаците ове делове“): парафи десно, „Нема документације…“, „Ко је сачинио исправу“ и
    # „Важно!!!“ нису на листу; унапред означени одговори остају у чек-листи (мењају се у детаљним целинама)
    natpisi = {str(w.cget("text")) for w in svi(koren) if isinstance(w, tk.Label)}
    for uklonjeno in ("парафирај", "Нема документације која се враћа", "Ко је сачинио исправу?  ", "В а ж н о ! ! !",
                      "Читао", "Предмет сам примила/о и преконтролисала/о"):
        assert uklonjeno not in natpisi, uklonjeno
    assert app.c["odgovori"]["dok_za_vracanje"] == "НЕ" and app.c["odgovori"]["sacinio_list"] == "ми"
    assert app._polja["valuta"].get() == "евра"
    assert kucica(koren, "Да", 0) == "☐"  # „Купац првог стана“ није унапред означен
    assert kucica(koren, "Да", 1) == "☑" and kucica(koren, "Да", 2) == "☑" and kucica(koren, "Купац") == "☑"
    assert not [w for w in svi(koren) if isinstance(w, tk.Label) and "пор. пријаве" in str(w.cget("text"))]  # уклоњено
    assert {k for k, _ in app._celije} >= {"cena_ok", "pranje_novca", "dato_uputstvo"}  # 12 редова КОНТРОЛЕ
    assert fajl.spisak() and fajl.spisak()[0]["naziv"] == "ОПУ 12/2026"  # постојећа није отворена сама


def test_klik_na_listu_je_odgovor(koren, poruke):
    app = zapocni(koren)
    assert app.c["odgovori"]["posao"] == "продаја" and kucica(koren, "Продаја") == "☑"
    for natpis in ("Мејлом", "Запис", "Имамо ЛК уговарача и супружника", "Продавац је наследио / поклон",
                   "Продавац купио пре брака — доказ", "Купац прихвата ризик"):
        klik(koren, natpis)
    o = app.c["odgovori"]
    assert (o["nacin_prijema"], o["forma"], o["lk_ugovaraca"], o["nasledio"], o["kupac_prihvata_rizik"]) == \
        ("имејлом", "јавнобележнички запис", "да", ["да", "спб"], "да")
    klik(koren, "Лично")  # друга кућица исте групе замењује прву
    klik(koren, "Продавац је наследио / поклон")  # поновни клик уклања
    assert o["nacin_prijema"] == "лично" and o["nasledio"] == ["спб"]
    klikni(koren, app._celije[("mesto", "терен")])  # КОНТРОЛА „Излази се на лице места“ — десно „Да“
    assert o["mesto"] == "терен"
    klikni(koren, app._celije[("dato_uputstvo", "ДА")])  # нова ставка листа 23.1
    klik(koren, "Да", 0)  # „Купац првог стана“ — Да
    assert o["dato_uputstvo"] == "ДА" and o["kupac_prvi_stan"] == "да"
    klikni(koren, app._celije[("mesto", "терен")])  # поновни клик на изабрану ћелију — без одговора
    assert "mesto" not in o
    sacuvano = fajl.ucitaj(app.putanja)["odgovori"]  # сачувано одмах
    assert sacuvano["dato_uputstvo"] == "ДА" and "mesto" not in sacuvano
    assert not poruke


def test_linije_lista(koren, poruke):
    app = zapocni(koren)
    e = polje_za(app, "cena")
    e.event_generate("<FocusIn>")  # уклања сиви савет
    e.insert(0, "85.000")
    e.event_generate("<FocusOut>")
    assert app.c["odgovori"]["cena"] == "85.000"
    e = polje_za(app, "posao_drugo")
    e.event_generate("<FocusIn>")
    e.insert(0, "Размена")  # посао из Саве — препознат
    e.event_generate("<FocusOut>")
    koren.update()
    assert app.c["odgovori"]["posao"] == "размена" and "posao_drugo" not in app.c["odgovori"]
    e = polje_za(app, "posao_drugo")
    e.delete(0, "end")
    e.insert(0, "уговор о грађењу")
    e.event_generate("<FocusOut>")
    koren.update()
    assert app.c["odgovori"]["posao"] == "друго" and app.c["odgovori"]["posao_drugo"] == "уговор о грађењу"
    e = polje_za(app, "termin")
    e.event_generate("<FocusIn>")
    e.insert(0, "сутра")
    e.event_generate("<FocusOut>")
    assert "termin" not in app.c["odgovori"] and any("датум и време" in p for p in poruke)


def test_poklon_na_listu(koren, poruke):
    app = zapocni(koren, "Поклон")
    assert "cena" not in app._polja  # цена само за продају — за поклон је нема на листу
    assert str(polje_za(app, "motiv").cget("state")) == "normal"
    klik(koren, "Поклонодавац је наследио / поклон")  # поклон: важи (Сава: продаја и поклон)
    assert app.c["odgovori"]["nasledio"] == ["да"]


def test_paraf_na_listu(koren, poruke):
    """На листу су само ✎ и ▤ (остали парафи су на страни „Парафи“ — налог 27.11.2026)."""
    app = zapocni(koren)
    klik(koren, "✎  Контрола извршена")
    assert any("Попунио/ла" in p for p in poruke) and not app.c["potvrde"]
    app.v_popunio.set("Мила")
    app._sacuvaj_popunio()
    koren.update()
    klik(koren, "✎  Контрола извршена")
    assert app.c["potvrde"]["kontrola"]["ime"] == "Мила"
    app.parafiraj("spremno")  # страна „Парафи“: КОНТРОЛА још не пролази
    assert "spremno" not in app.c["potvrde"] and any("не може на читање" in p for p in poruke)


def test_zapoceta_pa_nova_stranka(koren, poruke):
    app = zapocni(koren, "Поклон")
    assert app.putanja is not None  # први клик на листу је први унос: датотека постоји
    dugme(koren, ttk.Button, "Странке и детаљна питања →").invoke()
    koren.update()
    assert app.izbor == gui.LICA and app.levo.winfo_ismapped()
    app._e_nova.insert(0, PETAR)
    dugme(koren, ttk.Button, "Додај странку").invoke()
    koren.update()
    assert [x["ime"] for x in app.c["lica"]] == [PETAR]
    assert not poruke


def test_odgovor_klikom_se_odmah_cuva(koren, poruke):
    app = sa_strankama(koren)
    app.idi("B")
    koren.update()
    dugme(koren, ttk.Radiobutton, "у браку", 0).invoke()
    koren.update()
    assert app.c["stranke"]["1"]["brak"] == "у браку"
    assert app._cipovi["1.brak"].cget("text").strip() == "Да"
    assert fajl.ucitaj(app.putanja)["stranke"]["1"]["brak"] == "у браку"
    dugme(koren, ttk.Radiobutton, "пре брака", 0)  # условно питање се појавило


def test_tekst_pa_klik_na_drugo_pitanje(koren, poruke):
    """Упис износа при изласку из поља не сме да поништи клик на друго питање (страна се не исцртава поново)."""
    app = sa_strankama(koren)
    app.idi("V")
    koren.update()
    e = polje_za(app, "cena")
    e.insert(0, "85.000")
    e.event_generate("<FocusOut>")
    radio = dugme(koren, ttk.Radiobutton, "RSD")
    assert radio.winfo_exists()
    radio.invoke()
    koren.update()
    assert app.c["odgovori"]["cena"] == "85.000" and app.c["odgovori"]["valuta"] == "RSD"


def test_pogresan_iznos_prikazan_uz_polje(koren, poruke):
    app = sa_strankama(koren)
    app.idi("V")
    koren.update()
    e = polje_za(app, "cena")
    e.insert(0, "много")
    e.event_generate("<FocusOut>")
    koren.update()
    assert "cena" not in app.c["odgovori"]
    assert "износ бројем" in app._greske["cena"].cget("text") and not poruke


def test_polje_se_upisuje_pri_izlasku(koren, poruke):
    app = sa_strankama(koren)
    app.idi("V")
    koren.update()
    e = polje_za(app, "cena")
    e.insert(0, "120.000")  # курсор није изашао из поља (нема FocusOut)
    app.v_popunio.set("Мила")
    putanja = app.putanja
    app.zatvori()
    c = fajl.ucitaj(putanja)
    assert c["odgovori"]["cena"] == "120.000" and c["popunio"] == "Мила"


def test_grupna_potvrda_preko_spiska(koren, poruke):
    app = sa_strankama(koren)
    app.grupna_potvrda()
    koren.update()
    dijalog = next(w for w in koren.winfo_children() if isinstance(w, gui.DijalogPotvrde))
    assert len(dijalog.tabela.get_children()) == len(L.stanje(app.c)["grupna"])
    assert "cena_ok" not in app.c["odgovori"]  # ништа се не уписује док се не потврди
    dijalog.potvrdi()
    koren.update()
    assert app.c["odgovori"]["cena_ok"] == "ДА" and app.c["trag"]["cena_ok"]["nacin"] == "grupno"
    assert str(app.b_grupno.cget("state")) == "disabled"


def test_grupna_potvrda_kad_se_spisak_promenio(koren, poruke):
    app = sa_strankama(koren)
    app.grupna_potvrda()
    koren.update()
    dijalog = next(w for w in koren.winfo_children() if isinstance(w, gui.DijalogPotvrde))
    L.odgovori(app.c, "2.nastup", "преко пуномоћника")  # предлог „заступа пуномоћник“ се мења
    dijalog.potvrdi()
    koren.update()
    assert any("променио" in p for p in poruke)
    assert "k_punomocnik" not in app.c["odgovori"]
    novi = next(w for w in koren.winfo_children() if isinstance(w, gui.DijalogPotvrde))  # нови списак
    novi.potvrdi()
    koren.update()
    assert app.c["odgovori"]["k_punomocnik"] == "ДА"


def test_tocak_misa_iznad_padajuceg_spiska_ne_menja_posao(koren, poruke):
    app = sa_strankama(koren)
    for dogadjaj in ("<Button-4>", "<Button-5>", "<MouseWheel>"):
        app.cb_posao.event_generate(dogadjaj, **({"delta": -120} if dogadjaj == "<MouseWheel>" else {}))
        koren.update()
    assert app.c["odgovori"]["posao"] == "продаја" and app.v_posao.get() == "продаја"


def test_zavrsena_cek_lista_samo_za_citanje(koren, poruke):
    app = sa_strankama(koren)
    app.zavrsi_ili_vrati()
    app.idi("A")
    koren.update()
    radio = [w for w in svi(koren) if isinstance(w, ttk.Radiobutton)]
    assert radio and all(str(w.cget("state")) == "disabled" for w in radio)
    assert app.b_zavrsi.cget("text") == "Врати у рад"
    app.zavrsi_ili_vrati()
    assert app.c["stanje"] == "u_radu"


def test_parafi(koren, poruke):
    app = sa_strankama(koren)
    app.idi(gui.POTVRDE)
    app.parafiraj("citao")
    assert any("Попунио/ла" in p for p in poruke) and "citao" not in app.c["potvrde"]
    app.v_popunio.set("Мила")
    app._sacuvaj_popunio()
    app.parafiraj("primio")
    koren.update()
    next(w for w in koren.winfo_children() if isinstance(w, gui.DijalogPotvrde)).potvrdi()
    koren.update()
    assert app.c["potvrde"]["primio"]["ime"] == "Мила"
    app.parafiraj("spremno")  # КОНТРОЛА још не пролази (личне карте)
    assert "spremno" not in app.c["potvrde"] and any("не може на читање" in p for p in poruke)


def test_sazetak_kopiraj_i_word(koren, poruke, tmp_path):
    app = sa_strankama(koren)
    app.radi(L.odgovori, app.c, "cena", "85.000")
    app.idi(gui.SAZETAK)
    koren.update()
    app.kopiraj()
    tekst = koren.clipboard_get()
    assert PETAR in tekst and "Купопродајна цена: 85.000" in tekst
    p = app.u_word(tmp_path / "s.docx")
    assert p.is_file() and any(str(p) in x for x in poruke)  # отворен у Word-у


def test_zapocete_cek_liste_i_nastavak_rada(koren, poruke):
    app = sa_strankama(koren)
    app.radi(L.odgovori, app.c, "1.brak", "у браку")
    putanja = app.putanja
    app.idi("V")
    koren.update()
    e = polje_za(app, "cena")
    e.insert(0, "99.000")  # куцано, курсор није изашао из поља
    dugme(koren, ttk.Button, "Сачуване чек-листе").invoke()
    koren.update()
    assert app.ulaz.platno.winfo_ismapped() and not app.rad.winfo_ismapped() and app.ulaz.slika is not None
    assert fajl.ucitaj(putanja)["odgovori"]["cena"] == "99.000"
    assert app.ulaz.l_broj.cget("text") == "Сачуване чек-листе  1"
    redovi = [app.ulaz.tabela.item(i, "values") for i in app.ulaz.tabela.get_children()]
    assert redovi[0][1:4] == (f"{PETAR}, {JELENA}", "продаја", "у раду")
    app.ulaz.b_nazad.invoke()
    assert app.putanja == putanja and app.rad.winfo_ismapped()
    app.na_ulaz()
    app.ulaz.b_nastavi.invoke()  # прва (једина) је изабрана
    koren.update()
    assert app.putanja == putanja and app.c["stranke"]["1"]["brak"] == "у браку" and app.izbor == gui.LIST
    app.na_ulaz()
    app.ulaz.b_nova.invoke()
    assert app.putanja is None and app.izbor == gui.LIST and set(app.c["odgovori"]) == set(L.list23.PREDEFINISANO)


def test_sacuvane_zavrsene_i_ispravka(koren, poruke):
    """Налог 27.11.2026: попуњена чек-листа остаје сачувана за даљи рад и исправке — и кад је завршена."""
    app = sa_strankama(koren)
    app.zavrsi_ili_vrati()
    app.na_ulaz()
    koren.update()
    u = app.ulaz
    assert u.filter == "sve" and u.l_broj.cget("text") == "Сачуване чек-листе  1"  # завршене се виде одмах
    assert u.dugmad_filtera["u_radu"].cget("text") == "У раду (0)" and u.dugmad_filtera["zavrsena"].cget("text") == "Завршене (1)"
    u.dugmad_filtera["u_radu"].invoke()
    koren.update()
    assert u.prazno.winfo_ismapped() and str(u.b_nastavi.cget("state")) == "disabled"
    u.dugmad_filtera["zavrsena"].invoke()
    koren.update()
    assert u.l_broj.cget("text") == "Сачуване чек-листе  1" and u.b_nastavi.cget("text") == "Отвори"
    u.nastavi()
    koren.update()
    assert app.st["samo_citanje"]
    dugme(koren, ttk.Button, "Врати у рад").invoke()  # исправка завршене: дугме на врху листа
    koren.update()
    assert app.c["stanje"] == "u_radu"
    klik(koren, "Мејлом")
    assert fajl.ucitaj(app.putanja)["odgovori"]["nacin_prijema"] == "имејлом"


def test_trazi_u_sacuvanim(koren, poruke):
    for naziv, ime in (("ОПУ 12/2026", PETAR), ("ОПУ 13/2026", JELENA)):
        c = L.nov_list()
        L.postavi_naziv(c, naziv)
        L.dodaj_lice(c, ime, "продавац")
        fajl.sacuvaj(c, fajl.novo_ime(c))
    app = gui.Aplikacija(koren)
    app.na_ulaz()
    koren.update()
    u = app.ulaz
    assert len(u.tabela.get_children()) == 2
    u.e_trazi.insert(0, "јелена")
    koren.update()
    redovi = [u.tabela.item(i, "values") for i in u.tabela.get_children()]
    assert [r[0] for r in redovi] == ["ОПУ 13/2026"] and u.dugmad_filtera["sve"].cget("text") == "Све (1)"


def test_dugme_sacuvaj_i_naziv_datoteke(koren, poruke):
    """„Сачувај“ уписује и поље у које се управо куца; назив датотеке прати „Предмет / опис“."""
    app = zapocni(koren)
    klik(koren, "Мејлом")
    stara = app.putanja
    app.v_naziv.set("ОПУ 12/2026 Петровић")  # курсор није изашао из поља
    e = polje_za(app, "kontakt")
    e.insert(0, "060 000 000")
    dugme(koren, ttk.Button, "Сачувај").invoke()
    koren.update()
    assert app.putanja != stara and not stara.exists() and "ОПУ 12 2026 Петровић" in app.putanja.name
    c = fajl.ucitaj(app.putanja)
    assert c["naziv"] == "ОПУ 12/2026 Петровић" and c["odgovori"]["kontakt"] == "060 000 000"
    assert app.l_stanje.cget("text").startswith("✓ сачувано у") and app.putanja.name in app.l_stanje.cget("text")
    assert fajl.otvorena() == app.putanja.resolve()  # наставак при следећем покретању прати ново име
    assert [x["putanja"] for x in fajl.spisak()] == [app.putanja]


def ponovo_pokreni():
    k2 = novi_tk()
    app2 = gui.Aplikacija(k2)
    k2.update()
    return k2, app2


def test_novo_pokretanje_nastavlja_zapocetu(koren, poruke):
    """Налог 27.11.2026 („да чува започете чек листе“): чек-листа у раду, отворена при затварању, при новом покретању
    се отвара на листу, са свим уносима."""
    app = sa_strankama(koren)
    klik(koren, "Мејлом")
    e = polje_za(app, "kontakt")
    e.insert(0, "ПЕТАР ПЕТРОВИЋ")  # куцано, курсор није изашао из поља — затвара се на X
    putanja = app.putanja
    assert "сачувано у" in app.l_stanje.cget("text")
    app.zatvori()
    k2, app2 = ponovo_pokreni()
    try:
        assert app2.putanja == putanja and app2.izbor == gui.LIST
        assert app2.c["odgovori"]["nacin_prijema"] == "имејлом" and app2.c["odgovori"]["kontakt"] == "ПЕТАР ПЕТРОВИЋ"
        assert [x["ime"] for x in app2.c["lica"]] == [PETAR, JELENA]
        assert kucica(k2, "Мејлом") == "☑"
    finally:
        k2.destroy()


def test_nova_i_zavrsena_se_ne_otvaraju_same(koren, poruke):
    app = sa_strankama(koren)
    prva = app.putanja
    app.nova_cek_lista()  # нова, ништа унето
    app.zatvori()
    k2, app2 = ponovo_pokreni()
    try:
        assert app2.putanja is None  # празан лист; прва је у списку започетих
        assert [x["putanja"] for x in fajl.spisak()] == [prva]
        app2.otvori(prva)
        app2.zavrsi_ili_vrati()  # завршена
        app2.zatvori()
    except Exception:
        k2.destroy()
        raise
    k3, app3 = ponovo_pokreni()
    try:
        assert app3.putanja is None and fajl.spisak("zavrsena")[0]["putanja"] == prva
    finally:
        k3.destroy()


def test_svi_delovi_za_sve_poslove(koren, poruke):
    app = sa_strankama(koren)
    for posao in [L.NEODREDJEN, "продаја", "поклон", "доживотно издржавање", "завештање", "друго"]:
        app.radi(L.postavi_posao, app.c, posao)
        for oid in [gui.LIST] + [x[0] for x in L.ODELJCI] + [gui.LICA, gui.POTVRDE, gui.SAZETAK]:
            app.idi(oid)
            koren.update_idletasks()
    assert not poruke


def test_klik_na_listu_ne_trepce(koren, poruke):
    """Налог 27.11.2026 („сваки пут када пристиснем нешто апликација трепне“): клик на листу не исцртава лист
    поново — исти делови прозора остају, мења се само ☐/☑, сиво, текст парафа и бројачи."""
    app = zapocni(koren)
    papir, brojac = app._papir, app._cipovi_brojaca[L.DA]
    pre = {str(w) for w in svi(app._papir)}
    for natpis in ("Мејлом", "Запис", "Купац прихвата ризик", "Да"):
        klik(koren, natpis)
    klikni(koren, app._celije[("pranje_novca", "ДА")])
    app.v_popunio.set("Мила")
    app._sacuvaj_popunio()
    klik(koren, "✎  Контрола извршена")
    assert papir.winfo_exists() and app._papir is papir and brojac.winfo_exists()
    assert {str(w) for w in svi(app._papir)} >= pre  # ниједан део листа није направљен изнова
    assert kucica(koren, "Мејлом") == "☑" and kucica(koren, "Купац прихвата ризик") == "☑"
    assert app._celije[("pranje_novca", "ДА")].cget("background") == "#fbd3b0"
    assert app.c["potvrde"]["kontrola"]["ime"] == "Мила" and app.c["odgovori"]["kupac_prvi_stan"] == "да"
    assert brojac.cget("text").strip().startswith("Да ")


def test_list_prati_pravni_posao(koren, poruke):
    """Налог 27.11.2026: „Нека чек листа буде динамична. Када се промени правни посао мењају се и понуђени одговори у
    складу са логиком садржаном у Сави.“ Називи страна, ставке о супружницима и питања о послу прате посао."""
    app = zapocni(koren)
    natpisi = lambda: {str(w.cget("text")) for w in svi(koren) if isinstance(w, tk.Label)}  # noqa: E731
    e = polje_za(app, "cena")
    e.event_generate("<FocusIn>")
    e.insert(0, "85.000")
    e.event_generate("<FocusOut>")
    assert {"Продавчев супружник", "Купчев супружник", "Купац првог стана  "} <= natpisi()
    klik(koren, "Поклон")
    n = natpisi()
    assert {"Супружник поклонодавца", "Супружник поклонопримца", "Поклонодавац је наследио / поклон",
            "Поклонопримац и његов супружник стичу заједно", "Мотив поклона:  "} <= n
    assert "Купац првог стана  " not in n and "cena" not in app._polja and "motiv" in app._polja
    klik(koren, "Доживотно")
    n = natpisi()
    assert {"Супружник примаоца издржавања", "Прималац издржавања није у браку",
            "Искључено давање у дом за стара лица?  ", "Преносе се и новчана средства, аутомобил и остало?  "} <= n
    assert "Шта се преноси?  " not in n  # зависи од претходног одговора
    assert "Прималац издржавања је наследио / поклон" not in n  # Сава: „наследио?“ само за продају и поклон
    assert "Поклонопримац и његов супружник стичу заједно" not in n
    klik(koren, "Не", 0)  # „Искључено давање у дом за стара лица?“ — Не
    assert app.c["odgovori"]["dom_iskljucen"] == "не"
    klik(koren, "Да", 2)  # „Преносе се и новчана средства…“ — Да: појављује се „Шта се преноси?“
    assert "Шта се преноси?  " in natpisi()
    klik(koren, "возило")
    assert app.c["odgovori"]["prenos_obuhvata"] == ["возило"]
    klik(koren, "Доживотно")  # поново клик: посао није изабран
    assert "posao" not in app.c["odgovori"]
    assert "Изаберите правни посао горе — овде се тада појављују питања за тај посао." in natpisi()
    klik(koren, "Продаја")
    assert polje_za(app, "cena").get() == "85.000"  # одговори за продају су сачувани
    assert app.c["odgovori"]["dom_iskljucen"] == "не"  # и за доживотно (у сажетку само за доживотно)


def test_valuta_uz_cenu(koren, poruke):
    """Налог 27.11.2026: уз цену падајући списак евра / динара, подразумевано евра."""
    app = zapocni(koren)
    cb = app._polja["valuta"]
    assert cb.get() == "евра" and app.c["odgovori"]["valuta"] == "EUR"
    cb.set("динара")
    cb.event_generate("<<ComboboxSelected>>")
    koren.update()
    assert app.c["odgovori"]["valuta"] == "RSD" and fajl.ucitaj(app.putanja)["odgovori"]["valuta"] == "RSD"
    assert any("[CENA_EUR]" in x for x in [u["poruka"] for u in L.provera(app.c)])  # напомена за Word као у Сави


def test_paraf_bez_pitanja_i_ponistavanje(koren, poruke):
    """Налог 27.11.2026: параф без питања „Парафирати…?“; поновни клик поништава параф."""
    app = zapocni(koren)
    app.v_popunio.set("Иван")
    app._sacuvaj_popunio()
    klik(koren, "▤  Предмет физички спакован")
    assert app.c["potvrde"]["spakovan"]["ime"] == "Иван" and kucica(koren, "▤  Предмет физички спакован") == "☑"
    assert not any("Парафирати" in p for p in poruke)
    klik(koren, "▤  Предмет физички спакован")
    assert "spakovan" not in app.c["potvrde"] and kucica(koren, "▤  Предмет физички спакован") == "☐"
    app.parafiraj("primio")  # страна „Парафи“: „Предмет сам примила/о“ — са предлозима прво списак
    dijalog = next(w for w in koren.winfo_children() if isinstance(w, gui.DijalogPotvrde))
    dijalog.potvrdi()
    koren.update()
    assert app.c["potvrde"]["primio"]["ime"] == "Иван" and not any("Парафирати" in p for p in poruke)
