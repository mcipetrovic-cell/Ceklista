"""Сажетак чек-листе: само подаци који су стварно изабрани, по целинама и по странкама, па КОНТРОЛА, последице,
потребне радње и шта још није проверено.

Шта улази у сажетак као одговор: питање које важи (или је „за проверу“) и има одговор „Да“ / „Не“ или унет податак;
неозначена кућица под-ставке се не наводи (то није избор). Питања која сигурно не важе се само броје, а она која је
запослени сам означио „Није применљиво“ наводе се поименце. Напомена уз питање о сумњи у прање новца се не преноси у
сажетак (сажетак се може копирати и штампати; одговор на само питање остаје).
"""

from __future__ import annotations

import datetime as dt

from . import NAZIV, POTPIS, VERZIJA_BROJ, logika as L, pitanja as P

VRSTE = (
    ("crvene", "КОНТРОЛА — црвене заставице"),
    ("uticaj", "Последице и упозорења"),
    ("doslednost", "Доследност одговора"),
    ("word", "За израду исправе у Word-у"),
    ("nedostaje", "Недостаје напомена"),
)


def datum_vreme(iso: str) -> str:
    try:
        d = dt.datetime.fromisoformat(str(iso))
    except (TypeError, ValueError):
        return ""
    return f"{d:%d.%m.%Y}. у {d:%H.%M}"


def _izabrano(s: dict) -> bool:
    if s["primenljivost"] not in ("da", "nepoznato") or s["status"] not in (L.DA, L.NE):
        return False
    if s["tip"] == "kvacica":
        return s["status"] == L.DA
    if s["tip"] == "provera":
        return True
    return s["vrednost"] not in (None, "", [])


def _red(s: dict, stranka: str = "") -> dict:
    odgovor = s["prikaz"] or ("да" if s["status"] == L.DA else "не")
    return {"id": s["id"], "pitanje": s["pitanje"], "odgovor": odgovor, "stranka": stranka,
            "napomena": "" if s["poverljivo"] else s["napomena"]}


def _sa_strankom(s: dict, imena: dict) -> str:
    return f"{s['pitanje']} ({imena[s['sid']]})" if s["sid"] else s["pitanje"]


