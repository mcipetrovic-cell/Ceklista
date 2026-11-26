"""Прозор програма „Чек-листа“ (Tkinter): странке, питања по целинама, парафи и сажетак.

Свака измена се одмах чува у датотеку чек-листе (fajl.py) — нема дугмета „Сачувај“ и ништа се не губи при
изласку. Сав рад је у једној (главној) нити; програм не користи мрежу."""

from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

from . import NAZIV, POTPIS, VERZIJA, fajl, logika as L, pitanja as P, sazetak as S, word

# ---------------------------------------------------------------- изглед (светло, пастел — као Сава)
POZADINA = "#f7f3ea"
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

LICA, POTVRDE, SAZETAK = "LICA", "POTVRDE", "SAZETAK"


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
    def __init__(self, koren: tk.Tk, putanja: Path | None = None):
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
        self._stil()
        self._napravi()
        if putanja:
            self.otvori(Path(putanja), tiho=True)
        else:
            poslednja = fajl.poslednja()
            if poslednja:
                self.otvori(poslednja, tiho=True)
        self.osvezi(sve=True)
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
        s.map("TRadiobutton", background=[("active", "#f3efe4")])
        s.map("TCheckbutton", background=[("active", "#f3efe4")])

    def _napravi(self):
        k = self.koren
        self._meni()
        z = ttk.Frame(k, style="Zaglavlje.TFrame", padding=(14, 10))
        z.pack(side="top", fill="x")
        ttk.Label(z, text=NAZIV, style="Zaglavlje.TLabel", font=self.f["naslov"]).grid(row=0, column=0, rowspan=2,
                                                                                         sticky="w", padx=(0, 18))
        ttk.Label(z, text="Предмет / опис", style="Zaglavlje.TLabel").grid(row=0, column=1, sticky="w")
        self.v_naziv = tk.StringVar()
        self.e_naziv = ttk.Entry(z, textvariable=self.v_naziv, width=34)
        self.e_naziv.grid(row=1, column=1, sticky="we", padx=(0, 12))
        ttk.Label(z, text="Правни посао", style="Zaglavlje.TLabel").grid(row=0, column=2, sticky="w")
        self.v_posao = tk.StringVar()
        self.cb_posao = ttk.Combobox(z, textvariable=self.v_posao, state="readonly", width=24,
                                     values=[L.NEODREDJEN] + list(P.POSLOVI) + ["друго"])
        self.cb_posao.grid(row=1, column=2, sticky="w", padx=(0, 12))
        ttk.Label(z, text="Попунио/ла", style="Zaglavlje.TLabel").grid(row=0, column=3, sticky="w")
        self.v_popunio = tk.StringVar()
        self.e_popunio = ttk.Entry(z, textvariable=self.v_popunio, width=22)
        self.e_popunio.grid(row=1, column=3, sticky="w", padx=(0, 12))
        self.l_stanje = ttk.Label(z, text="", style="Zaglavlje.TLabel", font=self.f["jaki"])
        self.l_stanje.grid(row=0, column=4, sticky="e")
        self.b_zavrsi = ttk.Button(z, text="Заврши чек-листу", command=self.zavrsi_ili_vrati)
        self.b_zavrsi.grid(row=1, column=4, sticky="e")
        z.columnconfigure(1, weight=1)
        z.columnconfigure(4, weight=1)
        self.e_naziv.bind("<FocusOut>", lambda e: self._sacuvaj_naziv())
        self.e_naziv.bind("<Return>", lambda e: self._sacuvaj_naziv())
        self.e_popunio.bind("<FocusOut>", lambda e: self._sacuvaj_popunio())
        self.e_popunio.bind("<Return>", lambda e: self._sacuvaj_popunio())
        self.cb_posao.bind("<<ComboboxSelected>>", lambda e: self.radi(L.postavi_posao, self.c, self.v_posao.get()))

        ttk.Label(k, text=f"{NAZIV} {VERZIJA} · {POTPIS}", style="Sivo.TLabel", anchor="center").pack(side="bottom", fill="x")
        dno = ttk.Frame(k, style="Pozadina.TFrame", padding=(14, 6))
        dno.pack(side="bottom", fill="x")
        self.brojaci = ttk.Frame(dno, style="Pozadina.TFrame")
        self.brojaci.pack(side="left")
        self.b_grupno = ttk.Button(dno, text="Сагласан сам са свим осталим предложеним одговорима",
                                   command=self.grupna_potvrda)
        self.b_grupno.pack(side="right")

        telo = ttk.Frame(k, style="Pozadina.TFrame")
        telo.pack(side="top", fill="both", expand=True)
        levo = ttk.Frame(telo, style="Pozadina.TFrame", padding=(10, 10, 4, 10))
        levo.pack(side="left", fill="y")
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
        k.bind_all("<Control-n>", lambda e: self.nova())
        k.bind_all("<Control-o>", lambda e: self.otvori_dijalog())

    def _tocak_strane(self, e):
        self.sadrzaj._tocak(e)
        return "break"

    def _meni(self):
        m = tk.Menu(self.koren)
        d = tk.Menu(m, tearoff=False)
        d.add_command(label="Нова чек-листа", accelerator="Ctrl+N", command=self.nova)
        d.add_command(label="Отвори…", accelerator="Ctrl+O", command=self.otvori_dijalog)
        self.m_skorasnje = tk.Menu(d, tearoff=False, postcommand=self._napuni_skorasnje)
        d.add_cascade(label="Скорашње", menu=self.m_skorasnje)
        d.add_command(label="Сачувај копију као…", command=self.sacuvaj_kao)
        d.add_command(label="Отвори фасциклу чек-листа", command=lambda: otvori_spolja(self._fascikla()))
        d.add_separator()
        d.add_command(label="Излаз", command=self.zatvori)
        m.add_cascade(label="Датотека", menu=d)
        c = tk.Menu(m, tearoff=False)
        c.add_command(label="Странке", command=lambda: self.idi(LICA))
        c.add_command(label="Парафи", command=lambda: self.idi(POTVRDE))
        c.add_command(label="Сажетак", command=lambda: self.idi(SAZETAK))
        c.add_separator()
        c.add_command(label="Сагласан сам са свим осталим предложеним одговорима…", command=self.grupna_potvrda)
        c.add_command(label="Заврши чек-листу / врати у рад", command=self.zavrsi_ili_vrati)
        m.add_cascade(label="Чек-листа", menu=c)
        p = tk.Menu(m, tearoff=False)
        p.add_command(label="Кратко упутство", command=self.uputstvo)
        p.add_command(label="О програму", command=self.o_programu)
        m.add_cascade(label="Помоћ", menu=p)
        self.koren.configure(menu=m)

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
            fajl.zapamti_otvorenu(self.putanja)
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
        """Поље у коме се управо куца уписује се пре изласка, отварања друге чек-листе и сажетка."""
        w = self.koren.focus_get()
        upis = self._potvrde_polja.get(str(w)) if w is not None else None
        if upis:
            upis()
        if w is self.e_naziv:
            self._sacuvaj_naziv()
        if w is self.e_popunio:
            self._sacuvaj_popunio()

    # ------------------------------------------------------------ датотеке
    def nova(self):
        self._sacuvaj_otvoreno()
        self.c, self.putanja = L.nova(), None
        self._otvorene_napomene.clear()
        fajl.zapamti_otvorenu(None)
        self.izbor = LICA
        self.osvezi(sve=True)

    def otvori(self, putanja: Path, tiho: bool = False) -> bool:
        try:
            c = fajl.ucitaj(putanja)
        except L.GreskaUnosa as e:
            if not tiho:
                messagebox.showwarning(NAZIV, str(e), parent=self.koren)
            return False
        self.c, self.putanja = c, Path(putanja)
        self._otvorene_napomene.clear()
        fajl.zapamti_otvorenu(self.putanja)
        self.izbor = LICA if not c["lica"] else self.izbor
        self.osvezi(sve=True)
        return True

    def otvori_dijalog(self):
        self._sacuvaj_otvoreno()
        fascikla = self._fascikla()
        fascikla.mkdir(parents=True, exist_ok=True)
        p = filedialog.askopenfilename(parent=self.koren, title="Отвори чек-листу", initialdir=str(fascikla),
                                       filetypes=[("Чек-листа", "*" + fajl.EKSTENZIJA), ("Све датотеке", "*.*")])
        if p:
            self.otvori(Path(p))

    def _napuni_skorasnje(self):
        self.m_skorasnje.delete(0, "end")
        sk = fajl.skorasnje()
        if not sk:
            self.m_skorasnje.add_command(label="(нема)", state="disabled")
        for p in sk:
            self.m_skorasnje.add_command(label=p.stem, command=lambda p=p: (self._sacuvaj_otvoreno(), self.otvori(p)))

    def sacuvaj_kao(self):
        self._sacuvaj_otvoreno()
        p = filedialog.asksaveasfilename(parent=self.koren, title="Сачувај копију чек-листе", defaultextension=fajl.EKSTENZIJA,
                                         initialdir=str(self._fascikla()), initialfile=fajl.novo_ime(self.c).name,
                                         filetypes=[("Чек-листа", "*" + fajl.EKSTENZIJA)])
        if p:
            try:
                fajl.sacuvaj(self.c, Path(p))
            except OSError as e:
                messagebox.showerror(NAZIV, f"Копија није сачувана: {e}", parent=self.koren)
                return
            self.putanja = Path(p)
            fajl.zapamti_otvorenu(self.putanja)
            self.osvezi()

    def zatvori(self):
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
        self.l_stanje.configure(text=f"Стање: {self.st['stanje_naziv']}", foreground="#2f6b3d" if samo else TEKST)
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
        stavke = [(LICA, f"Странке ({len(self.st['lica'])})")]
        for o in self.st["odeljci"]:
            n = self._otvoreno_u(o["id"])
            vazi = any(s["primenljivost"] != "ne" for s in self.st["sve"] if s["odeljak"] == o["id"])
            stavke.append((o["id"], o["naslov"] + (f"  · отворено {n}" if n else ("  ✓" if vazi else ""))))
        stavke += [(POTVRDE, f"Парафи ({len(self.st['potvrde'])}/{len(P.POTVRDE)})"), (SAZETAK, "Сажетак")]
        self._stavke_liste = [x[0] for x in stavke]
        self.lista.delete(0, "end")
        for i, (oid, tekst) in enumerate(stavke):
            self.lista.insert("end", "  " + tekst)
            if oid in (LICA, SAZETAK, POTVRDE):
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
        if self.izbor == LICA:
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
        def_o = next((x for x in P.DEFINICIJA if x["id"] == oid), {})
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
            "1. У заглављу упишите предмет (нпр. ОПУ 12/2026 или презиме странке), изаберите правни посао и своје име.\n"
            "2. „Странке“: унесите странке са својством (продавац, купац…).\n"
            "3. Пролазите целине лево. Свако питање има пет статуса: Да, Не, Није применљиво, Није проверено, "
            "Потребна радња (дугме ⋯ уз питање). Предлог није одговор док га не прихватите.\n"
            "4. „Сагласан сам са свим осталим предложеним одговорима“ прво показује списак, па тек онда уписује.\n"
            "5. „Сажетак“: копирајте или сачувајте у Word.\n\n"
            f"Све се чува одмах, у фасцикли {fajl.fascikla()}."), parent=self.koren)

    def o_programu(self):
        messagebox.showinfo(NAZIV, f"{NAZIV} {VERZIJA}\n\nЧек-листа велике овере, издвојена из Саве: иста питања и правила, "
                                   f"резултат је сажетак изабраних података.\n\n{POTPIS}", parent=self.koren)


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
    putanja = next((Path(a) for a in argv if a.lower().endswith(fajl.EKSTENZIJA)), None)
    Aplikacija(koren, putanja)
    koren.mainloop()
    return 0
