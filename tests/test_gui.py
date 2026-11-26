"""Прозор (прави Tk; на Linux-у под Xvfb): унос странака, одговор кликом, поља за текст, групна потврда, точкић
миша изнад падајућег списка, сажетак, Word, ново покретање. Поруке (messagebox) се бележе уместо да чекају клик."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
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


@pytest.fixture
def koren():
    k = tk.Tk()
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


def sa_strankama(koren):
    app = gui.Aplikacija(koren)
    app.v_posao.set("продаја")
    app.cb_posao.event_generate("<<ComboboxSelected>>")
    app.radi(L.dodaj_lice, app.c, PETAR, "продавац")
    app.radi(L.dodaj_lice, app.c, JELENA, "купац")
    koren.update()
    return app


def test_prazan_pocetak_i_nova_stranka(koren, poruke):
    app = gui.Aplikacija(koren)
    assert app.izbor == gui.LICA and app.putanja is None
    app._e_nova.insert(0, PETAR)
    app._e_nova.focus_force()
    koren.update()
    app._e_nova.event_generate("<Return>")
    koren.update()
    assert [x["ime"] for x in app.c["lica"]] == [PETAR]
    assert app.putanja and app.putanja.parent == fajl.fascikla() and app.putanja.is_file()  # сачувано одмах
    assert fajl.poslednja() == app.putanja
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
    e.insert(0, "120.000")
    e.focus_force()
    koren.update()
    putanja = app.putanja
    app.zatvori()
    assert fajl.ucitaj(putanja)["odgovori"]["cena"] == "120.000"


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


def test_novo_pokretanje_vraca_poslednju(koren, poruke):
    app = sa_strankama(koren)
    app.radi(L.odgovori, app.c, "1.brak", "у браку")
    putanja = app.putanja
    koren.destroy()
    k2 = tk.Tk()
    try:
        app2 = gui.Aplikacija(k2)
        assert app2.putanja == putanja and app2.c["stranke"]["1"]["brak"] == "у браку"
        app2.nova()
        assert app2.putanja is None and app2.c["lica"] == [] and fajl.poslednja() is None
    finally:
        k2.destroy()


def test_otvaranje_datoteke_iz_argumenta(koren, poruke, tmp_path):
    c = L.nova("ПРОБА", "поклон")
    L.dodaj_lice(c, PETAR, "поклонодавац")
    p = fajl.sacuvaj(c, tmp_path / "x.ceklista")
    app = gui.Aplikacija(koren, p)
    assert app.putanja == Path(p) and app.c["naziv"] == "ПРОБА"


def test_svi_delovi_za_sve_poslove(koren, poruke):
    app = sa_strankama(koren)
    for posao in [L.NEODREDJEN, "продаја", "поклон", "доживотно издржавање", "завештање", "друго"]:
        app.radi(L.postavi_posao, app.c, posao)
        for oid in [x[0] for x in L.ODELJCI] + [gui.LICA, gui.POTVRDE, gui.SAZETAK]:
            app.idi(oid)
            koren.update_idletasks()
    assert not poruke
