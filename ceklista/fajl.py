"""Чување чек-листе: свака чек-листа је једна датотека .ceklista (JSON), сачувана после сваке измене.

- Подразумевана фасцикла: Документи\\Чек-листе (на Windows-у права фасцикла „Документи“, и кад је у OneDrive-у).
- Списак започетих набраја чек-листе из те фасцикле (spisak); ознака `.otvorena` у истој фасцикли памти која је
  чек-листа била отворена, па се при новом покретању наставља (otvorena). Програм нема других подешавања.
- Упис је атомски (привремена датотека, па замена): прекид струје не оставља пола датотеке.
За пробе: CEKLISTA_FASCIKLA замењује фасциклу чек-листа."""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import tempfile
from pathlib import Path

from . import logika as L

EKSTENZIJA = ".ceklista"
NAJVECA_DATOTEKA = 5 * 1024 * 1024


def upisi_atomski(putanja: Path, bajtovi: bytes) -> None:
    putanja = Path(putanja)
    putanja.parent.mkdir(parents=True, exist_ok=True)
    fd, privremena = tempfile.mkstemp(prefix=".~", suffix=".tmp", dir=str(putanja.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(bajtovi)
            f.flush()
            os.fsync(f.fileno())
        os.replace(privremena, putanja)
    except BaseException:
        try:
            os.unlink(privremena)
        except OSError:
            pass
        raise


def _windows_dokumenti() -> Path | None:
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        bafer = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, bafer) == 0 and bafer.value:  # CSIDL_PERSONAL
            return Path(bafer.value)
    except (OSError, AttributeError):
        return None
    return None


def dokumenti() -> Path:
    win = _windows_dokumenti()
    if win:
        return win
    kuca = Path.home()
    return kuca / "Documents" if (kuca / "Documents").is_dir() else kuca


def fascikla() -> Path:
    izbor = os.environ.get("CEKLISTA_FASCIKLA")
    return Path(izbor) if izbor else dokumenti() / "Чек-листе"


def _bezbedno_ime(tekst: str) -> str:
    t = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', " ", str(tekst or ""))
    t = " ".join(t.split()).strip(" .")
    return t[:80]


def novo_ime(c: dict, u: Path | None = None) -> Path:
    """„Чек-листа <опис> 26.11.2026 14.30.ceklista“ у фасцикли чек-листа; не замењује постојећу."""
    u = Path(u) if u else fascikla()
    opis = _bezbedno_ime(c.get("naziv") or "")
    osnova = "Чек-листа" + (f" {opis}" if opis else "") + f" {dt.datetime.now():%d.%m.%Y %H.%M}"
    putanja, n = u / f"{osnova}{EKSTENZIJA}", 2
    while putanja.exists():
        putanja, n = u / f"{osnova} ({n}){EKSTENZIJA}", n + 1
    return putanja


def ime_sazetka(c: dict, nastavak: str) -> str:
    opis = _bezbedno_ime(c.get("naziv") or "")
    return ("Сажетак чек-листе" + (f" {opis}" if opis else "") + f" {dt.datetime.now():%d.%m.%Y %H.%M}{nastavak}")


def sacuvaj(c: dict, putanja: Path) -> Path:
    putanja = Path(putanja)
    upisi_atomski(putanja, json.dumps(c, ensure_ascii=False, indent=1).encode("utf-8"))
    return putanja


def _recnik(x) -> dict:
    return x if isinstance(x, dict) else {}


def sredi(d) -> dict:
    """Проверена чек-листа из прочитаног JSON-а; недостајући делови добијају празну вредност."""
    if not isinstance(d, dict) or d.get("format") != L.FORMAT:
        raise L.GreskaUnosa("Ово није датотека чек-листе.")
    if int(d.get("verzija_formata") or 0) > L.VERZIJA_FORMATA:
        raise L.GreskaUnosa("Чек-листа је сачувана новијом верзијом програма — преузмите нову верзију Ceklista.exe.")
    c = L.nova()
    for k in ("naziv", "popunio", "napravljeno", "izmenjeno", "zavrseno"):
        if isinstance(d.get(k), str):
            c[k] = d[k]
    c["stanje"] = d.get("stanje") if d.get("stanje") in L.STANJA else "u_radu"
    lica = []
    for x in d.get("lica") or []:
        if isinstance(x, dict) and str(x.get("id") or "").strip() and "." not in str(x["id"]):
            lica.append({"id": str(x["id"]), "ime": str(x.get("ime") or ""), "svojstvo": str(x.get("svojstvo") or ""),
                         "pravno_lice": bool(x.get("pravno_lice"))})
    c["lica"] = lica
    c["odgovori"] = _recnik(d.get("odgovori"))
    c["stranke"] = {str(k): v for k, v in _recnik(d.get("stranke")).items() if isinstance(v, dict)}
    c["oznake"] = {str(k): v for k, v in _recnik(d.get("oznake")).items() if v in L.OZNAKE}
    c["modul"] = {str(k): v for k, v in _recnik(d.get("modul")).items() if v in L.STATUSI}
    c["trag"] = {str(k): v for k, v in _recnik(d.get("trag")).items() if isinstance(v, dict)}
    c["potvrde"] = {str(k): v for k, v in _recnik(d.get("potvrde")).items() if isinstance(v, dict)}
    return c


def ucitaj(putanja: Path) -> dict:
    putanja = Path(putanja)
    try:
        if putanja.stat().st_size > NAJVECA_DATOTEKA:
            raise L.GreskaUnosa("Датотека је превелика за чек-листу.")
        d = json.loads(putanja.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise L.GreskaUnosa(f"Чек-листа не постоји: {putanja}") from None
    except (OSError, UnicodeDecodeError, ValueError):
        raise L.GreskaUnosa(f"Чек-листа не може да се прочита (оштећена датотека): {putanja.name}") from None
    return sredi(d)


# ---------------------------------------------------------------- отворена чек-листа (наставак при покретању)
OTVORENA = ".otvorena"  # у фасцикли чек-листа: име датотеке која је била отворена кад је програм затворен


def zapamti_otvorenu(putanja: Path | None, u: Path | None = None) -> None:
    oznaka = (Path(u) if u else fascikla()) / OTVORENA
    try:
        if putanja is None:
            oznaka.unlink(missing_ok=True)
        else:
            upisi_atomski(oznaka, str(Path(putanja).resolve()).encode("utf-8"))
    except OSError:
        pass  # ознака није битна за податке: чек-листа је већ сачувана у својој датотеци


def otvorena(u: Path | None = None) -> Path | None:
    """Чек-листа која је била отворена при затварању програма, ако још постоји и у раду је; иначе None."""
    oznaka = (Path(u) if u else fascikla()) / OTVORENA
    try:
        putanja = Path(oznaka.read_text(encoding="utf-8").strip())
        return putanja if putanja.is_file() and ucitaj(putanja)["stanje"] == "u_radu" else None
    except (OSError, ValueError, L.GreskaUnosa):
        return None


# ---------------------------------------------------------------- започете чек-листе (почетни екран)

def spisak(stanje: str = "u_radu", u: Path | None = None) -> list[dict]:
    """Чек-листе из фасцикле, новије прве: [{putanja, naziv, stranke, posao, stanje, stanje_naziv, popunio,
    izmenjeno}]. stanje: u_radu, zavrsena или sve. Датотека која се не може прочитати се прескаче."""
    u = Path(u) if u else fascikla()
    out = []
    for putanja in sorted(u.glob("*" + EKSTENZIJA)) if u.is_dir() else []:
        try:
            c = ucitaj(putanja)
        except L.GreskaUnosa:
            continue
        if stanje != "sve" and c["stanje"] != stanje:
            continue
        out.append({"putanja": putanja, "naziv": c["naziv"], "stranke": [L.ime_lica(x) for x in c["lica"]],
                    "kontakt": str(c["odgovori"].get("kontakt") or ""),
                    "posao": c["odgovori"].get("posao") or "", "stanje": c["stanje"],
                    "stanje_naziv": L.STANJA[c["stanje"]], "popunio": c["popunio"], "izmenjeno": c["izmenjeno"]})
    return sorted(out, key=lambda x: x["izmenjeno"], reverse=True)
