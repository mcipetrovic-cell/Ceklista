"""Прозор програма „Чек-листа“ (Tkinter): странке, питања по целинама, парафи и сажетак.

Свака измена се одмах чува у датотеку чек-листе (fajl.py) — нема дугмета „Сачувај“ и ништа се не губи при
изласку. Сав рад је у једној (главној) нити; програм не користи мрежу."""

from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

from . import NAZIV, POTPIS, VERZIJA, VERZIJA_BROJ, fajl, list23, logika as L, pitanja as P, sazetak as S, word

# ---------------------------------------------------------------- изглед (светло, пастел — као Сава)
POZADINA = "#f7f3ea"
KREM = "#fbf8ef"  # крем вео Саве (--livada-krem)
NARANDZASTA, NARANDZASTA_TAMNA = "#df7a3c", "#c05f24"  # главно дугме Саве
KARTICA = "#ffffff"
IVICA = "#e3dccb"
TEKST = "#1f2a44"
SIVO = "#6b6f7a"
NAGLASAK = "#4f6f9a"
BOJE_STATUSA = {
    L.DA: ("#e1efe4", "#2f6b3d"),
    L.NE: ("#f4e3de", "#8a3b2a"),
    L.NIJE_PRIMENLJIVO: ("#ececec", "#666666"),
    L.NIJE_PROVERENO: ("#fbf1d6", "#7d6318"),
    L.RADNJA: ("#fde0c4", "#9a4600"),
}
UTICAJ_POZADINA, UTICAJ_TEKST = "#fff4e2", "#6d4a12"
CRVENO = "#b00020"

LIST, LICA, POTVRDE, SAZETAK = "LIST", "LICA", "POTVRDE", "SAZETAK"
# поља листа у која се куца (упис при изласку из поља; не мењају изглед стране док се куца)
TEKST_LISTA = ("primljeno", "termin", "kontakt", "telefon", "posao_drugo", "cena", "motiv", "sacinio_list_drugo",
               "cena_isplacena" + L.NAPOMENA, "posed_predat" + L.NAPOMENA)


def _fontovi() -> dict:
    win = sys.platform == "win32"
    osnovni = "Segoe UI" if win else "DejaVu Sans"
    naslovni = "Georgia" if win else "DejaVu Serif"
    return {"osnovni": (osnovni, 10), "jaki": (osnovni, 10, "bold"), "mali": (osnovni, 9),
            "kosi": (osnovni, 9, "italic"), "naslov": (naslovni, 16, "bold"), "podnaslov": (naslovni, 12, "bold"),
            "lista": (osnovni, 10), "tekst": ("Consolas" if win else "DejaVu Sans Mono", 10)}