def sazetak(c: dict) -> dict:
    """Сажетак као речник (за текст, Word и приказ у прозору)."""
    st = L.stanje(c)
    imena = {x["id"]: x["ime"] for x in st["lica"]}
    odg = c.get("odgovori") or {}
    zaglavlje = {
        "naziv": st["naziv"],
        "posao": st["posao"] or L.NEODREDJEN,
        "forma": odg.get("forma") or "није одређена",
        "stanje": st["stanje_naziv"],
        "popunio": st["popunio"],
        "izmenjeno": datum_vreme(c.get("izmenjeno") or ""),
        "zavrseno": datum_vreme(c.get("zavrseno") or "") if st["stanje"] == "zavrsena" else "",
    }
    stranke = []
    for x in st["lica"]:
        opis = x["svojstvo"] or "својство није уписано"
        stranke.append(f"{x['ime']} — {opis} ({x['strana']})" + (", правно лице" if x["pravno_lice"] else ""))
    odeljci = []
    for o in st["odeljci"]:
        redovi = [_red(s) for s in o["opsta"] if _izabrano(s)]
        po_licima = []
        for lice in o["po_licima"]:
            r = [_red(s, lice["ime"]) for s in lice["stavke"] if _izabrano(s)]
            if r:
                po_licima.append({"ime": lice["ime"], "redovi": r})
        if redovi or po_licima:
            odeljci.append({"naslov": o["naslov"], "redovi": redovi, "po_licima": po_licima})
    vazece = [s for s in st["sve"] if s["primenljivost"] in ("da", "nepoznato")]
    radnje = [{"pitanje": _sa_strankom(s, imena), "sta": "" if s["poverljivo"] else s["napomena"]}
              for s in vazece if s["status"] == L.RADNJA]
    obavezna = {u["polje"] for u in st["upozorenja"] if u["vrsta"] == "obavezno"}
    naslovi = {o["id"]: o["naslov"] for o in st["odeljci"]}
    neprovereno: list[dict] = []  # по целини и странци: [{odeljak, stranka, pitanja}]
    for s in vazece:
        if s["status"] != L.NIJE_PROVERENO or s["pokriva"] or s["tip"] == "kvacica":
            continue
        tekst = s["pitanje"] + (" (обавезно)" if s["id"] in obavezna else "") + \
            (" (за проверу)" if s["primenljivost"] == "nepoznato" else "")
        grupa = (naslovi[s["odeljak"]], imena.get(s["sid"], ""))
        if not neprovereno or (neprovereno[-1]["odeljak"], neprovereno[-1]["stranka"]) != grupa:
            neprovereno.append({"odeljak": grupa[0], "stranka": grupa[1], "pitanja": []})
        neprovereno[-1]["pitanja"].append(tekst)
    oznaceno_np = [_sa_strankom(s, imena) for s in st["sve"] if s["oznaka"] == L.NIJE_PRIMENLJIVO]
    ko = st["kontrola"]
    upozorenja = {v: [] for v, _ in VRSTE}
    upozorenja["crvene"] = [x["poruka"] for x in ko["crvene"]]
    for u in st["upozorenja"]:
        if u["vrsta"] == "obavezno":
            continue  # обавезно питање без одговора је у „Није проверено“, означено „(обавезно)“
        vrsta = "nedostaje" if u["vrsta"] == "napomena" else u["vrsta"]
        if u["poruka"] not in upozorenja[vrsta]:
            upozorenja[vrsta].append(u["poruka"])
    potvrde = [{"naziv": P.POTVRDE[k], "ime": v.get("ime", ""), "vreme": datum_vreme(v.get("vreme", ""))}
               for k, v in (st["potvrde"] or {}).items() if k in P.POTVRDE]
    return {"zaglavlje": zaglavlje, "stranke": stranke, "odeljci": odeljci, "radnje": radnje,
            "neprovereno": neprovereno, "oznaceno_np": oznaceno_np, "brojaci": st["brojaci"],
            "spremno": ko["spremno"], "nedostaje_za_citanje": [x["poruka"] for x in ko["nedostaje"]],
            "upozorenja": upozorenja, "potvrde": potvrde}


def _zaglavlje_redovi(s: dict) -> list[str]:
    z = s["zaglavlje"]
    redovi = []
    if z["naziv"]:
        redovi.append(f"Предмет: {z['naziv']}")
    redovi.append(f"Правни посао: {z['posao']} · Врста исправе: {z['forma']}")
    dodatak = [f"Стање: {z['stanje']}" + (f" ({z['zavrseno']})" if z["zavrseno"] else "")]
    if z["popunio"]:
        dodatak.append(f"Попунио/ла: {z['popunio']}")
    if z["izmenjeno"]:
        dodatak.append(f"последња измена {z['izmenjeno']}")
    redovi.append(" · ".join(dodatak))
    return redovi


def _odgovor(r: dict) -> str:
    return f"{r['pitanje']}: {r['odgovor']}" + (f" — напомена: {r['napomena']}" if r["napomena"] else "")


def brojaci_tekst(b: dict) -> str:
    return " · ".join(f"{naziv} {b.get(k, 0)}" for k, naziv in L.STATUSI.items())