def otvori_spolja(putanja: Path) -> None:
    """Отвара датотеку подразумеваним програмом (Word за .docx, Explorer за фасциклу)."""
    try:
        if sys.platform == "win32":
            os.startfile(str(putanja))  # noqa: S606 — датотека коју је програм управо направио
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(putanja)])
        else:
            subprocess.Popen(["xdg-open", str(putanja)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


class Pomicno(ttk.Frame):
    """Оквир са клизачем; точкић миша помера садржај док је показивач изнад њега."""

    def __init__(self, roditelj):
        super().__init__(roditelj, style="Pozadina.TFrame")
        self.platno = tk.Canvas(self, background=POZADINA, highlightthickness=0, borderwidth=0)
        self.klizac = ttk.Scrollbar(self, orient="vertical", command=self.platno.yview)
        self.platno.configure(yscrollcommand=self.klizac.set)
        self.klizac.pack(side="right", fill="y")
        self.platno.pack(side="left", fill="both", expand=True)
        self.unutra = ttk.Frame(self.platno, style="Pozadina.TFrame")
        self._prozor = self.platno.create_window(0, 0, anchor="nw", window=self.unutra)
        self.unutra.bind("<Configure>", lambda e: self.platno.configure(scrollregion=self.platno.bbox("all")))
        self.platno.bind("<Configure>", self._sirina)
        self.bind_all("<MouseWheel>", self._tocak, add="+")
        self.bind_all("<Button-4>", self._tocak, add="+")
        self.bind_all("<Button-5>", self._tocak, add="+")
        self.na_promenu_sirine = None

    def _sirina(self, e):
        self.platno.itemconfigure(self._prozor, width=e.width)
        if self.na_promenu_sirine:
            self.na_promenu_sirine(e.width)

    def _ispod_misa(self) -> bool:
        try:
            w = self.winfo_containing(*self.winfo_pointerxy())
        except (KeyError, tk.TclError):
            return False
        while w is not None:
            if w is self:
                return True
            w = w.master
        return False

    def _tocak(self, e):
        if not self._ispod_misa():
            return
        if getattr(e, "num", None) == 4:
            korak = -3
        elif getattr(e, "num", None) == 5:
            korak = 3
        else:
            korak = -int(e.delta / 120) * 3 if abs(e.delta) >= 120 else (-1 if e.delta > 0 else 1)
        self.platno.yview_scroll(korak, "units")

    def ocisti(self):
        for w in self.unutra.winfo_children():
            w.destroy()

    def polozaj(self) -> float:
        return self.platno.yview()[0]

    def vrati(self, polozaj: float):
        self.update_idletasks()
        self.platno.configure(scrollregion=self.platno.bbox("all"))
        self.platno.yview_moveto(polozaj)


class Aplikacija:
    def __init__(self, koren: tk.Tk):
        self.koren = koren
        self.f = _fontovi()
        self.c: dict = L.nova()
        self.putanja: Path | None = None
        self.izbor = LICA
        self.st: dict = L.stanje(self.c)
        self._potpis_strane = None
        self._cipovi: dict[str, tk.Label] = {}
        self._omotani: list[tk.Label] = []
        self._otvorene_napomene: set[str] = set()
        self._potvrde_polja: dict[str, callable] = {}
        self._greske: dict[str, tk.Label] = {}
        self._drzi: list = []
        self._polja: dict[str, tk.Widget] = {}  # ознака питања → поље за унос текста (за пробе и фокус)
        self._celije: dict[tuple, tk.Label] = {}  # (кључ, вредност) → ћелија КОНТРОЛЕ на листу
        self._stil()
        ttk.Label(koren, text=f"ЧЕК-ЛИСТА · верзија {VERZIJA_BROJ} · {POTPIS}", style="Podnozje.TLabel",
                  anchor="w", padding=(14, 3)).pack(side="bottom", fill="x")
        self.rad = ttk.Frame(koren, style="Pozadina.TFrame")
        self._napravi()
        self.ulaz = Ulaz(self)
        self.sacuvano = ""  # време последњег чувања (за натпис „сачувано“ у заглављу)
        otvorena = fajl.otvorena()  # започета чек-листа из претходног рада се наставља (налог 27.11.2026)
        if not (otvorena and self.otvori(otvorena)):
            self.nova_cek_lista()
        koren.protocol("WM_DELETE_WINDOW", self.zatvori)

    # ------------------------------------------------------------ изглед
    def _stil(self):
        k = self.koren
        k.title(f"{NAZIV} {VERZIJA}")
        k.configure(background=POZADINA)
        # подразумевани фонтови Tk (не „*Font“ у бази опција — то би прегазило фонт из стилова ttk)
        for ime in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            try:
                tkfont.nametofont(ime).configure(family=self.f["osnovni"][0], size=self.f["osnovni"][1])
            except tk.TclError:
                pass
        s = ttk.Style(k)
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure(".", background=POZADINA, foreground=TEKST, font=self.f["osnovni"])
        s.configure("Pozadina.TFrame", background=POZADINA)
        s.configure("Kartica.TFrame", background=KARTICA, relief="solid", borderwidth=1)
        s.configure("Zaglavlje.TFrame", background="#efe8d8")
        s.configure("TLabel", background=POZADINA, foreground=TEKST)
        s.configure("Zaglavlje.TLabel", background="#efe8d8")
        s.configure("Kartica.TLabel", background=KARTICA)
        s.configure("Naslov.TLabel", font=self.f["naslov"], background=POZADINA)
        s.configure("Podnaslov.TLabel", font=self.f["podnaslov"], background=POZADINA)
        s.configure("Sivo.TLabel", foreground=SIVO, background=POZADINA, font=self.f["mali"])
        s.configure("TRadiobutton", background=KARTICA)
        s.configure("TCheckbutton", background=KARTICA)
        s.configure("Pozadina.TCheckbutton", background=POZADINA)
        s.configure("TButton", padding=(10, 4))
        s.configure("Glavno.TButton", padding=(12, 5), font=self.f["jaki"])
        s.configure("Malo.TButton", padding=(6, 1), font=self.f["mali"])
        s.configure("Podnozje.TLabel", background=KREM, foreground="#55607a", font=self.f["mali"])
        s.configure("Ulaz.Treeview", rowheight=26, font=self.f["osnovni"], background="#fffdf8", fieldbackground="#fffdf8")
        s.configure("Ulaz.Treeview.Heading", font=self.f["jaki"], background="#eef3f9", foreground="#34466b", relief="flat")
        s.map("Ulaz.Treeview", background=[("selected", "#dbe5f1")], foreground=[("selected", TEKST)])
        s.map("TRadiobutton", background=[("active", "#f3efe4")])
        s.map("TCheckbutton", background=[("active", "#f3efe4")])

    def _napravi(self):
        """Радни приказ једне чек-листе (у оквиру self.rad; почетни екран је Ulaz)."""
        k = self.koren
        z = ttk.Frame(self.rad, style="Zaglavlje.TFrame", padding=(14, 10))
        z.pack(side="top", fill="x")
        ttk.Button(z, text="Нова чек-листа", style="Malo.TButton", command=self.nova_cek_lista).grid(
            row=0, column=0, sticky="we", padx=(0, 14))
        ttk.Button(z, text="Започете чек-листе", style="Malo.TButton", command=self.na_ulaz).grid(
            row=1, column=0, sticky="we", padx=(0, 14), pady=(4, 0))
        ttk.Label(z, text=NAZIV, style="Zaglavlje.TLabel", font=self.f["naslov"]).grid(row=0, column=1, rowspan=2,
                                                                                         sticky="w", padx=(0, 18))
        ttk.Label(z, text="Предмет / опис", style="Zaglavlje.TLabel").grid(row=0, column=2, sticky="w")
        self.v_naziv = tk.StringVar()
        self.e_naziv = ttk.Entry(z, textvariable=self.v_naziv, width=34)
        self.e_naziv.grid(row=1, column=2, sticky="we", padx=(0, 12))
        ttk.Label(z, text="Правни посао", style="Zaglavlje.TLabel").grid(row=0, column=3, sticky="w")
        self.v_posao = tk.StringVar()
        self.cb_posao = ttk.Combobox(z, textvariable=self.v_posao, state="readonly", width=24,
                                     values=[L.NEODREDJEN] + list(P.POSLOVI) + ["друго"])
        self.cb_posao.grid(row=1, column=3, sticky="w", padx=(0, 12))
        ttk.Label(z, text="Попунио/ла", style="Zaglavlje.TLabel").grid(row=0, column=4, sticky="w")
        self.v_popunio = tk.StringVar()
        self.e_popunio = ttk.Entry(z, textvariable=self.v_popunio, width=22)
        self.e_popunio.grid(row=1, column=4, sticky="w", padx=(0, 12))
        self.l_stanje = ttk.Label(z, text="", style="Zaglavlje.TLabel", font=self.f["jaki"])
        self.l_stanje.grid(row=0, column=5, sticky="e")
        self.b_zavrsi = ttk.Button(z, text="Заврши чек-листу", command=self.zavrsi_ili_vrati)
        self.b_zavrsi.grid(row=1, column=5, sticky="e")
        z.columnconfigure(1, weight=1)
        z.columnconfigure(4, weight=1)
        self.e_naziv.bind("<FocusOut>", lambda e: self._sacuvaj_naziv())
        self.e_naziv.bind("<Return>", lambda e: self._sacuvaj_naziv())
        self.e_popunio.bind("<FocusOut>", lambda e: self._sacuvaj_popunio())
        self.e_popunio.bind("<Return>", lambda e: self._sacuvaj_popunio())
        self.cb_posao.bind("<<ComboboxSelected>>", lambda e: self.radi(L.postavi_posao, self.c, self.v_posao.get()))

        dno = ttk.Frame(self.rad, style="Pozadina.TFrame", padding=(14, 6))
        dno.pack(side="bottom", fill="x")
        self.brojaci = ttk.Frame(dno, style="Pozadina.TFrame")
        self.brojaci.pack(side="left")
        self.b_grupno = ttk.Button(dno, text="Сагласан сам са свим осталим предложеним одговорима",
                                   command=self.grupna_potvrda)
        self.b_grupno.pack(side="right")

        telo = ttk.Frame(self.rad, style="Pozadina.TFrame")
        telo.pack(side="top", fill="both", expand=True)
        levo = ttk.Frame(telo, style="Pozadina.TFrame", padding=(10, 10, 4, 10))
        levo.pack(side="left", fill="y")
        self.levo = levo
        self.lista = tk.Listbox(levo, width=46, activestyle="none", font=self.f["lista"], borderwidth=1,
                                relief="solid", highlightthickness=0, background=KARTICA, foreground=TEKST,
                                selectbackground="#dbe5f1", selectforeground=TEKST, exportselection=False)
        self.lista.pack(fill="y", expand=True)
        self.lista.bind("<<ListboxSelect>>", self._izabrana_stavka)
        self._stavke_liste: list[str] = []
        self.sadrzaj = Pomicno(telo)
        self.sadrzaj.pack(side="left", fill="both", expand=True, padx=(4, 10), pady=10)
        self.sadrzaj.na_promenu_sirine = self._prelomi
        for dogadjaj in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            # точкић изнад падајућег списка би тихо променио одговор (правни посао, својство) — помера страну
            k.bind_class("TCombobox", dogadjaj, self._tocak_strane)
            k.bind_class("Text", dogadjaj, self._tocak_strane)

    def _tocak_strane(self, e):
        self.sadrzaj._tocak(e)
        return "break"

    # ------------------------------------------------------------ рад са моделом
    def radi(self, fn, *args, **kwargs):
        """Измена модела: порука на грешку, иначе одмах чување и освежавање."""
        try:
            ishod = fn(*args, **kwargs)
        except L.GreskaUnosa as e:
            messagebox.showwarning(NAZIV, str(e), parent=self.koren)
            self.osvezi(sve=True)
            return None
        self.sacuvaj()
        self.osvezi()
        return ishod if ishod is not None else True

    def sacuvaj(self):
        try:
            if self.putanja is None:
                self.putanja = fajl.novo_ime(self.c, self._fascikla())
            fajl.sacuvaj(self.c, self.putanja)
            fajl.zapamti_otvorenu(self.putanja if self.c.get("stanje") == "u_radu" else None)
            self.sacuvano = dt.datetime.now().strftime("%H.%M")
        except OSError as e:
            messagebox.showerror(NAZIV, f"Чек-листа није сачувана: {e}", parent=self.koren)

    def _fascikla(self) -> Path:
        return self.putanja.parent if self.putanja else fajl.fascikla()

    def _sacuvaj_naziv(self):
        if self.v_naziv.get().strip() != (self.c.get("naziv") or "") and not self.st["samo_citanje"]:
            self.radi(L.postavi_naziv, self.c, self.v_naziv.get())

    def _sacuvaj_popunio(self):
        if self.v_popunio.get().strip() != (self.c.get("popunio") or ""):
            self.radi(L.postavi_popunio, self.c, self.v_popunio.get())

    def _sacuvaj_otvoreno(self):
        """Сва поља у која је куцано, а нису уписана (курсор није изашао из поља), уписују се пре изласка, отварања
        друге чек-листе, сажетка и парафа — не само поље у коме је курсор (фокус на Windows-у није поуздан).
        Поље без измене се не дира."""
        # прво заглавље: освежавање после уписа поља враћа заглавље на сачувано стање
        if self.v_naziv.get().strip() != (self.c.get("naziv") or ""):
            self._sacuvaj_naziv()
        if self.v_popunio.get().strip() != (self.c.get("popunio") or ""):
            self._sacuvaj_popunio()
        try:
            fokus = self.koren.focus_get()
        except (KeyError, tk.TclError):
            fokus = None
        prvo = self._potvrde_polja.get(str(fokus)) if fokus is not None else None
        for upis in ([prvo] if prvo else []) + [u for u in list(self._potvrde_polja.values()) if u is not prvo]:
            try:
                upis()
            except tk.TclError:
                pass  # поље је нестало при поновном исцртавању стране; његов упис је већ обављен

    # ------------------------------------------------------------ почетак, започете чек-листе, отварање
    def na_ulaz(self):
        """Започете чек-листе: наставак рада или нова чек-листа."""
        if self.rad.winfo_ismapped():
            self._sacuvaj_otvoreno()
        self.rad.pack_forget()
        self.koren.title(NAZIV)
        self.ulaz.prikazi()

    def _u_rad(self):
        self.ulaz.sakrij()
        self.rad.pack(side="top", fill="both", expand=True)
        self._otvorene_napomene.clear()
        self.osvezi(sve=True, vrh=True)

    def nova_cek_lista(self) -> None:
        """Празан лист 23.1 — једини улаз у чек-листу предмета (налог 27.11.2026). Датотека настаје са првим уносом."""
        if self.rad.winfo_ismapped():
            self._sacuvaj_otvoreno()
        self.c, self.putanja = L.nov_list(), None
        self.sacuvano = ""
        fajl.zapamti_otvorenu(None)
        self.izbor = LIST
        self._u_rad()

    def nazad(self) -> None:
        """Са списка започетих назад на чек-листу која је била отворена."""
        self._u_rad()

    def otvori(self, putanja: Path) -> bool:
        try:
            c = fajl.ucitaj(putanja)
        except L.GreskaUnosa as e:
            messagebox.showwarning(NAZIV, str(e), parent=self.koren)
            return False
        self.c, self.putanja = c, Path(putanja)
        self.sacuvano = ""
        if c["stanje"] == "u_radu":
            fajl.zapamti_otvorenu(self.putanja)
        self.izbor = LIST
        self._u_rad()
        return True

    def zatvori(self):
        if self.rad.winfo_ismapped():
            self._sacuvaj_otvoreno()
        self.koren.destroy()

    # ------------------------------------------------------------ освежавање
    def osvezi(self, sve: bool = False, vrh: bool = False):
        self.st = L.stanje(self.c)
        if self.koren.focus_get() is not self.e_naziv:
            self.v_naziv.set(self.c.get("naziv") or "")
        if self.koren.focus_get() is not self.e_popunio:
            self.v_popunio.set(self.c.get("popunio") or "")
        self.v_posao.set(self.st["posao"] or L.NEODREDJEN)
        samo = self.st["samo_citanje"]
        self.e_naziv.configure(state="disabled" if samo else "normal")
        self.cb_posao.configure(state="disabled" if samo else "readonly")
        if self.putanja is None:
            cuvanje = "још није сачувана"
        else:
            cuvanje = f"сачувано у {self.sacuvano}" if self.sacuvano else "сачувана"
        self.l_stanje.configure(text=f"Стање: {self.st['stanje_naziv']}  ·  {cuvanje}", font=self.f["mali"],
                                foreground="#2f6b3d" if samo or self.putanja else TEKST)
        self.b_zavrsi.configure(text="Врати у рад" if samo else "Заврши чек-листу")
        n = len(self.st["grupna"])
        self.b_grupno.configure(text=f"Сагласан сам са свим осталим предложеним одговорима ({n})",
                                state="normal" if n and not samo else "disabled")
        ime = self.putanja.name if self.putanja else "нова чек-листа (још није сачувана)"
        self.koren.title(f"{NAZIV} — {ime}")
        self._osvezi_brojace()
        self._osvezi_listu()
        self._prikazi(sve, vrh)

    def _osvezi_brojace(self):
        for w in self.brojaci.winfo_children():
            w.destroy()
        for k, naziv in L.STATUSI.items():
            poz, boja = BOJE_STATUSA[k]
            tk.Label(self.brojaci, text=f" {naziv} {self.st['brojaci'][k]} ", background=poz, foreground=boja,
                     font=self.f["mali"], padx=4, pady=2).pack(side="left", padx=(0, 6))

    def _otvoreno_u(self, oid: str) -> int:
        return sum(1 for s in self.st["sve"] if s["odeljak"] == oid and s["primenljivost"] in ("da", "nepoznato")
                   and s["status"] in (L.NIJE_PROVERENO, L.RADNJA) and not s["pokriva"] and s["tip"] != "kvacica")

    def _osvezi_listu(self):
        stavke = [(LIST, f"Лист чек-листе {list23.OZNAKA}"), (LICA, f"Странке ({len(self.st['lica'])})")]
        for o in self.st["odeljci"]:
            n = self._otvoreno_u(o["id"])
            vazi = any(s["primenljivost"] != "ne" for s in self.st["sve"] if s["odeljak"] == o["id"])
            stavke.append((o["id"], o["naslov"] + (f"  · отворено {n}" if n else ("  ✓" if vazi else ""))))
        stavke += [(POTVRDE, f"Парафи ({len(self.st['potvrde'])}/{len(P.POTVRDE)})"), (SAZETAK, "Сажетак")]
        self._stavke_liste = [x[0] for x in stavke]
        self.lista.delete(0, "end")
        for i, (oid, tekst) in enumerate(stavke):
            self.lista.insert("end", "  " + tekst)
            if oid in (LIST, LICA, SAZETAK, POTVRDE):
                self.lista.itemconfigure(i, foreground=NAGLASAK)
        if self.izbor in self._stavke_liste:
            i = self._stavke_liste.index(self.izbor)
            self.lista.selection_clear(0, "end")
            self.lista.selection_set(i)
            self.lista.see(i)

    def _izabrana_stavka(self, _e=None):
        sel = self.lista.curselection()
        if sel and self._stavke_liste[sel[0]] != self.izbor:
            self._sacuvaj_otvoreno()
            self.idi(self._stavke_liste[sel[0]])

    def idi(self, oid: str):
        self.izbor = oid
        self.osvezi(sve=True, vrh=True)

    def _potpis(self) -> tuple:
        """Шта одређује изглед стране: ако се не промени, освежавају се само ознаке статуса (поље у коме се куца
        остаје, клик на друго питање не губи се)."""
        if self.izbor == LIST:
            odg = self.c.get("odgovori") or {}
            return (LIST, self.st["samo_citanje"], repr(self.st["potvrde"]),
                    tuple(sorted((k, repr(v)) for k, v in odg.items() if k not in TEKST_LISTA)),
                    tuple(s["primenljivost"] for s in self.st["sve"] if s["sid"] == ""))
        if self.izbor in (LICA, POTVRDE, SAZETAK):
            lica = tuple((x["id"], x["svojstvo"], x["strana"], x["pravno_lice"]) for x in self.st["lica"])
            return (self.izbor, lica, self.st["posao"], repr(self.st["potvrde"]), self.st["samo_citanje"],
                    repr(self.st["kontrola"]) if self.izbor == POTVRDE else "", repr(self.c) if self.izbor == SAZETAK else "")
        o = next(x for x in self.st["odeljci"] if x["id"] == self.izbor)
        stavke = o["opsta"] + [s for x in o["po_licima"] for s in x["stavke"]]
        return (self.izbor, self.st["samo_citanje"], tuple(x["ime"] for x in o["po_licima"]),
                tuple((s["id"], s["primenljivost"], s["razlog"], bool(s["predlog"]), s["uticaj"], s["oznaka"], s["pokriva"],
                       bool(s["trag"]) and s["status"] != L.NIJE_PROVERENO,
                       self._napomena_vidljiva(s), repr(s["vrednost"]) if s["tip"] not in ("tekst", "iznos", "napomena", "termin")
                       else "") for s in stavke))

    def _prikazi(self, sve: bool = False, vrh: bool = False):
        potpis = self._potpis()
        if not sve and potpis == self._potpis_strane:
            for oznaka, cip in self._cipovi.items():
                s = L.nadji(self.st, oznaka)
                if s:
                    self._oboji_cip(cip, s["status"])
            return
        polozaj = 0.0 if vrh else self.sadrzaj.polozaj()
        self._potpis_strane = potpis
        self.sadrzaj.ocisti()
        self._cipovi.clear()
        self._omotani.clear()
        self._potvrde_polja.clear()
        self._greske.clear()
        self._drzi.clear()
        self._polja.clear()
        self._celije.clear()
        if self.izbor == LIST:
            self.levo.pack_forget()  # лист заузима целу ширину, као на папиру
        elif not self.levo.winfo_ismapped():
            self.levo.pack(side="left", fill="y", before=self.sadrzaj)
        if self.izbor == LIST:
            self._strana_lista()
        elif self.izbor == LICA:
            self._strana_lica()
        elif self.izbor == POTVRDE:
            self._strana_potvrda()
        elif self.izbor == SAZETAK:
            self._strana_sazetka()
        else:
            self._strana_odeljka(self.izbor)
        self.sadrzaj.vrati(polozaj)

    def _sirina_teksta(self) -> int:
        return max(360, self.sadrzaj.platno.winfo_width() - 90)

    def _prelomi(self, sirina: int):
        for w in self._omotani:
            try:
                w.configure(wraplength=max(360, sirina - 90))
            except tk.TclError:
                pass

    def _oznaka(self, roditelj, tekst, stil="TLabel", **kw) -> ttk.Label:
        w = ttk.Label(roditelj, text=tekst, style=stil, wraplength=self._sirina_teksta(), justify="left", **kw)
        self._omotani.append(w)
        return w

    # ------------------------------------------------------------ лист 23.1 (као на папиру)
    def _strana_lista(self):
        """Лист „Чек листа 23.1“ канцеларије, распоређен као на папиру (list23.py): кућице, линије за упис, КОНТРОЛА
        Да | Не, парафи. Сваки клик је одговор на исто питање као у детаљним целинама; ништа се не уписује само."""
        u = self.sadrzaj.unutra
        samo = self.st["samo_citanje"]
        traka = ttk.Frame(u, style="Pozadina.TFrame")
        traka.pack(fill="x", pady=(0, 8))
        self._oznaka(traka, "Лист се попуњава кликом, као на папиру. Све остало (странке, детаљна питања, сажетак) је у "
                            "наставку.", "Sivo.TLabel").pack(side="left")
        ttk.Button(traka, text="Сажетак →", command=lambda: self.idi(SAZETAK)).pack(side="right")
        ttk.Button(traka, text="Странке и детаљна питања →", command=lambda: self.idi(LICA)).pack(side="right", padx=8)
        papir = tk.Frame(u, background="white", highlightbackground="#bdb5a3", highlightthickness=1, padx=30, pady=22)
        papir.pack(anchor="n", pady=(0, 16))
        self._papir = papir
        B, F = "white", self.f
        odg = self.c.get("odgovori") or {}

        def red(pady=(0, 10)):
            r = tk.Frame(papir, background=B)
            r.pack(fill="x", pady=pady)
            return r

        def tekst(roditelj, t, **kw):
            w = tk.Label(roditelj, text=t, background=B, foreground="#111111", font=kw.pop("font", F["osnovni"]), **kw)
            w.pack(side="left")
            return w

        def traka_naslov(t, boja="#fffccc"):
            tk.Label(papir, text=" ".join(t), background=boja, foreground="#111111", font=F["jaki"], relief="solid",
                     borderwidth=1, pady=2).pack(fill="x", pady=(6, 8))

        # 1. Примљено, начин пријема, ознака листа
        r = red()
        tekst(r, "Примљено:", width=13, anchor="w")
        self._linija(r, "primljeno", 20, "нпр. 27.11.2026 09:30")
        if not samo:
            tk.Button(r, text="сада", font=F["mali"], relief="flat", background="#eef3f9", cursor="hand2",
                      command=lambda: self.radi(L.odgovori, self.c, "primljeno", dt.datetime.now().strftime("%d.%m.%Y %H:%M"))
                      ).pack(side="left", padx=(4, 14))
        self._grupa(r, "nacin_prijema", (("Лично", "лично"), ("Мејлом", "имејлом")))
        tk.Label(r, text=f"ЧЕК ✈ {list23.OZNAKA}", background="#e8fbe0", foreground="#1f3a8a", font=F["jaki"],
                 relief="solid", borderwidth=1, padx=10).pack(side="right")
        # 2. Заказано за, врста исправе
        r = red()
        tekst(r, "Заказано за:", width=13, anchor="w")
        self._linija(r, "termin", 20, "датум и време")
        tk.Frame(r, width=40, background=B).pack(side="left")
        self._grupa(r, "forma", (("Запис", "јавнобележнички запис"), ("Солемнизација", "солемнизација")))
        # 3. Контакт, телефон
        r = red()
        tekst(r, "Контакт:", width=13, anchor="w")
        self._linija(r, "kontakt", 42)
        tekst(r, "   Тел:")
        self._linija(r, "telefon", 20)
        # 4. Правни посао
        r = red((6, 10))
        posao = odg.get("posao") or ""
        for naziv, vrednost in list23.POSLOVI_NA_LISTU:
            self._kucica(r, naziv, posao == vrednost, lambda v=vrednost: self._posao_sa_lista(v))
        tekst(r, "   Друго:")
        pocetno = odg.get("posao_drugo") or (posao if posao and posao not in dict(list23.POSLOVI_NA_LISTU).values()
                                             and posao != "друго" else "")
        e = self._linija(r, "posao_drugo", 30, "нпр. размена", pocetno=pocetno, upis=self._posao_drugo)
        e.pack_configure(fill="x", expand=True)
        # 5. ЛК (ставка „Дате су им пор. пријаве“ уклоњена — налог 27.11.2026)
        r = red()
        self._kucica_kljuc(r, "lk_ugovaraca", "Имамо ЛК уговарача и супружника", "да")
        # 6. Супружници
        traka_naslov("Супружници")
        dve = tk.Frame(papir, background=B)
        dve.pack(fill="x", pady=(0, 6))
        levo, desno = tk.Frame(dve, background=B), tk.Frame(dve, background=B)
        levo.pack(side="left", fill="both", expand=True)
        desno.pack(side="left", fill="both", expand=True, padx=(20, 0))
        for kolona, naslov in ((levo, "Продавчев супружник"), (desno, "Купчев супружник")):
            tk.Label(kolona, text=naslov, background=B, font=F["osnovni"]).pack(pady=(0, 6))
        stavke_levo = ((lambda r: self._kucica_vise(r, "nasledio", "да", "Продавац је наследио / поклон")),
                       (lambda r: self._kucica_kljuc(r, "prodavac_nije_u_braku", "Продавац није у браку", "да")),
                       (lambda r: self._kucica_kljuc(r, "sup_prodavca_dolazi", "Супружник долази да да сагласност", "да")),
                       (lambda r: self._kucica_vise(r, "nasledio", "спб", "Продавац купио пре брака — доказ")),
                       (lambda r: self._kucica_kljuc(r, "kupac_prihvata_rizik", "Купац прихвата ризик", "да")))
        stavke_desno = ((lambda r: self._kucica_kljuc(r, "sup_kupca_dolazi", "Супружник долази да да сагласност", "да")),
                        (lambda r: self._kucica_kljuc(r, "kupac_nije_u_braku", "Купац није у браку", "да")),
                        (lambda r: self._kucica_kljuc(r, "oba_supruznika", "Купац и његов супружник стичу заједно", "да")),
                        (lambda r: self._kucica_kljuc(r, "susvojina_pola", "Стичу сусвојину са уделима од по 1/2", "да")),
                        (lambda r: (tekst(r, "Купац првог стана  ", font=(F["osnovni"][0], F["osnovni"][1], "italic")),
                                    self._grupa(r, "kupac_prvi_stan", (("Да", "да"), ("Не", "не"))))))
        for kolona, stavke in ((levo, stavke_levo), (desno, stavke_desno)):
            for napravi in stavke:
                r = tk.Frame(kolona, background=B)
                r.pack(fill="x", pady=3)
                napravi(r)
        # 7. Део који се попуњава кад канцеларија прави уговор
        traka_naslov("Овај део се попуњава само када ми правимо уговор")
        r = red((0, 6))
        tekst(r, "Цена")
        self._linija(r, "cena", 18, "нпр. 85.000")
        r = red((0, 6))
        tekst(r, "Да ли ће купац на дан закључења уговора у потпуности измирити обавезу исплате кппр. цене?  ")
        self._grupa(r, "cena_isplacena", (("Да", "да"), ("Не", "не")))
        self._linija(r, "cena_isplacena" + L.NAPOMENA, 24, "ако не — рок и начин", kljuc_pitanja="cena_isplacena",
                     napomena=True).pack_configure(fill="x", expand=True, padx=(8, 0))
        r = red((0, 6))
        tekst(r, "Да ли је продавац увео купца у посед купљене непокретности?  ")
        self._grupa(r, "posed_predat", (("Да", "да"), ("Не", "не")))
        self._linija(r, "posed_predat" + L.NAPOMENA, 24, "ако не — када", kljuc_pitanja="posed_predat",
                     napomena=True).pack_configure(fill="x", expand=True, padx=(8, 0))
        r = red((0, 6))
        tekst(r, "Ко плаћа порез на пренос апсолутних права?  ")
        self._grupa(r, "porez_snosi", (("Продавац", "продавац"), ("Купац", "купац")))
        r = red((0, 12))
        tekst(r, "Ако је у питању уговор о поклону — МОТИВ:  ")
        self._linija(r, "motiv", 40).pack_configure(fill="x", expand=True)
        # 8. Парафи контроле и паковања (сличице оловке и списа на листу)
        r = red((4, 12))
        self._paraf_kucica(r, "kontrola", "✎  Контрола извршена")
        tk.Frame(r, width=30, background=B).pack(side="left")
        self._paraf_kucica(r, "spakovan", "▤  Предмет физички спакован")
        # 9. КОНТРОЛА и парафи десно
        blok = tk.Frame(papir, background=B)
        blok.pack(fill="x")
        tabela = tk.Frame(blok, background=B)
        tabela.pack(side="left", anchor="n")
        for i, (naslov, kljuc, levo_, desno_) in enumerate(list23.KONTROLA):
            tk.Label(tabela, text=("КОНТРОЛА — " if i == 0 else "") + naslov, background=B, anchor="e",
                     font=F["jaki"] if i == 0 else F["osnovni"]).grid(row=i, column=0, sticky="e", padx=(0, 4))
            for j, (natpis, vrednost) in enumerate((levo_, desno_)):
                self._celija(tabela, kljuc, natpis, vrednost, levo=j == 0).grid(row=i, column=1 + j, sticky="nsew")
        desno = tk.Frame(blok, background=B)
        desno.pack(side="left", fill="both", expand=True, padx=(28, 0), anchor="n")
        self._paraf_linija(desno, "primio", "Предмет сам примила/о и преконтролисала/о")
        r = tk.Frame(desno, background=B)
        r.pack(fill="x", pady=(10, 10))
        self._kucica_kljuc(r, "dok_za_vracanje", "Нема документације која се враћа", "НЕ")
        self._paraf_linija(desno, "dokumentacija", "Потврђујем да ми је ВРАЋЕНА сва документација — Налепница")
        self._paraf_linija(desno, "spremno", "Потврђујем да сам предмет спремила/о у целости и да може да иде на читање")
        # 10. Ко је сачинио исправу; Важно (парафи после броја)
        r = red((18, 6))
        tekst(r, "Ко је сачинио исправу?  ", font=F["jaki"])
        self._grupa(r, "sacinio_list", (("Ми", "ми"), ("Адвокат", "адвокат"), ("Агенција", "агенција"), ("Геометар", "геометар")))
        self._linija(r, "sacinio_list_drugo", 18).pack_configure(fill="x", expand=True)
        traka_naslov("Важно!!!", boja="#d9d9d9")
        vazno = tk.Frame(papir, background=B)
        vazno.pack(fill="x")
        for j, (k, naziv) in enumerate((("citao", "Читао"), ("pis", "Унео у ПИС"), ("plava", "у Плаву"), ("aa", "а/а"))):
            vazno.columnconfigure(j, weight=1, uniform="vazno")
            tk.Label(vazno, text=naziv, background=B, font=F["jaki"], relief="solid", borderwidth=1).grid(
                row=0, column=j, sticky="nsew")
            self._paraf_celija(vazno, k).grid(row=1, column=j, sticky="nsew")

    # ---- делови листа
    def _omoguceno(self, kljuc: str) -> bool:
        s = L.nadji(self.st, kljuc)
        return not self.st["samo_citanje"] and (s is None or s["primenljivost"] != "ne")

    def _kucica(self, roditelj, natpis: str, ukljuceno: bool, komanda, omoguceno: bool = True):
        boja = "#111111" if omoguceno else "#b0b0b0"
        okvir = tk.Frame(roditelj, background="white", cursor="hand2" if omoguceno else "")
        okvir.pack(side="left", padx=(0, 14))
        k = tk.Label(okvir, text="☑" if ukljuceno else "☐", background="white", foreground="#1f3a8a" if ukljuceno else boja,
                     font=(self.f["osnovni"][0], 17))
        k.pack(side="left")
        n = tk.Label(okvir, text=natpis, background="white", foreground=boja, font=self.f["osnovni"])
        n.pack(side="left", padx=(2, 0))
        if omoguceno:
            for w in (okvir, k, n):
                w.bind("<Button-1>", lambda _e: komanda())
        okvir.kucica = k
        return okvir

    def _kucica_kljuc(self, roditelj, kljuc: str, natpis: str, vrednost: str):
        """Кућица за једно питање: означена — вредност; поново клик — питање без одговора."""
        tren = (self.c.get("odgovori") or {}).get(kljuc)
        return self._kucica(roditelj, natpis, tren == vrednost,
                            lambda: self.radi(L.odgovori, self.c, kljuc, None if tren == vrednost else vrednost),
                            self._omoguceno(kljuc))

    def _kucica_vise(self, roditelj, kljuc: str, vrednost: str, natpis: str):
        """Кућица која додаје или уклања вредност питања са више избора („наследио“: да / спб)."""
        tren = list((self.c.get("odgovori") or {}).get(kljuc) or [])
        novo = [x for x in tren if x != vrednost] if vrednost in tren else tren + [vrednost]
        return self._kucica(roditelj, natpis, vrednost in tren, lambda: self.radi(L.odgovori, self.c, kljuc, novo or None),
                            self._omoguceno(kljuc))

    def _grupa(self, roditelj, kljuc: str, izbori):
        """Кућице од којих важи највише једна (као заокруживање на папиру)."""
        tren = (self.c.get("odgovori") or {}).get(kljuc)
        for natpis, vrednost in izbori:
            self._kucica(roditelj, natpis, tren == vrednost,
                         lambda v=vrednost: self.radi(L.odgovori, self.c, kljuc, None if tren == v else v),
                         self._omoguceno(kljuc))

    def _linija(self, roditelj, kljuc: str, sirina: int, savet: str = "", pocetno: str | None = None, upis=None,
                kljuc_pitanja: str | None = None, napomena: bool = False):
        """Линија за упис (поље), уписује се при изласку из поља."""
        odg = self.c.get("odgovori") or {}
        if pocetno is None:
            pocetno = odg.get(kljuc) or ""
            s = L.nadji(self.st, kljuc)
            if s and s["tip"] == "termin" and pocetno:
                pocetno = s["prikaz"].replace(". у ", " ")
        v = tk.StringVar(value=pocetno)
        self._drzi.append(v)
        omoguceno = self._omoguceno(kljuc_pitanja or kljuc)
        e = tk.Entry(roditelj, textvariable=v, width=sirina, relief="flat", font=self.f["osnovni"], background="#fbfbf7",
                     highlightthickness=1, highlightbackground="#9a9a9a", highlightcolor=NAGLASAK,
                     state="normal" if omoguceno else "disabled", disabledbackground="#f1f1f1")
        e.pack(side="left", padx=(2, 0), ipady=2)
        if savet and not pocetno and omoguceno:
            e.insert(0, savet)
            e.configure(foreground="#a0a0a0")

            def ocisti_savet(_e):
                if e.cget("foreground") == "#a0a0a0":
                    e.delete(0, "end")
                    e.configure(foreground="#111111")
            e.bind("<FocusIn>", ocisti_savet, add="+")
        stanje = {"poslednje": pocetno}

        def citaj() -> str:
            return "" if e.cget("foreground") == "#a0a0a0" else v.get()

        def sacuvaj_liniju():
            t = citaj().strip()
            if t == stanje["poslednje"].strip() or self.st["samo_citanje"] or not omoguceno:
                return
            try:
                if upis:
                    upis(t)
                elif napomena:
                    L.odgovori(self.c, kljuc_pitanja, napomena=t)
                else:
                    L.odgovori(self.c, kljuc, t)
            except L.GreskaUnosa as greska:
                messagebox.showwarning(NAZIV, str(greska), parent=self.koren)
                return
            stanje["poslednje"] = t
            self.sacuvaj()
            self.osvezi()

        e.bind("<FocusOut>", lambda _e: sacuvaj_liniju(), add="+")
        e.bind("<Return>", lambda _e: sacuvaj_liniju())
        self._potvrde_polja[str(e)] = sacuvaj_liniju
        self._polja[kljuc] = e
        return e

    def _posao_sa_lista(self, vrednost: str):
        posao = (self.c.get("odgovori") or {}).get("posao")

        def promena():
            L.postavi_posao(self.c, "" if posao == vrednost else vrednost)
            L.odgovori(self.c, "posao_drugo", None)
        self.radi(promena)

    def _posao_drugo(self, tekst: str):
        """„Друго: ___“: посао из Саве ако се препозна (нпр. „размена“), иначе „друго“ и упис текста."""
        t = " ".join(tekst.split())
        poznat = next((x for x in P.POSLOVI if x.casefold() == t.casefold()), None)
        if poznat:
            L.postavi_posao(self.c, poznat)
            L.odgovori(self.c, "posao_drugo", None)
        elif t:
            L.postavi_posao(self.c, "друго")
            L.odgovori(self.c, "posao_drugo", t)
        else:
            if (self.c.get("odgovori") or {}).get("posao") == "друго":
                L.postavi_posao(self.c, "")
            L.odgovori(self.c, "posao_drugo", None)

    def _celija(self, roditelj, kljuc: str, natpis: str, vrednost: str, levo: bool):
        """Ћелија КОНТРОЛЕ (Да | Не): лева је подразумевана колона листа, десна алтернатива."""
        tren = (self.c.get("odgovori") or {}).get(kljuc)
        izabrana = tren == vrednost
        omoguceno = self._omoguceno(kljuc)
        pozadina = ("#cfe8d4" if levo else "#fbd3b0") if izabrana else "white"
        c = tk.Label(roditelj, text=natpis, width=4, background=pozadina, relief="solid", borderwidth=1,
                     font=self.f["jaki"] if izabrana else self.f["osnovni"], foreground="#111111" if omoguceno else "#b0b0b0",
                     cursor="hand2" if omoguceno else "")
        if omoguceno:
            c.bind("<Button-1>", lambda _e: self.radi(L.odgovori, self.c, kljuc, None if izabrana else vrednost))
        self._celije[(kljuc, vrednost)] = c
        return c

    def _paraf_tekst(self, k: str) -> str:
        p = (self.c.get("potvrde") or {}).get(k)
        return f"✓ {p.get('ime', '')}, {S.datum_vreme(p.get('vreme', ''))}" if p else ""

    def _paraf_kucica(self, roditelj, k: str, natpis: str):
        potpisano = bool((self.c.get("potvrde") or {}).get(k))
        okvir = self._kucica(roditelj, natpis, potpisano, lambda: self.parafiraj(k),
                             not potpisano and not self.st["samo_citanje"])
        if potpisano:
            tk.Label(okvir, text="  " + self._paraf_tekst(k), background="white", foreground="#2f6b3d",
                     font=self.f["mali"]).pack(side="left")
        return okvir

    def _paraf_linija(self, roditelj, k: str, natpis: str):
        tk.Label(roditelj, text=natpis, background="white", font=self.f["jaki"], wraplength=360, justify="center").pack(
            fill="x", pady=(8, 0))
        self._paraf_celija(roditelj, k, crta=True).pack(fill="x")

    def _paraf_celija(self, roditelj, k: str, crta: bool = False):
        okvir = None
        if crta:
            okvir = tk.Frame(roditelj, background="white")
            roditelj = okvir
        tekst = self._paraf_tekst(k)
        if tekst:
            w = tk.Label(roditelj, text=tekst, background="white", foreground="#2f6b3d", font=self.f["mali"], pady=4,
                         relief="solid" if not crta else "flat", borderwidth=0 if crta else 1)
        elif self.st["samo_citanje"]:
            w = tk.Label(roditelj, text=" ", background="white", relief="solid" if not crta else "flat",
                         borderwidth=0 if crta else 1, pady=4)
        else:
            w = tk.Label(roditelj, text="парафирај", background="white", foreground="#2c6aa0", cursor="hand2",
                         font=self.f["mali"], pady=4, relief="solid" if not crta else "flat", borderwidth=0 if crta else 1)
            w.bind("<Button-1>", lambda _e: self.parafiraj(k))
        if okvir is not None:
            w.pack(fill="x")
            tk.Frame(okvir, background="#555555", height=1).pack(fill="x")
            return okvir
        return w

    # ------------------------------------------------------------ странке
    def _strana_lica(self):
        u = self.sadrzaj.unutra
        ttk.Label(u, text="Странке", style="Naslov.TLabel").pack(anchor="w", pady=(0, 2))
        self._oznaka(u, "Унесите странке са својством у послу. Својство одређује страну (располаже / стиче), а од ње "
                        "зависе питања о супружнику и упису стицаоца. Име је довољно — ЈМБГ и подаци исправе се не уносе.",
                     "Sivo.TLabel").pack(anchor="w", pady=(0, 10))
        samo = self.st["samo_citanje"]
        posao = self.st["posao"]
        for lice in self.st["lica"]:
            kart = ttk.Frame(u, style="Kartica.TFrame", padding=(12, 8))
            kart.pack(fill="x", pady=4)
            v_ime = tk.StringVar(value=lice["ime"])
            v_sv = tk.StringVar(value=lice["svojstvo"])
            v_pr = tk.BooleanVar(value=lice["pravno_lice"])
            self._drzi += [v_ime, v_sv, v_pr]
            ttk.Label(kart, text=f"{lice['id']}.", style="Kartica.TLabel", font=self.f["jaki"]).grid(row=0, column=0, padx=(0, 8))
            e = ttk.Entry(kart, textvariable=v_ime, width=34)
            e.grid(row=0, column=1, sticky="we")
            cb = ttk.Combobox(kart, textvariable=v_sv, values=L.svojstva_za_posao(posao), width=26)
            cb.grid(row=0, column=2, padx=8)
            ch = ttk.Checkbutton(kart, text="правно лице", variable=v_pr)
            ch.grid(row=0, column=3, padx=4)
            ttk.Label(kart, text=f"страна: {lice['strana']}", style="Kartica.TLabel", foreground=SIVO).grid(row=0, column=4, padx=8)
            b = ttk.Button(kart, text="Уклони", style="Malo.TButton",
                           command=lambda sid=lice["id"], ime=lice["ime"]: self._ukloni_lice(sid, ime))
            b.grid(row=0, column=5)
            kart.columnconfigure(1, weight=1)

            def upis(sid=lice["id"], v_ime=v_ime, v_sv=v_sv, v_pr=v_pr, staro=dict(lice)):
                if (v_ime.get().strip(), v_sv.get().strip(), v_pr.get()) != (staro["ime"], staro["svojstvo"], staro["pravno_lice"]):
                    self.radi(L.izmeni_lice, self.c, sid, v_ime.get(), v_sv.get(), v_pr.get())

            for w in (e, cb):
                w.bind("<FocusOut>", lambda _e, upis=upis: upis())
                w.bind("<Return>", lambda _e, upis=upis: upis())
                self._potvrde_polja[str(w)] = upis
            cb.bind("<<ComboboxSelected>>", lambda _e, upis=upis: upis())
            ch.configure(command=upis)
            if samo:
                for w in (e, cb, ch, b):
                    w.configure(state="disabled")
        if not samo:
            nov = ttk.Frame(u, style="Kartica.TFrame", padding=(12, 10))
            nov.pack(fill="x", pady=(12, 4))
            ttk.Label(nov, text="Нова странка", style="Kartica.TLabel", font=self.f["jaki"]).grid(row=0, column=0, columnspan=4, sticky="w")
            v_ime, v_sv, v_pr = tk.StringVar(), tk.StringVar(), tk.BooleanVar()
            self._drzi += [v_ime, v_sv, v_pr]
            ttk.Label(nov, text="Име и презиме / назив", style="Kartica.TLabel").grid(row=1, column=0, sticky="w")
            ttk.Label(nov, text="Својство", style="Kartica.TLabel").grid(row=1, column=1, sticky="w", padx=8)
            e = ttk.Entry(nov, textvariable=v_ime, width=34)
            e.grid(row=2, column=0, sticky="we")
            cb = ttk.Combobox(nov, textvariable=v_sv, values=L.svojstva_za_posao(posao), width=26)
            cb.grid(row=2, column=1, padx=8)
            ttk.Checkbutton(nov, text="правно лице", variable=v_pr).grid(row=2, column=2, padx=4)

            def dodaj():
                if self.radi(L.dodaj_lice, self.c, v_ime.get(), v_sv.get(), v_pr.get()):
                    self.koren.after_idle(self._fokus_nove_stranke)

            ttk.Button(nov, text="Додај странку", style="Glavno.TButton", command=dodaj).grid(row=2, column=3, padx=(8, 0))
            e.bind("<Return>", lambda _e: dodaj())
            nov.columnconfigure(0, weight=1)
            self._e_nova = e
            if not self.st["lica"]:
                self.koren.after_idle(lambda: e.winfo_exists() and e.focus_set())
            if not posao:
                self._oznaka(u, "Савет: прво изаберите правни посао у заглављу — тада се у пољу „Својство“ нуде својства тог посла.",
                             "Sivo.TLabel").pack(anchor="w", pady=(6, 0))
        if self.st["lica"]:
            ttk.Button(u, text="Даље: питања чек-листе →", command=lambda: self.idi(L.ODELJCI[0][0])).pack(anchor="e", pady=10)

    def _fokus_nove_stranke(self):
        e = getattr(self, "_e_nova", None)
        if e is not None and e.winfo_exists():
            e.focus_set()

    def _ukloni_lice(self, sid: str, ime: str):
        if messagebox.askyesno(NAZIV, f"Уклонити странку „{ime}“ и све њене одговоре?", parent=self.koren):
            self.radi(L.ukloni_lice, self.c, sid)

    # ------------------------------------------------------------ питања
    def _strana_odeljka(self, oid: str):
        u = self.sadrzaj.unutra
        o = next(x for x in self.st["odeljci"] if x["id"] == oid)
        ttk.Label(u, text=o["naslov"], style="Naslov.TLabel").pack(anchor="w", pady=(0, 6))
        if oid == L.NEP:
            self._oznaka(u, "Питања провере непокретности из модула Саве. Програм нема податке катастра (у Сави долазе из "
                            "Снопа), па ништа не предлаже — проверите у листу непокретности и одговорите.",
                         "Sivo.TLabel").pack(anchor="w", pady=(0, 8))
        def_o = next((x for x in L.DEFINICIJA if x["id"] == oid), {})
        sve = o["opsta"] + [s for x in o["po_licima"] for s in x["stavke"]]
        if not sve and not def_o.get("po_stranci"):
            self._oznaka(u, "Ова целина не важи за изабрани правни посао.", "Sivo.TLabel").pack(anchor="w")
        for s in o["opsta"]:
            if s["primenljivost"] in ("da", "nepoznato"):
                self._pitanje(u, s)
        if def_o.get("po_stranci") and not o["po_licima"]:
            okvir = ttk.Frame(u, style="Pozadina.TFrame")
            okvir.pack(fill="x", pady=8)
            self._oznaka(okvir, "Ова целина има питања за сваку странку — прво унесите странке.", "Sivo.TLabel").pack(side="left")
            ttk.Button(okvir, text="Странке", style="Malo.TButton", command=lambda: self.idi(LICA)).pack(side="left", padx=8)
        for lice in o["po_licima"]:
            vidljive = [s for s in lice["stavke"] if s["primenljivost"] in ("da", "nepoznato")]
            ttk.Label(u, text=f"{lice['ime']}", style="Podnaslov.TLabel").pack(anchor="w", pady=(14, 0))
            ttk.Label(u, text=f"{lice['svojstvo'] or 'својство није уписано'} · страна: {lice['strana']}",
                      style="Sivo.TLabel").pack(anchor="w", pady=(0, 4))
            for s in vidljive:
                self._pitanje(u, s)
        ceka = [s for s in sve if s["primenljivost"] == "ceka"]
        ne = [s for s in sve if s["primenljivost"] == "ne"]
        if ceka:
            ttk.Label(u, text="Зависи од другог одговора", style="Podnaslov.TLabel").pack(anchor="w", pady=(16, 2))
            for s in ceka:
                self._oznaka(u, f"• {self._sa_strankom(s)} — {s['razlog']}", "Sivo.TLabel").pack(anchor="w")
        if ne:
            v = tk.BooleanVar(value=False)
            okvir = ttk.Frame(u, style="Pozadina.TFrame")

            def prebaci():
                if v.get():
                    okvir.pack(fill="x", anchor="w")
                else:
                    okvir.pack_forget()

            ttk.Checkbutton(u, text=f"Прикажи питања која нису применљива ({len(ne)})", variable=v, command=prebaci,
                            style="Pozadina.TCheckbutton").pack(anchor="w", pady=(16, 2))
            for s in ne:
                self._oznaka(okvir, f"• {self._sa_strankom(s)} — {s['razlog']}", "Sivo.TLabel").pack(anchor="w")
        i = [x[0] for x in L.ODELJCI].index(oid)
        nav = ttk.Frame(u, style="Pozadina.TFrame")
        nav.pack(fill="x", pady=14)
        if i > 0:
            ttk.Button(nav, text="← " + L.ODELJCI[i - 1][1], command=lambda: self.idi(L.ODELJCI[i - 1][0])).pack(side="left")
        sledeca = L.ODELJCI[i + 1] if i + 1 < len(L.ODELJCI) else (SAZETAK, "Сажетак")
        ttk.Button(nav, text=sledeca[1] + " →", command=lambda: self.idi(sledeca[0])).pack(side="right")

    def _sa_strankom(self, s: dict) -> str:
        ime = next((x["ime"] for x in self.st["lica"] if x["id"] == s["sid"]), "")
        return f"{s['pitanje']} ({ime})" if ime else s["pitanje"]

    def _napomena_vidljiva(self, s: dict) -> bool:
        return bool(s["odstupa"] or s["oznaka"] == L.RADNJA or s["napomena"] or s["id"] in self._otvorene_napomene)

    def _oboji_cip(self, cip: tk.Label, status: str):
        poz, boja = BOJE_STATUSA[status]
        cip.configure(text=f" {L.STATUSI[status]} ", background=poz, foreground=boja)

    def _pitanje(self, roditelj, s: dict):
        samo = self.st["samo_citanje"]
        kart = tk.Frame(roditelj, background=KARTICA, highlightbackground=IVICA, highlightthickness=1, padx=12, pady=8)
        kart.pack(fill="x", pady=3)
        gore = tk.Frame(kart, background=KARTICA)
        gore.pack(fill="x")
        cip = tk.Label(gore, font=self.f["mali"], padx=4, pady=1)
        self._oboji_cip(cip, s["status"])
        cip.pack(side="right", padx=(8, 0))
        self._cipovi[s["id"]] = cip
        if not samo:
            mb = ttk.Menubutton(gore, text="⋯", style="Malo.TButton", width=2)
            meni = tk.Menu(mb, tearoff=False)
            meni.add_command(label="Није применљиво", command=lambda: self.radi(L.odgovori, self.c, s["id"], oznaka=L.NIJE_PRIMENLJIVO))
            meni.add_command(label="Потребна радња…", command=lambda: self._radnja(s))
            if s["oznaka"]:
                meni.add_command(label="Поништи ознаку", command=lambda: self.radi(L.odgovori, self.c, s["id"], oznaka=""))
            meni.add_separator()
            meni.add_command(label="Напомена…", command=lambda: self._otvori_napomenu(s["id"]))
            meni.add_command(label="Обриши одговор (Није проверено)", command=lambda: self.radi(L.odgovori, self.c, s["id"], None))
            mb["menu"] = meni
            mb.pack(side="right")
        lab = tk.Label(gore, text=s["pitanje"], background=KARTICA, foreground=TEKST, font=self.f["jaki"],
                       justify="left", anchor="w", wraplength=self._sirina_teksta() - 160)
        lab.pack(side="left", fill="x", expand=True)
        odgovor = tk.Frame(kart, background=KARTICA)
        odgovor.pack(fill="x", pady=(4, 0))
        if s["oznaka"]:
            tk.Label(odgovor, text=f"Означено: {L.STATUSI[s['oznaka']]}", background=KARTICA, foreground=SIVO,
                     font=self.f["kosi"]).pack(anchor="w")
        else:
            self._polje_odgovora(odgovor, s, samo)
        if s["trag"] and s["status"] != L.NIJE_PROVERENO:
            tr = s["trag"]
            ko = ", ".join(x for x in (tr.get("ime"), S.datum_vreme(tr.get("vreme", ""))) if x)
            nacin = L.NACINI.get(tr.get("nacin"), "")
            prihvacen = " · прихваћен предлог" if tr.get("poreklo") in ("podrazumevano", "uneto") else ""
            tk.Label(kart, text=f"{ko} · {nacin}{prihvacen}", background=KARTICA, foreground="#9a9ca3",
                     font=self.f["mali"]).pack(anchor="w", pady=(2, 0))
        if s["predlog"] and not samo:
            p = tk.Frame(kart, background="#eef3f9", padx=8, pady=4)
            p.pack(fill="x", pady=(6, 0))
            tk.Label(p, text=f"Предлог: {s['predlog']['prikaz']}", background="#eef3f9", foreground=NAGLASAK,
                     font=self.f["jaki"]).pack(side="left")
            tk.Label(p, text=f"  {s['predlog']['osnov']}", background="#eef3f9", foreground=SIVO,
                     font=self.f["mali"]).pack(side="left")
            ttk.Button(p, text="Прихвати", style="Malo.TButton",
                       command=lambda: self.radi(L.odgovori, self.c, s["id"], prihvati=True)).pack(side="right")
        if s["primenljivost"] == "nepoznato" and s["razlog"]:
            self._mala(kart, f"За проверу: {s['razlog']}", SIVO, self.f["kosi"])
        if s["pokriva"]:
            self._mala(kart, s["pokriva"].capitalize(), SIVO, self.f["kosi"])
        if s["uticaj"]:
            w = tk.Label(kart, text=s["uticaj"], background=UTICAJ_POZADINA, foreground=UTICAJ_TEKST, font=self.f["mali"],
                         justify="left", anchor="w", padx=8, pady=4, wraplength=self._sirina_teksta())
            w.pack(fill="x", pady=(6, 0))
            self._omotani.append(w)
        if self._napomena_vidljiva(s) and s["tip"] != "napomena":
            self._polje_napomene(kart, s, samo)
        g = tk.Label(kart, text="", background=KARTICA, foreground=CRVENO, font=self.f["mali"], anchor="w", justify="left")
        self._greske[s["id"]] = g

    def _mala(self, roditelj, tekst, boja, font):
        w = tk.Label(roditelj, text=tekst, background=KARTICA, foreground=boja, font=font, justify="left", anchor="w",
                     wraplength=self._sirina_teksta())
        w.pack(fill="x", pady=(4, 0))
        self._omotani.append(w)

    def _polje_odgovora(self, roditelj, s: dict, samo: bool):
        stanje_ = "disabled" if samo else "normal"
        tip = s["tip"]
        if tip in ("izbor", "tri", "provera"):
            trenutno = s["vrednost"] if tip != "provera" else ("да" if s["status"] == L.DA else "не" if s["status"] == L.NE else "")
            v = tk.StringVar(value=trenutno if isinstance(trenutno, str) else "")
            self._drzi.append(v)
            red = tk.Frame(roditelj, background=KARTICA)
            red.pack(anchor="w")
            for x in s["opcije"]:
                ttk.Radiobutton(red, text=x, value=x, variable=v, state=stanje_,
                                command=lambda v=v: self.radi(L.odgovori, self.c, s["id"], v.get())).pack(side="left", padx=(0, 14))
            if isinstance(trenutno, str) and trenutno and trenutno not in s["opcije"]:
                tk.Label(red, text=f"(уписано: {trenutno})", background=KARTICA, foreground=SIVO).pack(side="left")
        elif tip == "vise":
            izabrano = set(s["vrednost"] or [])
            promenljive = {}
            red = tk.Frame(roditelj, background=KARTICA)
            red.pack(anchor="w")

            def upis():
                self.radi(L.odgovori, self.c, s["id"], [x for x, v in promenljive.items() if v.get()])

            for x in s["opcije"]:
                promenljive[x] = tk.BooleanVar(value=x in izabrano)
                self._drzi.append(promenljive[x])
                ttk.Checkbutton(red, text=x, variable=promenljive[x], command=upis, state=stanje_).pack(side="left", padx=(0, 14))
        elif tip == "kvacica":
            v = tk.BooleanVar(value=s["vrednost"] == "да")
            self._drzi.append(v)
            ttk.Checkbutton(roditelj, text="означено (важи)", variable=v, state=stanje_,
                            command=lambda: self.radi(L.odgovori, self.c, s["id"], "да" if v.get() else "")).pack(anchor="w")
        elif tip == "lice":
            druga = [x for x in self.st["lica"] if x["id"] != s["sid"]]
            imena = ["—"] + [x["ime"] for x in druga]
            v = tk.StringVar(value=next((x["ime"] for x in druga if x["id"] == s["vrednost"]), "—"))
            cb = ttk.Combobox(roditelj, textvariable=v, values=imena, state="disabled" if samo else "readonly", width=34)
            cb.pack(anchor="w")
            cb.bind("<<ComboboxSelected>>", lambda _e: self.radi(
                L.odgovori, self.c, s["id"], next((x["id"] for x in druga if x["ime"] == v.get()), None)))
            if not druga:
                tk.Label(roditelj, text="(нема других унетих странака)", background=KARTICA, foreground=SIVO,
                         font=self.f["mali"]).pack(anchor="w")
        elif tip == "napomena":
            self._tekst_polje(roditelj, s, samo, s["vrednost"] or "", lambda t: self.radi(L.odgovori, self.c, s["id"], t))
        else:  # tekst, iznos, termin
            pocetno = s["vrednost"] or ""
            if tip == "termin" and pocetno:
                pocetno = s["prikaz"].replace(". у ", " ")
            v = tk.StringVar(value=pocetno)
            self._drzi.append(v)
            red = tk.Frame(roditelj, background=KARTICA)
            red.pack(anchor="w", fill="x")
            e = ttk.Entry(red, textvariable=v, width=48 if tip == "tekst" else 22, state=stanje_)
            e.pack(side="left")
            savet = {"iznos": "нпр. 85.000 или 85000,50", "termin": "датум и време, нпр. 26.11.2026 14:30"}.get(tip)
            if savet:
                tk.Label(red, text=savet, background=KARTICA, foreground=SIVO, font=self.f["mali"]).pack(side="left", padx=8)
            self._veza_polja(e, s, lambda: v.get(), pocetno)

    def _veza_polja(self, e, s: dict, citaj, pocetno: str):
        stanje = {"poslednje": pocetno}

        def upis():
            t = citaj().strip()
            if t == stanje["poslednje"].strip() or self.st["samo_citanje"]:
                return
            try:
                L.odgovori(self.c, s["id"], t)
            except L.GreskaUnosa as greska:
                self._prikazi_gresku(s["id"], str(greska))
                return
            stanje["poslednje"] = t
            self._prikazi_gresku(s["id"], "")
            self.sacuvaj()
            self.osvezi()

        e.bind("<FocusOut>", lambda _e: upis())
        e.bind("<Return>", lambda _e: upis())
        self._potvrde_polja[str(e)] = upis
        self._polja[s["id"]] = e

    def _tekst_polje(self, roditelj, s: dict, samo: bool, pocetno: str, upisi, oznaka_polja: str | None = None):
        t = tk.Text(roditelj, height=3, width=70, wrap="word", font=self.f["osnovni"], relief="flat", borderwidth=0,
                    highlightthickness=1, highlightbackground="#c9bfa8", highlightcolor=NAGLASAK, padx=4, pady=2)
        t.insert("1.0", pocetno)
        t.pack(fill="x")
        if samo:
            t.configure(state="disabled", background="#f4f4f4")
        stanje = {"poslednje": pocetno}

        def upis():
            tekst = t.get("1.0", "end").strip()
            if tekst == stanje["poslednje"].strip() or self.st["samo_citanje"]:
                return
            stanje["poslednje"] = tekst
            upisi(tekst)

        t.bind("<FocusOut>", lambda _e: upis())
        self._potvrde_polja[str(t)] = upis
        self._polja.setdefault(s["id"], t)
        return t

    def _polje_napomene(self, kart, s: dict, samo: bool):
        naslov = "Шта треба урадити" if s["oznaka"] == L.RADNJA else (
            "Напомена / разлог одступања" if s["odstupa"] else "Напомена")
        tk.Label(kart, text=naslov, background=KARTICA, foreground=SIVO, font=self.f["mali"]).pack(anchor="w", pady=(6, 0))
        t = self._tekst_polje(kart, s, samo, s["napomena"],
                              lambda tekst: self.radi(L.odgovori, self.c, s["id"], napomena=tekst))
        t.configure(height=2)
        if s["id"] in self._otvorene_napomene and not s["napomena"]:
            self.koren.after_idle(lambda: t.winfo_exists() and t.focus_set())

    def _otvori_napomenu(self, oznaka: str):
        self._otvorene_napomene.add(oznaka)
        self._prikazi(True)

    def _radnja(self, s: dict):
        self._otvorene_napomene.add(s["id"])
        self.radi(L.odgovori, self.c, s["id"], oznaka=L.RADNJA)

    def _prikazi_gresku(self, oznaka: str, poruka: str):
        g = self._greske.get(oznaka)
        if g is None or not g.winfo_exists():
            if poruka:
                messagebox.showwarning(NAZIV, poruka, parent=self.koren)
            return
        g.configure(text=poruka)
        if poruka:
            g.pack(fill="x", pady=(4, 0))
        else:
            g.pack_forget()

    # ------------------------------------------------------------ групна потврда
    def grupna_potvrda(self, posle=None):
        self._sacuvaj_otvoreno()
        spisak = L.stanje(self.c)["grupna"]
        if self.st["samo_citanje"]:
            return
        if not spisak:
            if posle:
                if messagebox.askyesno(NAZIV, "Нема предложених одговора. Парафирати „" + P.POTVRDE["primio"] + "“ као "
                                       + (self.c.get("popunio") or "") + "? Параф се не поништава.", parent=self.koren):
                    self.potvrdi_spisak([], posle)
            else:
                messagebox.showinfo(NAZIV, "Нема предложених одговора за потврду.", parent=self.koren)
            return
        DijalogPotvrde(self, spisak, posle)

    def potvrdi_spisak(self, spisak, posle=None) -> bool:
        try:
            if posle:
                posle(spisak)
            else:
                L.grupna_potvrda(self.c, spisak)
        except L.SpisakSePromenio as e:
            messagebox.showwarning(NAZIV, str(e), parent=self.koren)
            self.sacuvaj()
            self.osvezi()
            self.koren.after_idle(lambda: self.grupna_potvrda(posle))
            return False
        except L.GreskaUnosa as e:
            messagebox.showwarning(NAZIV, str(e), parent=self.koren)
            self.osvezi()
            return False
        self.sacuvaj()
        self.osvezi()
        return True

    # ------------------------------------------------------------ парафи
    def _strana_potvrda(self):
        u = self.sadrzaj.unutra
        ttk.Label(u, text="Парафи", style="Naslov.TLabel").pack(anchor="w", pady=(0, 2))
        self._oznaka(u, "Параф носи име из поља „Попунио/ла“ и време; не поништава се. „Предмет сам примила/о“ прво "
                        "показује списак предложених одговора који се тада потврђују.", "Sivo.TLabel").pack(anchor="w", pady=(0, 8))
        ko = self.st["kontrola"]
        kart = tk.Frame(u, background=KARTICA, highlightbackground=IVICA, highlightthickness=1, padx=12, pady=8)
        kart.pack(fill="x", pady=(0, 10))
        tk.Label(kart, text="КОНТРОЛА листа", background=KARTICA, foreground=TEKST, font=self.f["jaki"]).pack(anchor="w")
        for x in ko["crvene"]:
            self._mala(kart, "Црвена заставица: " + x["poruka"], CRVENO, self.f["jaki"])
        if not ko["crvene"]:
            self._mala(kart, "Црвених заставица нема.", "#2f6b3d", self.f["osnovni"])
        if ko["spremno"]:
            self._mala(kart, "Спремно за читање: да (по листу).", "#2f6b3d", self.f["osnovni"])
        else:
            self._mala(kart, "Спремно за читање: не — " + "; ".join(x["poruka"] for x in ko["nedostaje"]) + ".", SIVO, self.f["mali"])
        samo = self.st["samo_citanje"]
        for k, naziv in P.POTVRDE.items():
            red = tk.Frame(u, background=KARTICA, highlightbackground=IVICA, highlightthickness=1, padx=12, pady=6)
            red.pack(fill="x", pady=2)
            tk.Label(red, text=naziv + (" (после коначног броја)" if k in P.POTVRDE_POSLE_BROJA else ""), background=KARTICA,
                     foreground=TEKST, anchor="w").pack(side="left")
            p = self.st["potvrde"].get(k)
            if p:
                tk.Label(red, text=f"✓ {p.get('ime', '')}, {S.datum_vreme(p.get('vreme', ''))}", background=KARTICA,
                         foreground="#2f6b3d", font=self.f["jaki"]).pack(side="right")
            elif not samo:
                ttk.Button(red, text="Парафирај", style="Malo.TButton", command=lambda k=k: self.parafiraj(k)).pack(side="right")

    def parafiraj(self, k: str):
        self._sacuvaj_otvoreno()
        if not (self.c.get("popunio") or "").strip():
            messagebox.showwarning(NAZIV, "Пре парафа упишите своје име у поље „Попунио/ла“ (у заглављу).", parent=self.koren)
            self.e_popunio.focus_set()
            return
        if k == "primio":
            self.grupna_potvrda(posle=lambda spisak: L.potvrdi(self.c, "primio", spisak))
            return
        if not messagebox.askyesno(NAZIV, f"Парафирати „{P.POTVRDE[k]}“ као {self.c['popunio']}? Параф се не поништава.",
                                   parent=self.koren):
            return
        self.radi(L.potvrdi, self.c, k)

    # ------------------------------------------------------------ сажетак
    def _strana_sazetka(self):
        u = self.sadrzaj.unutra
        ttk.Label(u, text="Сажетак", style="Naslov.TLabel").pack(anchor="w", pady=(0, 2))
        self._oznaka(u, "Само изабрани подаци, по целинама и странкама, па КОНТРОЛА, последице, потребне радње и шта још "
                        "није проверено. Копирајте га (у Саву, Word, поруку) или сачувајте као Word документ.",
                     "Sivo.TLabel").pack(anchor="w", pady=(0, 8))
        dugmad = ttk.Frame(u, style="Pozadina.TFrame")
        dugmad.pack(fill="x", pady=(0, 8))
        ttk.Button(dugmad, text="Копирај сажетак", style="Glavno.TButton", command=self.kopiraj).pack(side="left")
        ttk.Button(dugmad, text="Сачувај у Word и отвори", style="Glavno.TButton", command=self.u_word).pack(side="left", padx=8)
        ttk.Button(dugmad, text="Сачувај као текст…", command=self.u_tekst).pack(side="left")
        self.l_kopirano = ttk.Label(dugmad, text="", style="Sivo.TLabel")
        self.l_kopirano.pack(side="left", padx=10)
        tekst = S.kao_tekst(S.sazetak(self.c))
        t = tk.Text(u, wrap="word", font=self.f["osnovni"], relief="solid", borderwidth=1, highlightthickness=0,
                    background=KARTICA, padx=14, pady=10,
                    height=max(12, sum(1 + len(r) // 110 for r in tekst.splitlines()) + 2))
        t.tag_configure("odeljak", font=self.f["jaki"], foreground=TEKST, spacing1=8)
        t.tag_configure("naslov", font=self.f["podnaslov"], foreground=TEKST)
        t.tag_configure("crveno", foreground=CRVENO, font=self.f["jaki"])
        t.tag_configure("sivo", foreground=SIVO)
        for i, red in enumerate(tekst.splitlines()):
            oznaka = ()
            if i == 0:
                oznaka = ("naslov",)
            elif red.isupper() and red.strip() and not red.startswith(" "):
                oznaka = ("odeljak",)
            elif "Црвена заставица" in red:
                oznaka = ("crveno",)
            elif red.startswith(("Укупно", NAZIV)):
                oznaka = ("sivo",)
            t.insert("end", red + "\n", oznaka)
        t.configure(state="disabled")
        t.pack(fill="both", expand=True)
        self.t_sazetak = t

    def _tekst_sazetka(self) -> str:
        self._sacuvaj_otvoreno()
        return S.kao_tekst(S.sazetak(self.c))

    def kopiraj(self):
        tekst = self._tekst_sazetka()
        self.koren.clipboard_clear()
        self.koren.clipboard_append(tekst)
        self.koren.update()
        if getattr(self, "l_kopirano", None) is not None and self.l_kopirano.winfo_exists():
            self.l_kopirano.configure(text="Сажетак је копиран — налепите га са Ctrl+V.")

    def u_word(self, putanja: Path | None = None, otvori: bool = True) -> Path | None:
        self._sacuvaj_otvoreno()
        if putanja is None:
            p = filedialog.asksaveasfilename(parent=self.koren, title="Сачувај сажетак у Word", defaultextension=".docx",
                                             initialdir=str(self._fascikla()), initialfile=fajl.ime_sazetka(self.c, ".docx"),
                                             filetypes=[("Word документ", "*.docx")])
            if not p:
                return None
            putanja = Path(p)
        try:
            word.sacuvaj(S.sazetak(self.c), putanja)
        except OSError as e:
            messagebox.showerror(NAZIV, f"Word документ није сачуван (да ли је отворен у Word-у?): {e}", parent=self.koren)
            return None
        if otvori:
            otvori_spolja(putanja)
        return putanja

    def u_tekst(self):
        tekst = self._tekst_sazetka()
        p = filedialog.asksaveasfilename(parent=self.koren, title="Сачувај сажетак као текст", defaultextension=".txt",
                                         initialdir=str(self._fascikla()), initialfile=fajl.ime_sazetka(self.c, ".txt"),
                                         filetypes=[("Текст", "*.txt")])
        if p:
            try:
                fajl.upisi_atomski(Path(p), tekst.replace("\n", "\r\n").encode("utf-8-sig"))
            except OSError as e:
                messagebox.showerror(NAZIV, f"Текст није сачуван: {e}", parent=self.koren)

    # ------------------------------------------------------------ остало
    def zavrsi_ili_vrati(self):
        self._sacuvaj_otvoreno()
        if self.st["samo_citanje"]:
            self.radi(L.vrati_u_rad, self.c)
        elif messagebox.askyesno(NAZIV, "Завршити чек-листу? Завршена чек-листа је само за читање док је не вратите у рад. "
                                        "Ништа се не тражи ни не претвара.", parent=self.koren):
            self.radi(L.zavrsi, self.c)

    def uputstvo(self):
        messagebox.showinfo(NAZIV, (
            "1. Програм почиње празним листом „Чек листа 23.1“ — попуњава се кликом, као на папиру (кућице, Да | Не, "
            "линије за упис).\n"
            "2. Горе: предмет (опис) и своје име у „Попунио/ла“ — име иде уз парафе.\n"
            "3. „Странке и детаљна питања →“: странке са својством и сва питања чек-листе по целинама (као у Сави).\n"
            "4. „Сагласан сам са свим осталим предложеним одговорима“ прво показује списак, па тек онда уписује.\n"
            "5. „Сажетак →“: копирајте или сачувајте у Word.\n"
            "6. „Започете чек-листе“: наставак рада на ранијој чек-листи; „Нова чек-листа“: празан лист.\n\n"
            f"Све се чува одмах, у фасцикли {fajl.fascikla()}."), parent=self.koren)

    def o_programu(self):
        messagebox.showinfo(NAZIV, f"{NAZIV} {VERZIJA}\n\nЧек-листа велике овере, издвојена из Саве: иста питања и правила, "
                                   "резултат је сажетак изабраних података.\n\nПозадина: Алфред Сисле, „Ливада“ (1875), "
                                   f"National Gallery of Art, Вашингтон — јавно власништво (као у Сави).\n\n{POTPIS}",
                            parent=self.koren)


def zaobljen(platno: tk.Canvas, x0: float, y0: float, x1: float, y1: float, r: float, **kw) -> int:
    """Правоугаоник заобљених углова (картица као у Сави) — многоугао са `smooth`."""
    tacke = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1, x0, y1,
             x0, y1 - r, x0, y0 + r, x0, y0]
    return platno.create_polygon(tacke, smooth=True, splinesteps=24, **kw)


def putanja_podatka(ime: str) -> Path:
    """Датотека из фасцикле data (и у Ceklista.exe, где је у привременој фасцикли PyInstaller-а)."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)) / "data" / ime


class Ulaz:
    """Започете чек-листе, у изгледу Саве (Сислијева „Ливада“ под крем велом): наставак рада (У раду / Завршене /
    Све) или нова чек-листа. Нова чек-листа почиње празним листом 23.1 — једини улаз у предмет."""

    KARTICA = "#fdfbf6"
    IVICA = "#e4dccb"
    FILTERI = (("u_radu", "У раду"), ("zavrsena", "Завршене"), ("sve", "Све"))

    def __init__(self, app: Aplikacija):
        self.app, k, f = app, app.koren, app.f
        self.filter = "u_radu"
        self.platno = tk.Canvas(k, background=KREM, highlightthickness=0, borderwidth=0)
        try:
            self.slika = tk.PhotoImage(file=str(putanja_podatka("livada.png")))
        except tk.TclError:
            self.slika = None
        bg = self.KARTICA
        self.f_naslov = (f["naslov"][0], 22, "bold")
        self.f_podnaslov = (f["naslov"][0], 15)
        # картица 1: нова чек-листа (празан лист 23.1) или назад на отворену
        self.k1 = tk.Frame(self.platno, background=bg, padx=18, pady=14)
        self.b_nova = tk.Button(self.k1, text="＋  Нова чек-листа", command=app.nova_cek_lista, font=f["jaki"],
                                background=NARANDZASTA, foreground="white", activebackground=NARANDZASTA_TAMNA,
                                activeforeground="white", relief="flat", borderwidth=0, padx=16, pady=7, cursor="hand2")
        self.b_nova.pack(side="left")
        self.b_nazad = tk.Button(self.k1, text="← Назад на отворену чек-листу", command=app.nazad, font=f["osnovni"],
                                 background="white", relief="solid", borderwidth=1, padx=12, pady=5, cursor="hand2")
        self.b_nazad.pack(side="left", padx=(12, 0))
        self.napomena1 = tk.Label(self.k1, background=bg, foreground="#5b6577", font=f["mali"], justify="left", anchor="w",
                                  text="Нова чек-листа почиње празним листом 23.1.")
        self.napomena1.pack(side="left", padx=(16, 0))
        # картица 2: започете чек-листе
        self.k2 = tk.Frame(self.platno, background=bg, padx=18, pady=14)
        gore = tk.Frame(self.k2, background=bg)
        gore.pack(anchor="w", fill="x")
        self.l_broj = tk.Label(gore, text="Започете чек-листе", font=(f["naslov"][0], 13, "bold"), foreground=TEKST,
                               background=bg)
        self.l_broj.pack(side="left")
        filteri = tk.Frame(self.k2, background=bg)
        filteri.pack(anchor="w", pady=(8, 8))
        self.dugmad_filtera = {}
        for kod, naziv in self.FILTERI:
            b = tk.Button(filteri, text=naziv, font=f["osnovni"], relief="solid", borderwidth=1, padx=10, pady=3,
                          background="white", activebackground="#f3efe4", cursor="hand2",
                          command=lambda kod=kod: self.postavi_filter(kod))
            b.pack(side="left", padx=(0, 6))
            self.dugmad_filtera[kod] = b
        okvir = tk.Frame(self.k2, background=bg)
        okvir.pack(fill="both", expand=True)
        kolone = (("predmet", "Предмет", 230), ("stranke", "Чија (странке)", 230), ("posao", "Правни посао", 140),
                  ("stanje", "Стање", 80), ("popunio", "Попунио/ла", 100), ("izmenjeno", "Последња измена", 150))
        self.tabela = ttk.Treeview(okvir, columns=[x[0] for x in kolone], show="headings", height=8,
                                   style="Ulaz.Treeview", selectmode="browse")
        for kol, naslov, sirina in kolone:
            self.tabela.heading(kol, text=naslov, anchor="w")
            self.tabela.column(kol, width=sirina, anchor="w", stretch=kol in ("predmet", "stranke"))
        klizac = ttk.Scrollbar(okvir, orient="vertical", command=self.tabela.yview)
        self.tabela.configure(yscrollcommand=klizac.set)
        self.tabela.pack(side="left", fill="both", expand=True)
        klizac.pack(side="right", fill="y")
        self.tabela.bind("<Double-1>", lambda _e: self.nastavi())
        self.tabela.bind("<Return>", lambda _e: self.nastavi())
        self.prazno = tk.Label(self.k2, text="Нема чек-листа у овом прегледу.", background=bg, foreground="#5b6577")
        dole = tk.Frame(self.k2, background=bg)
        dole.pack(fill="x", pady=(10, 0))
        self.b_nastavi = tk.Button(dole, text="Настави рад", command=self.nastavi, font=f["jaki"], background="white",
                                   relief="solid", borderwidth=1, padx=14, pady=4, cursor="hand2")
        self.b_nastavi.pack(side="left")
        tk.Label(dole, text=f"Чек-листе се чувају у фасцикли {fajl.fascikla()}", background=bg, foreground="#8a8f99",
                 font=f["mali"]).pack(side="left", padx=12)
        self.pomoc = (("Кратко упутство", app.uputstvo), ("О програму", app.o_programu))
        self.platno.bind("<Configure>", lambda _e: self.rasporedi())
        self._putanje: dict[str, Path] = {}

    # ------------------------------------------------------------ приказ
    def prikazi(self):
        self.osvezi_spisak()
        self.platno.pack(side="top", fill="both", expand=True)
        self.app.koren.update_idletasks()
        self.rasporedi()

    def sakrij(self):
        self.platno.pack_forget()

    def rasporedi(self):
        """Распоред на платну према величини прозора: слика у позадини (исечак око 30 % висине, као у Сави),
        колона садржаја на средини, картице заобљених углова."""
        p = self.platno
        p.delete("pozadina", "okvir", "tekst")
        sirina, visina = max(p.winfo_width(), 600), max(p.winfo_height(), 400)
        if self.slika is not None:
            p.create_image(sirina // 2, int(visina * 0.30) - int(self.slika.height() * 0.30) + self.slika.height() // 2,
                           image=self.slika, anchor="center", tags="pozadina")
        kolona = min(1040, sirina - 48)
        x = (sirina - kolona) // 2
        # наслов као у Сави („Чек-листа претходна провера за правни посао“) — текст на платну, преко слике
        naslov = p.create_text(x, 26, text="Чек-листа", anchor="nw", font=self.f_naslov, fill="#23324f", tags="tekst")
        p.create_text(p.bbox(naslov)[2] + 10, p.bbox(naslov)[3] - 6, text="започете чек-листе", anchor="sw",
                      font=self.f_podnaslov, fill="#23324f", tags="tekst")
        y = p.bbox(naslov)[3] + 16
        for w, razmak, kartica in ((self.k1, 18, True), (self.k2, 14, True)):
            if not p.find_withtag(f"w{id(w)}"):
                p.create_window(x, y, window=w, anchor="nw", width=kolona, tags=f"w{id(w)}")
            p.coords(f"w{id(w)}", x, y)
            p.itemconfigure(f"w{id(w)}", width=kolona)
            self.app.koren.update_idletasks()
            h = w.winfo_reqheight()
            if kartica:
                zaobljen(p, x - 1, y - 1, x + kolona + 1, y + h + 1, 16, fill=self.KARTICA, outline=self.IVICA,
                         width=1, tags="okvir")
            y += h + razmak
        xl = x
        for tekst, komanda in self.pomoc:
            veza = p.create_text(xl, y, text=tekst, anchor="nw", font=self.app.f["mali"], fill="#2c6aa0", tags="tekst")
            p.tag_bind(veza, "<Button-1>", lambda _e, komanda=komanda: komanda())
            p.tag_bind(veza, "<Enter>", lambda _e: p.configure(cursor="hand2"))
            p.tag_bind(veza, "<Leave>", lambda _e: p.configure(cursor=""))
            xl = p.bbox(veza)[2] + 18
        p.tag_lower("okvir")
        p.tag_lower("pozadina")

    def osvezi_spisak(self):
        liste = fajl.spisak(self.filter)
        self.l_broj.configure(text=f"Започете чек-листе  {len(liste)}")
        for kod, b in self.dugmad_filtera.items():
            izabran = kod == self.filter
            b.configure(relief="solid", borderwidth=2 if izabran else 1,
                        highlightbackground="#23324f" if izabran else self.IVICA,
                        font=self.app.f["jaki"] if izabran else self.app.f["osnovni"])
        self.tabela.delete(*self.tabela.get_children())
        self._putanje.clear()
        for x in liste:
            iid = self.tabela.insert("", "end", values=(
                x["naziv"] or "(без описа)", ", ".join(x["stranke"]) or x["kontakt"] or "—", x["posao"] or f"— {L.NEODREDJEN} —",
                x["stanje_naziv"], x["popunio"] or "—", S.datum_vreme(x["izmenjeno"])))
            self._putanje[iid] = x["putanja"]
        self.tabela.configure(height=max(3, min(10, len(liste))))
        if liste:
            self.prazno.pack_forget()
            self.tabela.selection_set(self.tabela.get_children()[0])
            self.b_nastavi.configure(state="normal", text="Настави рад" if self.filter != "zavrsena" else "Отвори")
        else:
            self.prazno.pack(anchor="w", before=self.b_nastavi.master)
            self.b_nastavi.configure(state="disabled")

    def postavi_filter(self, kod: str):
        self.filter = kod
        self.osvezi_spisak()
        self.app.koren.update_idletasks()
        self.rasporedi()

    # ------------------------------------------------------------ радње
    def nastavi(self):
        izbor = self.tabela.selection()
        if izbor and izbor[0] in self._putanje:
            self.app.otvori(self._putanje[izbor[0]])


class DijalogPotvrde(tk.Toplevel):
    """Списак предложених одговора пре групне потврде: уписује се тек на „Потврђујем наведене одговоре“."""

    def __init__(self, app: Aplikacija, spisak: list[dict], posle=None):
        super().__init__(app.koren)
        self.app, self.spisak, self.posle = app, spisak, posle
        self.title("Предложени одговори")
        self.configure(background=POZADINA, padx=14, pady=12)
        self.transient(app.koren)
        ttk.Label(self, text=f"Биће уписано као потврђено ({len(spisak)}):", style="Podnaslov.TLabel").pack(anchor="w")
        ttk.Label(self, text="Питања без предлога остају „Није проверено“.", style="Sivo.TLabel").pack(anchor="w", pady=(0, 6))
        okvir = ttk.Frame(self, style="Pozadina.TFrame")
        okvir.pack(fill="both", expand=True)
        self.tabela = ttk.Treeview(okvir, columns=("pitanje", "stranka", "odgovor", "osnov"), show="headings", height=14)
        for kol, naslov, sirina in (("pitanje", "Питање", 360), ("stranka", "Странка", 150), ("odgovor", "Одговор", 120),
                                    ("osnov", "Основ предлога", 400)):
            self.tabela.heading(kol, text=naslov)
            self.tabela.column(kol, width=sirina, anchor="w")
        for x in spisak:
            self.tabela.insert("", "end", values=(x["pitanje"], x["stranka"], x["odgovor"], x["osnov"]))
        klizac = ttk.Scrollbar(okvir, orient="vertical", command=self.tabela.yview)
        self.tabela.configure(yscrollcommand=klizac.set)
        self.tabela.pack(side="left", fill="both", expand=True)
        klizac.pack(side="right", fill="y")
        dugmad = ttk.Frame(self, style="Pozadina.TFrame")
        dugmad.pack(fill="x", pady=(10, 0))
        self.b_da = ttk.Button(dugmad, text="Потврђујем наведене одговоре", style="Glavno.TButton", command=self.potvrdi)
        self.b_da.pack(side="right")
        ttk.Button(dugmad, text="Откажи", command=self.destroy).pack(side="right", padx=8)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.update_idletasks()
        sirina, visina = min(1100, app.koren.winfo_width() - 40), min(520, app.koren.winfo_height() - 40)
        x = app.koren.winfo_rootx() + (app.koren.winfo_width() - sirina) // 2
        y = app.koren.winfo_rooty() + (app.koren.winfo_height() - visina) // 2
        self.geometry(f"{sirina}x{visina}+{max(0, x)}+{max(0, y)}")
        self.grab_set()
        self.b_da.focus_set()

    def potvrdi(self):
        spisak = [{"k": x["k"], "v": x["v"]} for x in self.spisak]
        self.destroy()
        self.app.potvrdi_spisak(spisak, self.posle)


def postavi_dpi() -> None:
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (OSError, AttributeError):
            pass


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    postavi_dpi()
    koren = tk.Tk()
    try:
        ikona = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)) / "data" / "Ceklista.ico"
        if sys.platform == "win32" and ikona.is_file():
            koren.iconbitmap(default=str(ikona))
    except tk.TclError:
        pass
    sirina, visina = min(1280, koren.winfo_screenwidth() - 40), min(860, koren.winfo_screenheight() - 80)
    koren.geometry(f"{sirina}x{visina}+20+10")
    koren.minsize(900, 560)
    Aplikacija(koren)
    koren.mainloop()
    return 0