def delovi(s: dict) -> list[tuple[str, object]]:
    """Сажетак као низ (врста, садржај) — исти редослед за текст и за Word.
    Врсте: naslov, podnaslov, odeljak, lice, stavka, crveno, napomena, ukupno, potpis."""
    out: list[tuple[str, object]] = [("naslov", "ЧЕК-ЛИСТА — САЖЕТАК")]
    out += [("podnaslov", r) for r in _zaglavlje_redovi(s)]
    out.append(("odeljak", "Странке"))
    out += [("stavka", x) for x in s["stranke"]] or [("napomena", "Странке нису унете.")]
    for o in s["odeljci"]:
        out.append(("odeljak", o["naslov"]))
        out += [("stavka", _odgovor(r)) for r in o["redovi"]]
        for lice in o["po_licima"]:
            out.append(("lice", lice["ime"]))
            out += [("stavka", _odgovor(r)) for r in lice["redovi"]]
    if not s["odeljci"]:
        out += [("odeljak", "Одговори"), ("napomena", "Још ниједно питање нема одговор.")]
    out.append(("odeljak", "КОНТРОЛА"))
    if s["upozorenja"]["crvene"]:
        out += [("crveno", "Црвена заставица: " + x) for x in s["upozorenja"]["crvene"]]
    else:
        out.append(("stavka", "Црвених заставица нема."))
    if s["spremno"]:
        out.append(("stavka", "Спремно за читање: да (по листу)."))
    else:
        bez = [x for x in s["nedostaje_za_citanje"] if x.startswith("без одговора: ")]
        ostalo = [x for x in s["nedostaje_za_citanje"] if not x.startswith("без одговора: ")]
        razlozi = ([f"без одговора {len(bez)} " + ("питање" if len(bez) == 1 else "питања") + " листа"] if bez else []) + ostalo
        out.append(("stavka", "Спремно за читање: не — " + "; ".join(razlozi) + "."))
    for vrsta, naslov in VRSTE[1:]:
        if s["upozorenja"][vrsta]:
            out.append(("odeljak", naslov))
            out += [("stavka", x) for x in s["upozorenja"][vrsta]]
    if s["radnje"]:
        out.append(("odeljak", f"Потребна радња ({len(s['radnje'])})"))
        out += [("stavka", r["pitanje"] + (f": {r['sta']}" if r["sta"] else " — шта треба урадити није уписано"))
                for r in s["radnje"]]
    if s["oznaceno_np"]:
        out.append(("odeljak", "Означено као „Није применљиво“"))
        out += [("stavka", x) for x in s["oznaceno_np"]]
    if s["neprovereno"]:
        ukupno = sum(len(g["pitanja"]) for g in s["neprovereno"])
        out.append(("odeljak", f"Није проверено ({ukupno})"))
        out += [("stavka", g["odeljak"] + (f" — {g['stranka']}" if g["stranka"] else "") + ": " + "; ".join(g["pitanja"]))
                for g in s["neprovereno"]]
    if s["potvrde"]:
        out.append(("odeljak", "Парафи"))
        out += [("stavka", f"{p['naziv']} — {p['ime']}, {p['vreme']}") for p in s["potvrde"]]
    out.append(("ukupno", "Укупно: " + brojaci_tekst(s["brojaci"]) + "."))
    out.append(("potpis", f"{NAZIV} {VERZIJA_BROJ} · {POTPIS}"))
    return out


def kao_tekst(s: dict) -> str:
    """Обичан текст (за копирање у Саву, Word или поруку)."""
    redovi: list[str] = []
    uvlaka = "  "
    for vrsta, sadrzaj in delovi(s):
        if vrsta in ("naslov", "podnaslov"):
            redovi.append(str(sadrzaj))
        elif vrsta == "odeljak":
            redovi += ["", str(sadrzaj).upper()]
            uvlaka = "  "
        elif vrsta == "lice":
            redovi.append(f"  {sadrzaj}:")
            uvlaka = "    "
        elif vrsta in ("stavka", "crveno"):
            redovi.append(f"{uvlaka}• {sadrzaj}")
        elif vrsta == "ukupno":
            redovi += ["", str(sadrzaj)]
        elif vrsta == "potpis":
            redovi.append(str(sadrzaj))
        else:
            redovi.append(f"  {sadrzaj}")
    return "\n".join(redovi).strip() + "\n"
