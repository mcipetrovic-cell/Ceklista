"""Правила чек-листе — иста као у Сави (`sava_app/cek_lista.py` и `cek_lista_modul.py`), без базе предмета.

Питања, предлози, последице и правила контроле су препис из Саве (`pitanja.py`). Овде су пренета само правила која
не траже предмет у бази: видљивост и применљивост питања (да / не / не зна се / чека), пет статуса, предложени
одговори са пореклом, групна потврда виђеног списка, упозорења и доследност одговора, КОНТРОЛА листа и парафи.

Што Сава ради уз податке из предмета, а овај програм не може (нема их): предлози из личних исправа очитаних читачем,
из катастра (Сноп), из Агенде и из картице странке; попис прилога; веза са Word обрасцима. Та питања остају обична
питања на која запослени одговара сам.

Чек-листа је обичан речник (чува се као JSON у датотеци .ceklista, види fajl.py):

- naziv — ознака предмета или кратак опис; popunio — ко попуњава (име иде уз парафе);
- lica — странке [{id, ime, svojstvo, pravno_lice}]; страна у послу (располаже / стиче) следи својство;
- odgovori — општи одговори {кључ: вредност}, ту је и „posao“ (правни посао); stranke — {id странке: {кључ: вредност}};
- напомена уз питање: odgovori[кључ + "__napomena"], за странку stranke[id][кључ + "__napomena"] (као у Сави);
- oznake — {ознака питања: nije_primenljivo | potrebna_radnja}; modul — {провера непокретности: статус};
- trag — {ознака питања: {vreme, nacin, poreklo, ime}}; potvrde — {параф: {ime, vreme}};
- stanje (u_radu | zavrsena), napravljeno, izmenjeno, zavrseno.

Ознака питања: „кључ“ за опште питање, „<id странке>.кључ“ за питање по странци.
"""

from __future__ import annotations

import datetime as dt
import re

from . import pitanja as P

DA, NE, NIJE_PRIMENLJIVO, NIJE_PROVERENO, RADNJA = "da", "ne", "nije_primenljivo", "nije_provereno", "potrebna_radnja"
STATUSI = dict(P.STATUSI_MODULA)
OZNAKE = (NIJE_PRIMENLJIVO, RADNJA)  # статуси које запослени поставља без вредности одговора
POREKLA = {"izvor": "податак из проверљивог извора", "uneto": "податак који је корисник раније унео",
           "podrazumevano": "подразумевани предложени одговор", "proveriti": "чињеница коју корисник посебно проверава",
           "nije_primenljivo": "питање које није применљиво"}
NACINI = {"pojedinacno": "појединачно", "grupno": "групно"}
STANJA = {"u_radu": "у раду", "zavrsena": "завршена"}
NAPOMENA = P.NAPOMENA
NESIGURNO = P.NESIGURNO
FORMAT, VERZIJA_FORMATA = "ceklista", 1
NEODREDJEN = "још није одређен"  # приказ празног правног посла
NEP = "NEP"  # целина провере непокретности (питања само из модула Саве)
BEZ_KATASTRA = "програм нема податке катастра — проверите у листу непокретности"


class GreskaUnosa(Exception):
    """Порука за запосленог (ћирилицом); ништа није уписано."""


class SpisakSePromenio(GreskaUnosa):
    """Групна потврда без виђеног списка, или се списак у међувремену променио; носи важећи списак."""

    def __init__(self, poruka: str, spisak: list):
        super().__init__(poruka)
        self.spisak = spisak


def sada() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------- питања

def _pitanja(deo: str):
    for o in P.DEFINICIJA:
        for q in o.get(deo, []):
            yield o, q


OPSTA = {q["k"]: (o, q) for o, q in _pitanja("pitanja")}
PO_STRANCI = {q["k"]: (o, q) for o, q in _pitanja("po_stranci")}
ODELJCI = [(o["id"], o["odeljak"]) for o in P.DEFINICIJA] + [(NEP, "Провера непокретности")]


def kljuc(k: str, sid: str = "") -> str:
    return f"{sid}.{k}" if sid else k


def rastavi(oznaka: str) -> tuple[str, str]:
    """(кључ питања, странка) из „k“ или „<странка>.k“."""
    sid, tacka, k = str(oznaka).rpartition(".")
    return (k, sid) if tacka else (str(oznaka), "")


def _uslovi(uslov) -> list:
    if not uslov:
        return []
    if isinstance(uslov[0], (list, tuple)):
        return [(k, v) for k, v in uslov]
    return [(uslov[0], uslov[1])]


def vidljivo(uslov, odgovori: dict, opsti: dict | None = None) -> bool:
    """Услов приказа (као cek_lista._vidljivo): сваки услов мора да важи; „*“ — било шта изабрано."""
    for k, dozvoljeno in _uslovi(uslov):
        v = odgovori.get(k, (opsti or {}).get(k))
        if dozvoljeno == "*":
            if not v:
                return False
            continue
        dozvoljeno = dozvoljeno if isinstance(dozvoljeno, (list, tuple)) else [dozvoljeno]
        if isinstance(v, list) and not set(v) & set(dozvoljeno) or not isinstance(v, list) and v not in dozvoljeno:
            return False
    return True


def pitanje(k: str) -> dict:
    """Питање по кључу; „ako“ спаја услов целине и питања (као cek_lista.pitanje)."""
    for o in P.DEFINICIJA:
        for q in (o.get("pitanja") or []) + (o.get("po_stranci") or []):
            if q["k"] == k:
                uslovi = [list(x) for x in _uslovi(o.get("ako"))] + [list(x) for x in _uslovi(q.get("ako"))]
                if k in P.UZ_ZAPIS_2020:
                    uslovi.append(list(P.SAMO_ZAPIS))
                return {**q, "ako": uslovi[0] if len(uslovi) == 1 else (uslovi or None)}
    raise KeyError(k)


def binarno(q: dict) -> bool:
    if q["tip"] in ("tri", "kvacica", "provera"):
        return True
    return q["tip"] == "izbor" and {str(x).casefold() for x in q["o"]} <= {"да", "не", *NESIGURNO}


def opcije(q: dict) -> list[str]:
    """Понуђени одговори: „није утврђено“ / „потребна провера“ нису одговор — то су статуси (као у модулу Саве)."""
    if q["tip"] == "tri":
        return ["да", "не"]
    if q["tip"] in ("izbor", "vise"):
        return [x for x in q["o"] if x not in NESIGURNO]
    return []


def status_vrednosti(q: dict | None, v, oznaka: str | None = None) -> str:
    """Један од пет статуса. Празно је „Није проверено“ — никад „да“ ни „не“; изузетак је кућица под-ставке
    (tip „kvacica“): неозначена значи „не важи“ (одговор јавног бележника 14)."""
    if oznaka in OZNAKE:
        return oznaka
    if q and q["tip"] == "kvacica":
        return DA if v == "да" else NE
    if v in (None, "", []):
        return NIJE_PROVERENO
    if isinstance(v, str):
        if v == "потребна провера":
            return RADNJA
        if v in ("није утврђено", "није проверено"):
            return NIJE_PROVERENO
        if v.casefold() == "не":
            return NE
    return DA


def predlog(k: str, posao: str = "продаја") -> str | None:
    return (P.PREDLOZI.get(posao) or {}).get(k) or P.PREDLOZI_OPSTI.get(k)


def odstupa(k: str, v, stranka: bool = False) -> bool:
    """Одговор је алтернатива подразумеваном (левом) → „Напомена / разлог одступања“."""
    redovno = (P.REDOVNO_STRANKA if stranka else P.REDOVNO).get(k)
    return bool(redovno and v not in (None, "", []) and v != redovno)


# ---------------------------------------------------------------- странке

def svojstva_lica(lice: dict) -> list[str]:
    return [x.strip().lower() for x in str(lice.get("svojstvo") or "").split(";") if x.strip()]


def strana(lice: dict) -> str:
    """„располаже“, „стиче“, „располаже и стиче“ или „није одређено“ — из својства, никад из одговора."""
    sv = svojstva_lica(lice)
    r = any(x in P.RASPOLAGAC + P.RASPOLAGAC_OSTALI or x in P.OBE_STRANE for x in sv)
    st = any(x in P.STICALAC + P.STICALAC_OSTALI or x in P.OBE_STRANE for x in sv)
    return "располаже и стиче" if r and st else "располаже" if r else "стиче" if st else P.NEODREDJENA


def ime_lica(lice: dict) -> str:
    return str(lice.get("ime") or "").strip() or f"странка {lice.get('id', '')}".strip()


def svojstva_za_posao(posao: str) -> list[str]:
    """Својства странака за правни посао (из Саве), па остала — ниједно се не крије."""
    prva = list(P.SVOJSTVA_PO_POSLU.get(posao, ()))
    ostala = sorted({x for v in P.SVOJSTVA_PO_POSLU.values() for x in v} - set(prva))
    return prva + ostala


def _polja_lica(c: dict, lice: dict) -> dict:
    polja = dict((c.get("stranke") or {}).get(lice["id"]) or {})
    polja["strana"] = strana(lice)
    return polja


# ---------------------------------------------------------------- нова чек-листа

def nova(naziv: str = "", posao: str = "") -> dict:
    t = sada()
    c = {"format": FORMAT, "verzija_formata": VERZIJA_FORMATA, "naziv": naziv, "popunio": "", "lica": [],
         "odgovori": {}, "stranke": {}, "oznake": {}, "modul": {}, "trag": {}, "potvrde": {},
         "stanje": "u_radu", "napravljeno": t, "izmenjeno": t, "zavrseno": ""}
    if posao:
        postavi_posao(c, posao)
    return c


def _u_radu(c: dict) -> None:
    if c.get("stanje") != "u_radu":
        raise GreskaUnosa("Чек-листа је завршена — само за читање. Да бисте је мењали: „Врати у рад“.")


def _izmenjeno(c: dict) -> None:
    c["izmenjeno"] = sada()


def postavi_naziv(c: dict, naziv: str) -> None:
    _u_radu(c)
    c["naziv"] = " ".join(str(naziv or "").split())[:200]
    _izmenjeno(c)


def postavi_popunio(c: dict, ime: str) -> None:
    c["popunio"] = " ".join(str(ime or "").split())[:100]
    _izmenjeno(c)


def postavi_posao(c: dict, posao: str) -> None:
    _u_radu(c)
    posao = str(posao or "").strip()
    if posao == NEODREDJEN:
        posao = ""
    if posao and posao not in P.POSLOVI and posao != "друго":
        raise GreskaUnosa(f"Непознат правни посао: {posao}.")
    if posao:
        c["odgovori"]["posao"] = posao
    else:
        c["odgovori"].pop("posao", None)
    _izmenjeno(c)


def dodaj_lice(c: dict, ime: str, svojstvo: str = "", pravno_lice: bool = False) -> dict:
    _u_radu(c)
    ime = " ".join(str(ime or "").split())[:150]
    if not ime:
        raise GreskaUnosa("Упишите име и презиме странке (или назив правног лица).")
    broj = max([int(x["id"]) for x in c["lica"] if str(x.get("id", "")).isdigit()] + [0]) + 1
    lice = {"id": str(broj), "ime": ime, "svojstvo": " ".join(str(svojstvo or "").split())[:100],
            "pravno_lice": bool(pravno_lice)}
    c["lica"].append(lice)
    _izmenjeno(c)
    return lice


def izmeni_lice(c: dict, sid: str, ime: str | None = None, svojstvo: str | None = None,
                pravno_lice: bool | None = None) -> dict:
    _u_radu(c)
    lice = next((x for x in c["lica"] if x["id"] == sid), None)
    if lice is None:
        raise GreskaUnosa("Странка не постоји.")
    if ime is not None:
        ime = " ".join(str(ime).split())[:150]
        if not ime:
            raise GreskaUnosa("Упишите име и презиме странке (или назив правног лица).")
        lice["ime"] = ime
    if svojstvo is not None:
        lice["svojstvo"] = " ".join(str(svojstvo).split())[:100]
    if pravno_lice is not None:
        lice["pravno_lice"] = bool(pravno_lice)
    _izmenjeno(c)
    return lice


def ukloni_lice(c: dict, sid: str) -> None:
    """Странка и њени одговори се уклањају; одговор „већ унето лице“ који на њу показује се брише."""
    _u_radu(c)
    if not any(x["id"] == sid for x in c["lica"]):
        raise GreskaUnosa("Странка не постоји.")
    c["lica"] = [x for x in c["lica"] if x["id"] != sid]
    c["stranke"].pop(sid, None)
    c["oznake"] = {k: v for k, v in c["oznake"].items() if rastavi(k)[1] != sid}
    c["trag"] = {k: v for k, v in c["trag"].items() if rastavi(k)[1] != sid}
    for polja in c["stranke"].values():
        for k in ("supruznik_lice", "zastupnik_lice"):
            if polja.get(k) == sid:
                polja.pop(k)
    _izmenjeno(c)


# ---------------------------------------------------------------- применљивост (три исхода и „чека“)

def _naziv_uslova(k: str) -> str:
    return {"posao": "правни посао", "forma": "врста исправе", "strana": "страна у послу"}.get(k) or \
        f"„{(PO_STRANCI.get(k) or OPSTA.get(k) or (None, {'t': k}))[1]['t']}“"


def primenljivost(o: dict, q: dict, polja: dict, opsti: dict | None, oznake: dict, sid: str = "") -> tuple[str, str]:
    """(исход, разлог) као cek_lista_modul.primenljivost: „da“ — питање важи; „ne“ — сигурно не важи;
    „nepoznato“ — не зна се, питање се приказује за проверу; „ceka“ — зависи од питања које још нема одговор."""
    ishodi = []
    for k, dozvoljeno in _uslovi(o.get("ako")) + _uslovi(q.get("ako")):
        v = polja.get(k, (opsti or {}).get(k))
        naziv = _naziv_uslova(k)
        oz = oznake.get(kljuc(k, sid)) if sid and k in PO_STRANCI else oznake.get(k)
        if k == "posao" and (not v or v == "друго"):
            ishodi.append(("nepoznato", "правни посао још није одређен"))
        elif k == "forma" and v in (None, "", "није утврђено"):
            ishodi.append(("nepoznato", "врста исправе (запис или солемнизација) још није одређена"))
        elif k == "strana" and v == P.NEODREDJENA:
            ishodi.append(("nepoznato", "страна у послу није одређена (својство странке)"))
        elif oz == NIJE_PRIMENLJIVO:
            ishodi.append(("ne", f"{naziv} је означено као „Није применљиво“"))
        elif oz == RADNJA:
            ishodi.append(("nepoznato", f"{naziv}: потребна радња"))
        elif v in (None, "", []):
            ishodi.append(("ceka", f"зависи од одговора на {naziv}"))
        else:
            lista = dozvoljeno if isinstance(dozvoljeno, (list, tuple)) else [dozvoljeno]
            vazi = bool(v) if dozvoljeno == "*" else (bool(set(v) & set(lista)) if isinstance(v, list) else v in lista)
            if vazi:
                ishodi.append(("da", ""))
            elif isinstance(v, str) and v in NESIGURNO:
                ishodi.append(("nepoznato", f"{naziv} — {v}"))
            else:
                uslov = "било шта изабрано" if dozvoljeno == "*" else ", ".join(str(x) for x in lista)
                ishodi.append(("ne", f"важи само кад је {naziv}: {uslov}"))
    for ishod in ("ne", "nepoznato", "ceka"):
        razlozi = [r for i, r in ishodi if i == ishod]
        if razlozi:
            return ishod, "; ".join(dict.fromkeys(razlozi))
    return "da", ""


# ---------------------------------------------------------------- предлози (никад нису одговор)

def _list_pokriva(k: str, odg: dict) -> bool:
    """Одговор на листу који важи за све странке (као cek_lista._list_pokriva)."""
    return (k == "nastup" and odg.get("k_punomocnik") == "НЕ") or (k in P.PISMENOST and odg.get("k_pismena") == "ДА")


def podrazumevano(c: dict, odg: dict, lica_polja: list[dict]) -> dict:
    """Леви одговори листа за видљива питања без одговора (cek_lista.podrazumevano). После парафа „Предмет сам
    примила/о“ ништа се више не нуди. Пуномоћник и писменост прате оно што је већ унето по странкама."""
    if (c.get("potvrde") or {}).get("primio"):
        return {}
    oznake = c.get("oznake") or {}
    out = {}
    for k, levo in P.REDOVNO.items():
        if k not in P.LIST_2020 or k in odg or k in oznake:
            continue
        if vidljivo(pitanje(k)["ako"], odg):
            out[k] = levo
    for polja in lica_polja:
        if "k_punomocnik" in out and polja.get("nastup") in P.NIJE_LICNO:
            out["k_punomocnik"] = "ДА"
        if "k_pismena" in out and any(polja.get(x) == "не" for x in P.PISMENOST):
            out["k_pismena"] = "НЕ"
    return out


def _predlozi(c: dict, odg: dict) -> dict:
    """{(кључ, странка): {v, poreklo, osnov}} — као cek_lista_modul._predlozi, без података предмета."""
    if (c.get("potvrde") or {}).get("primio"):
        return {}
    pred = {}
    posao = odg.get("posao") or ""
    lica = c.get("lica") or []
    polja_lica = [(c.get("stranke") or {}).get(x["id"]) or {} for x in lica]
    for k, v in podrazumevano(c, odg, polja_lica).items():
        if v == P.REDOVNO.get(k):
            pred[(k, "")] = {"v": v, "poreklo": "podrazumevano", "osnov": "подразумевани (леви) одговор листа"}
        else:
            pred[(k, "")] = {"v": v, "poreklo": "uneto", "osnov": "из одговора већ унетих по странкама"}
    for k in OPSTA:
        if k not in P.LIST_2020 and (k, "") not in pred and k not in odg and predlog(k, posao or "—"):
            pred[(k, "")] = {"v": predlog(k, posao or "—"), "poreklo": "podrazumevano",
                             "osnov": "предлог канцеларије" + (f" за посао „{posao}“" if k in (P.PREDLOZI.get(posao) or {}) else "")}
    # Личне исправе: Сава „да“ предлаже само кад су исправе свих лица уписане у предмет — овај програм их не види.
    pred.pop(("lk_ugovaraca", ""), None)
    pravna = [ime_lica(x) for x in lica if x.get("pravno_lice")]
    if pravna and "firma_ucesnik" not in odg:
        pred[("firma_ucesnik", "")] = {"v": "да", "poreklo": "uneto", "osnov": "међу странкама је правно лице: " + ", ".join(pravna)}
    return pred


# ---------------------------------------------------------------- стање за приказ и сажетак

def prikaz(q: dict | None, v, lica_po_id: dict | None = None) -> str:
    if v in (None, "", []):
        return ""
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    if q and q["tip"] == "lice":
        return (lica_po_id or {}).get(str(v), str(v))
    if q and q["tip"] == "termin":
        m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}:\d{2}).*", str(v))
        return f"{m.group(3)}.{m.group(2)}.{m.group(1)}. у {m.group(4)}" if m else str(v)
    if q and q["tip"] == "kvacica":
        return "важи" if v == "да" else ""
    return str(v)


def _stavka(o: dict, q: dict, sid: str, v, oznaka, ishod: tuple, predlog_, trag, napomena: str,
            lica_po_id: dict, pokriva: str = "") -> dict:
    k = q["k"]
    status = status_vrednosti(q, v, oznaka)
    primenljivo = ishod[0] in ("da", "nepoznato")
    ima_odgovor = (v not in (None, "", []) and status != NIJE_PROVERENO) or oznaka in OZNAKE
    nudi = predlog_ if predlog_ and primenljivo and not ima_odgovor else None
    if nudi and q["tip"] == "kvacica" and v == "да":
        nudi = None
    return {"id": kljuc(k, sid), "k": k, "sid": sid, "odeljak": o["id"], "pitanje": q["t"], "tip": q["tip"],
            "opcije": opcije(q), "binarno": binarno(q), "vrednost": v, "prikaz": prikaz(q, v, lica_po_id),
            "status": status, "status_naziv": STATUSI[status], "oznaka": oznaka if oznaka in OZNAKE else "",
            "primenljivost": ishod[0], "razlog": ishod[1],
            "predlog": ({**nudi, "prikaz": prikaz(q, nudi["v"], lica_po_id), "poreklo_naziv": POREKLA[nudi["poreklo"]]}
                        if nudi else None),
            "trag": trag, "napomena": napomena, "uticaj": P.UTICAJ.get((k, v)) if isinstance(v, str) else None,
            "pokriva": pokriva, "odstupa": odstupa(k, v, bool(sid)), "poverljivo": k == P.POVERLJIVO}


def _stavke_nepokretnosti(c: dict, odg: dict) -> list[dict]:
    """Питања провере непокретности из модула Саве: за послове којима се располаже непокретношћу и кад посао није
    одређен. Без података катастра програм ништа не предлаже — одговара запослени."""
    posao = odg.get("posao") or ""
    if posao and posao != "друго" and posao not in P.PRENOS:
        return []
    modul, oznake, trag = c.get("modul") or {}, c.get("oznake") or {}, c.get("trag") or {}
    out = []
    for k, tekst in P.PROVERE_NEPOKRETNOSTI.items():
        st = modul.get(k) if modul.get(k) in STATUSI else NIJE_PROVERENO
        if oznake.get(k) in OZNAKE:
            st = oznake[k]
        razlog = BEZ_KATASTRA if posao in P.PRENOS else "правни посао још није одређен; " + BEZ_KATASTRA
        out.append({"id": k, "k": k, "sid": "", "odeljak": NEP, "pitanje": tekst, "tip": "provera", "opcije": ["да", "не"],
                    "binarno": True, "vrednost": None, "prikaz": "", "status": st, "status_naziv": STATUSI[st],
                    "oznaka": st if st in OZNAKE else "", "primenljivost": "nepoznato", "razlog": razlog, "predlog": None,
                    "trag": trag.get(k), "napomena": odg.get(k + NAPOMENA) or "", "uticaj": None, "pokriva": "",
                    "odstupa": False, "poverljivo": False})
    return out


def stanje(c: dict) -> dict:
    """Све за приказ и сажетак: питања по целинама (са пет статуса, применљивошћу, предлогом и последицом),
    бројачи, списак за групну потврду, упозорења и КОНТРОЛА листа. Само чита."""
    odg, po_str, oznake = c.get("odgovori") or {}, c.get("stranke") or {}, c.get("oznake") or {}
    trag = c.get("trag") or {}
    lica = c.get("lica") or []
    pred = _predlozi(c, odg)
    lica_po_id = {x["id"]: ime_lica(x) for x in lica}
    odeljci, sve = [], []
    for o in P.DEFINICIJA:
        opsta, po_licima = [], []
        for q in o.get("pitanja", []):
            k = q["k"]
            v = None if oznake.get(k) in OZNAKE else odg.get(k)
            opsta.append(_stavka(o, q, "", v, oznake.get(k), primenljivost(o, q, odg, None, oznake), pred.get((k, "")),
                                 trag.get(k), odg.get(k + NAPOMENA) or "", lica_po_id))
        for lice in lica if o.get("po_stranci") else []:
            sid = lice["id"]
            polja = _polja_lica(c, lice)
            stavke = []
            for q in o["po_stranci"]:
                k = q["k"]
                oz = oznake.get(kljuc(k, sid))
                v = None if oz in OZNAKE else polja.get(k)
                pokriva = ""
                if v in (None, "", []) and _list_pokriva(k, odg):
                    pokriva = "важи одговор са листа за све странке (" + ("не заступа пуномоћник" if k == "nastup"
                                                                         else "писмена, чује, види и пише") + ")"
                stavke.append(_stavka(o, q, sid, v, oz, primenljivost(o, q, polja, odg, oznake, sid), pred.get((k, sid)),
                                      trag.get(kljuc(k, sid)), polja.get(k + NAPOMENA) or "", lica_po_id, pokriva))
            po_licima.append({"sid": sid, "ime": lica_po_id[sid], "svojstvo": lice.get("svojstvo") or "",
                              "strana": strana(lice), "pravno_lice": bool(lice.get("pravno_lice")), "stavke": stavke})
        odeljci.append({"id": o["id"], "naslov": o["odeljak"], "opsta": opsta, "po_licima": po_licima})
        sve += opsta + [s for x in po_licima for s in x["stavke"]]
    nep = _stavke_nepokretnosti(c, odg)
    odeljci.append({"id": NEP, "naslov": "Провера непокретности", "opsta": nep, "po_licima": []})
    sve += nep
    vazece = [s for s in sve if s["primenljivost"] in ("da", "nepoznato")]
    brojaci = {st: 0 for st in STATUSI}
    for s in vazece:
        if (s["pokriva"] and s["status"] == NIJE_PROVERENO) or (s["tip"] == "kvacica" and s["status"] == NE):
            continue  # покривено одговором са листа, односно неозначена кућица под-ставке: не броји се
        brojaci[s["status"]] += 1
    brojaci[NIJE_PRIMENLJIVO] += sum(1 for s in sve if s["primenljivost"] == "ne")
    grupna = [{"k": s["id"], "v": s["predlog"]["v"], "pitanje": s["pitanje"], "stranka": lica_po_id.get(s["sid"], ""),
               "odgovor": s["predlog"]["prikaz"], "poreklo": s["predlog"]["poreklo"],
               "poreklo_naziv": s["predlog"]["poreklo_naziv"], "osnov": s["predlog"]["osnov"]} for s in sve if s["predlog"]]
    return {"naziv": c.get("naziv") or "", "posao": odg.get("posao") or "", "forma": odg.get("forma") or "",
            "popunio": c.get("popunio") or "", "stanje": c.get("stanje") or "u_radu",
            "stanje_naziv": STANJA.get(c.get("stanje") or "u_radu", ""), "samo_citanje": c.get("stanje") != "u_radu",
            "lica": [{"id": x["id"], "ime": lica_po_id[x["id"]], "svojstvo": x.get("svojstvo") or "",
                      "strana": strana(x), "pravno_lice": bool(x.get("pravno_lice"))} for x in lica],
            "odeljci": odeljci, "sve": sve, "brojaci": brojaci, "grupna": grupna, "upozorenja": provera(c),
            "kontrola": kontrola(c), "potvrde": c.get("potvrde") or {}}


def nadji(st: dict, oznaka_pitanja: str) -> dict | None:
    return next((s for s in st["sve"] if s["id"] == oznaka_pitanja), None)


# ---------------------------------------------------------------- унос

def _broj(x) -> float | None:
    try:
        return float(str(x).replace(".", "").replace(" ", "").replace(",", "."))
    except (TypeError, ValueError):
        return None


def procitaj_termin(tekst: str) -> str:
    """„26.11.2026 14:30“, „26.11.2026. у 14.30“ или „2026-11-26T14:30“ → „2026-11-26T14:30“."""
    t = str(tekst or "").strip()
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})[T ](\d{1,2})[:.](\d{2})(?::\d{2})?", t) or None
    if m:
        g, mes, d, h, mi = (int(x) for x in m.groups())
    else:
        m = re.fullmatch(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})\.?\s*(?:у|u|,)?\s*(\d{1,2})[:.](\d{2})\s*(?:ч|h)?\.?", t)
        if not m:
            raise GreskaUnosa("„Жељени термин“: упишите датум и време, нпр. 26.11.2026 14:30.")
        d, mes, g, h, mi = (int(x) for x in m.groups())
    try:
        return dt.datetime(g, mes, d, h, mi).strftime("%Y-%m-%dT%H:%M")
    except ValueError:
        raise GreskaUnosa("„Жељени термин“: такав датум или време не постоји.") from None


def ocisti(q: dict, v, lica: set[str]):
    """Провера једне вредности (као cek_lista._ocisti); празно → None (непопуњено, не значи „не“)."""
    if v in (None, "", []):
        return None
    tip = q["tip"]
    if tip == "kvacica":
        v = v[0] if isinstance(v, list) and len(v) == 1 else v
        if v in ("да", True, "true", "on"):
            return "да"
        raise GreskaUnosa(f"„{q['t']}“: поље се само означава.")
    if tip == "vise":
        v = [x for x in (v if isinstance(v, list) else [v]) if x]
        if any(x not in q["o"] for x in v):
            raise GreskaUnosa(f"„{q['t']}“: непознат избор.")
        return [x for x in q["o"] if x in v] or None
    v = str(v).strip()
    if not v:
        return None
    if tip == "izbor" and v not in q["o"]:
        raise GreskaUnosa(f"„{q['t']}“: непознат одговор.")
    if tip == "tri" and v not in P.TRI:
        raise GreskaUnosa(f"„{q['t']}“: одговор је да, не или није утврђено.")
    if tip == "lice" and v not in lica:
        raise GreskaUnosa(f"„{q['t']}“: изаберите странку са списка.")
    if tip == "iznos":
        cifre = v.replace(".", "").replace(" ", "").replace(",", ".")
        try:
            if float(cifre) < 0:
                raise ValueError
        except ValueError:
            raise GreskaUnosa(f"„{q['t']}“: упишите износ бројем (нпр. 85.000 или 85000,50).") from None
    if tip == "termin":
        return procitaj_termin(v)
    return v[:2000]


_NISTA = object()


def odgovori(c: dict, oznaka_pitanja: str, vrednost=_NISTA, *, prihvati: bool = False, oznaka: str | None = None,
             napomena: str | None = None) -> None:
    """Један одговор: вредност, прихваћен предлог, ознака „Није применљиво“ / „Потребна радња“ (празна ознака је
    поништава), повратак на „Није проверено“ (празна вредност) или напомена (као cek_lista_modul.odgovori)."""
    _u_radu(c)
    k, sid = rastavi(oznaka_pitanja)
    st = stanje(c)
    s = nadji(st, oznaka_pitanja)
    if s is None:
        raise GreskaUnosa("Непознато питање чек-листе.")
    nep = s["tip"] == "provera"
    polja = c["stranke"].setdefault(sid, {}) if sid else c["odgovori"]
    try:
        _upisi_odgovor(c, s, k, sid, oznaka_pitanja, polja, nep, vrednost, prihvati, oznaka, napomena)
    finally:
        if sid and not c["stranke"].get(sid):
            c["stranke"].pop(sid, None)  # одбијен унос не оставља празан запис странке


def _upisi_odgovor(c, s, k, sid, oznaka_pitanja, polja, nep, vrednost, prihvati, oznaka, napomena) -> None:
    tr = {"vreme": sada(), "nacin": "pojedinacno", "ime": c.get("popunio") or ""}
    if napomena is not None:
        tekst = str(napomena).strip()[:2000]
        if tekst:
            polja[k + NAPOMENA] = tekst
        else:
            polja.pop(k + NAPOMENA, None)
    elif oznaka is not None:
        if oznaka in OZNAKE:
            if nep:
                c["modul"].pop(k, None)
            polja.pop(k, None)
            c["oznake"][oznaka_pitanja] = oznaka
            c["trag"][oznaka_pitanja] = {**tr, "poreklo": "nije_primenljivo" if oznaka == NIJE_PRIMENLJIVO else "proveriti"}
        elif oznaka == "":
            c["oznake"].pop(oznaka_pitanja, None)
            c["trag"].pop(oznaka_pitanja, None)
        else:
            raise GreskaUnosa("Непознат статус.")
    else:
        if prihvati:
            if not s["predlog"]:
                raise GreskaUnosa("За ово питање нема предложеног одговора.")
            vrednost = s["predlog"]["v"]
        elif vrednost is _NISTA:
            raise GreskaUnosa("Нема одговора.")
        if vrednost in NESIGURNO:
            raise GreskaUnosa("Изаберите одговор, „Потребна радња“ или оставите питање као „Није проверено“.")
        if nep:
            if vrednost in (None, ""):
                c["modul"].pop(k, None)
            elif vrednost in ("да", DA, "не", NE):
                c["modul"][k] = DA if vrednost in ("да", DA) else NE
            else:
                raise GreskaUnosa("Одговор је да или не.")
            vrednost = c["modul"].get(k)
        else:
            q = (PO_STRANCI if sid else OPSTA)[k][1]
            dozvoljena = {x["id"] for x in c["lica"] if x["id"] != sid}
            vrednost = ocisti(q, vrednost, dozvoljena)
            if vrednost is None:
                polja.pop(k, None)
            else:
                polja[k] = vrednost
        c["oznake"].pop(oznaka_pitanja, None)
        if vrednost in (None, "", []):
            c["trag"].pop(oznaka_pitanja, None)
        else:
            poreklo = s["predlog"]["poreklo"] if s["predlog"] and vrednost == s["predlog"]["v"] else "proveriti"
            c["trag"][oznaka_pitanja] = {**tr, "poreklo": poreklo}
    _izmenjeno(c)


def proveri_spisak(ponudjeno: list[dict], spisak) -> None:
    """Групно се потврђује само виђени списак: сваки предлог мора бити у њему, са истом вредношћу."""
    if not ponudjeno:
        return
    if not isinstance(spisak, list):
        raise SpisakSePromenio("Пре потврде погледајте списак предложених одговора.", ponudjeno)
    vidjeno = {str(x.get("k")): x.get("v") for x in spisak if isinstance(x, dict)}
    if any(x["k"] not in vidjeno or vidjeno[x["k"]] != x["v"] for x in ponudjeno):
        raise SpisakSePromenio("Списак предложених одговора се у међувремену променио — погледајте га поново, "
                               "па потврдите.", ponudjeno)


def grupna_potvrda(c: dict, spisak) -> int:
    """„Сагласан сам са свим осталим предложеним одговорима“: предлози са виђеног списка постају одговори; уз сваки
    остаје време, начин „групно“ и порекло. Питања без предлога остају „Није проверено“. Враћа број потврђених."""
    _u_radu(c)
    ponudjeno = stanje(c)["grupna"]
    proveri_spisak(ponudjeno, spisak)
    t = sada()
    for x in ponudjeno:
        k, sid = rastavi(x["k"])
        (c["stranke"].setdefault(sid, {}) if sid else c["odgovori"])[k] = x["v"]
        c["oznake"].pop(x["k"], None)
        c["trag"][x["k"]] = {"vreme": t, "nacin": "grupno", "ime": c.get("popunio") or "", "poreklo": x["poreklo"]}
    if ponudjeno:
        _izmenjeno(c)
    return len(ponudjeno)


# ---------------------------------------------------------------- упозорења и доследност (cek_lista.provera)

def word_upozorenja(odg: dict) -> list[dict]:
    out = []
    if (odg.get("forma") or "") == "солемнизација":
        return out
    for (k, x), poruka in P.WORD_RUCNO.items():
        if odg.get(k) == x and (k != "zabelezba" or odg.get("posao") == "доживотно издржавање"):
            out.append({"polje": k, "vrsta": "word", "poruka": poruka})
    if odg.get("posao") == "поклон" and not odg.get("motiv"):
        out.append({"polje": "motiv", "vrsta": "word", "poruka": "Мотив поклона није уписан: у обрасцу остаје његова "
                    "формулација (оригинал фн. 5) — мотив је обавезан, проверите пре нацрта."})
    return out


def forma_dozvoljena(posao: str, forma: str) -> tuple:
    return tuple((P.FORME.get(posao) or {}).get(forma) or (True, ""))


def provera(c: dict) -> list[dict]:
    """Обавезна поља, напомене уз одступања, последице и доследност — само упозорења, ништа не блокира и ништа се
    не закључује (cek_lista.provera). [{polje, poruka, vrsta}]"""
    odg, po_str, lica = c.get("odgovori") or {}, c.get("stranke") or {}, c.get("lica") or []
    oznake = c.get("oznake") or {}
    out = []
    for o in P.DEFINICIJA:
        vid_o = vidljivo(o.get("ako"), odg)
        for q in o.get("pitanja", []):
            k = q["k"]
            if not (vid_o and vidljivo(q.get("ako"), odg)) or oznake.get(k) in OZNAKE:
                continue
            x = odg.get(k)
            if k in P.OBAVEZNA and x in (None, "", []):
                out.append({"polje": k, "vrsta": "obavezno", "poruka": f"Није попуњено: {q['t']}."})
            if odstupa(k, x) and not odg.get(k + NAPOMENA):
                out.append({"polje": k, "vrsta": "napomena", "poruka": f"„{q['t']}“ = {x}: упишите напомену / разлог одступања."})
            if isinstance(x, str) and (k, x) in P.UTICAJ:
                out.append({"polje": k, "vrsta": "uticaj", "poruka": P.UTICAJ[(k, x)]})
        for lice in lica:
            polja = _polja_lica(c, lice)
            ime = ime_lica(lice)
            for q in o.get("po_stranci", []):
                k = q["k"]
                if not vidljivo(q.get("ako"), polja, odg) or oznake.get(kljuc(k, lice["id"])) in OZNAKE:
                    continue
                x = polja.get(k)
                if k in P.OBAVEZNA_STRANKA and x in (None, "") and not _list_pokriva(k, odg):
                    out.append({"polje": kljuc(k, lice["id"]), "vrsta": "obavezno", "poruka": f"{ime}: није попуњено „{q['t']}“."})
                if odstupa(k, x, stranka=True) and not polja.get(k + NAPOMENA):
                    out.append({"polje": kljuc(k, lice["id"]), "vrsta": "napomena",
                                "poruka": f"{ime}: „{q['t']}“ = {x}: упишите напомену / разлог одступања."})
                if isinstance(x, str) and (k, x) in P.UTICAJ:
                    out.append({"polje": kljuc(k, lice["id"]), "vrsta": "uticaj", "poruka": f"{ime}: {P.UTICAJ[(k, x)]}"})

    def d(polje, poruka, vrsta="doslednost"):
        out.append({"polje": polje, "vrsta": vrsta, "poruka": poruka})

    if odg.get("posao") == "продаја":
        cena, isp, ost = (_broj(odg.get(k)) for k in ("cena", "isplaceno", "preostalo"))
        if odg.get("cena_isplacena") in P.NEISPLACENO and None not in (cena, isp, ost) and abs(isp + ost - cena) > 0.005:
            d("preostalo", f"Исплаћено ({odg['isplaceno']}) и преостало ({odg['preostalo']}) не дају цену ({odg['cena']}).")
        if odg.get("cena_isplacena") == "да" and odg.get("dozvola_upisa") == "након исплате":
            d("dozvola_upisa", "Цена је исплаћена у целости, а дозвола за упис се даје „након исплате“ — проверите.")
        if odg.get("cena_isplacena") == "не" and odg.get("dozvola_upisa") == "даје се одмах":
            d("dozvola_upisa", "Цена није исплаћена, а дозвола за упис се даје одмах — питање за јавног бележника.")
    out.extend(word_upozorenja(odg))
    # доследност листа са странкама (cek_lista._provera_lista)
    polja_svih = [po_str.get(x["id"]) or {} for x in lica]
    if odg.get("k_punomocnik") == "ДА" and not any(p.get("nastup") in P.NIJE_LICNO for p in polja_svih):
        d("k_punomocnik", "КОНТРОЛА: странку заступа пуномоћник — по странкама означите коју странку и пуномоћје.")
    if odg.get("k_pismena") == "НЕ" and not any(p.get(k) == "не" for p in polja_svih for k in P.PISMENOST):
        d("k_pismena", "КОНТРОЛА: странка није писмена или не чује, не види, не говори, не пише — по странкама "
                       "означите коју странку и шта (сведоци, тумач).")
    pravna = [x for x in lica if x.get("pravno_lice")]
    if odg.get("firma_ucesnik") == "да" and not pravna:
        d("firma_ucesnik", "На листу је означено „Продавац/Купац је фирма“, а међу странкама нема правног лица — унесите "
                           "правно лице и заступника.")
    elif pravna and odg.get("firma_ucesnik") != "да" and odg.get("posao"):
        d("firma_ucesnik", "Међу странкама је правно лице, а на листу није означено „Продавац/Купац је фирма“.")
    if odg.get("ne_dostavlja") == "да":
        d("ne_dostavlja", "Странке захтевају да нотар не доставља — пре доставе и слања еШалтером проверити са јавним "
                          "бележником (одлуку доноси јавни бележник).", "uticaj")
    for lice in lica:
        polja = po_str.get(lice["id"]) or {}
        if polja.get("govori") == "не" and not set(polja.get("potrebna_lica") or []) & {"тумач", "сведок"}:
            d(kljuc("potrebna_lica", lice["id"]), f"{ime_lica(lice)}: не говори, а тумач или сведок није означен — "
                                                 "проверите потребна лица.")
    if odg.get("forma") == "солемнизација":
        if odg.get("posao") == "заложна изјава":
            d("forma", "ЗЈБ чл. 82 ст. 1 т. 3: заложна изјава са изричитом изјавом о непосредном принудном извршењу "
                       "сачињава се само као јавнобележнички запис — проверите садржину изјаве.")
        if odg.get("posao") == "зајам":
            d("forma", "ЗЈБ чл. 93 ст. 3–4: зајам новца између физичких лица од 10.000 евра и више — оверен препис уговора "
                       "одмах се доставља Управи за спречавање прања новца и уписују се подаци у регистар (зајмодавац, "
                       "зајмопримац, износ, рок, валута).", "uticaj")
        if odg.get("posao") in P.PRENOS and any((po_str.get(x["id"]) or {}).get("nastup") == "преко законског заступника"
                                                and strana(x) in P.RASPOLAZE[:2] for x in lica):
            d("forma", "ЗЈБ чл. 82 ст. 1 т. 1: уговор о располагању непокретностима пословно неспособних лица "
                       "сачињава се у облику јавнобележничког записа — располагач наступа преко законског заступника.")
    if odg.get("posao") and odg.get("forma") in ("јавнобележнички запис", "солемнизација"):
        ok, izvor = forma_dozvoljena(odg["posao"], odg["forma"])
        if ok is False:
            d("forma", f"„{odg['posao']}“ се не сачињава као {odg['forma']}. {izvor}".strip())
        elif ok == "provera":
            d("forma", f"Форма „{odg['forma']}“ за „{odg['posao']}“ није активирана (правни извор на провери). {izvor}".strip())
    for lice in lica:
        polja = po_str.get(lice["id"]) or {}
        ime = ime_lica(lice)
        if "не" in (polja.get("cita"), polja.get("potpisuje"), polja.get("vidi")) and \
                "сведок" not in (polja.get("potrebna_lica") or []):
            d(kljuc("potrebna_lica", lice["id"]), f"{ime}: не чита, не види или не може да потпише, а сведок није "
                                                 "означен — проверите потребна лица.")
        if polja.get("nastup") in P.NIJE_LICNO and polja.get("punomocje_dostavljeno") == "не":
            d(kljuc("punomocje_dostavljeno", lice["id"]), f"{ime}: наступа преко заступника, а пуномоћје није достављено.")
    return out


# ---------------------------------------------------------------- КОНТРОЛА листа (cek_lista.kontrola)

def ima_napomenu(k: str, odg: dict) -> bool:
    return bool(odg.get(k + NAPOMENA)) or any(odg.get(x) not in (None, "", []) for x in P.DOPUNE_2020.get(k, ()))


def kontrola(c: dict) -> dict:
    """crvene — заставице које у Сави заустављају коначан број; nedostaje — шта спречава параф „спремно за читање“;
    spremno — нема ни једног ни другог. Програм не доноси правну одлуку: набраја разлоге."""
    odg, potvrde = c.get("odgovori") or {}, c.get("potvrde") or {}

    def vid(k: str) -> bool:
        return vidljivo(pitanje(k)["ako"], odg)

    crvene = [{"k": k, "poruka": poruka} for k, x, poruka in P.CRVENE if odg.get(k) == x]
    if odg.get("dok_za_vracanje") == "ДА" and not potvrde.get("dokumentacija") and not ima_napomenu("dok_za_vracanje", odg):
        crvene.append({"k": "dok_za_vracanje", "poruka": P.CRVENA_DOKUMENTACIJA})
    nedostaje = []
    for k in ("lk_ugovaraca",) + tuple(P.KONTROLA_LISTA):
        if vid(k) and (odg.get(k) in (None, "", []) or odg.get(k) in NESIGURNO):
            nedostaje.append({"k": k, "poruka": f"без одговора: {pitanje(k)['t']}"})
    for k, poruka in P.ZA_SPREMNO.items():
        if odg.get(k) == "не":
            nedostaje.append({"k": k, "poruka": poruka})
    for k in P.NAPOMENA_OBAVEZNA:
        if vid(k) and odstupa(k, odg.get(k)) and odg.get(k) not in NESIGURNO and not ima_napomenu(k, odg):
            nedostaje.append({"k": k + NAPOMENA, "poruka": f"без напомене: {pitanje(k)['t']} — {odg[k]}"})
    if odg.get("forma") == "јавнобележнички запис" and odg.get("posao") in P.PRENOS and odg.get("imamo_parcelu") != "да":
        nedostaje.append({"k": "imamo_parcelu", "poruka": "није означено „Имамо број парцеле“ (запис о непокретности)"})
    return {"crvene": crvene, "nedostaje": nedostaje, "spremno": not crvene and not nedostaje}


# ---------------------------------------------------------------- парафи и животни циклус

def potvrdi(c: dict, k: str, spisak: list | None = None) -> dict:
    """Параф са именом и временом (cek_lista.potvrdi). „primio“ групно потврђује виђени списак предлога; „spremno“
    само кад КОНТРОЛА нема ни црвених заставица ни недостатака; „spakovan“ не ако списи нису сложени. Параф се не
    поништава (остаје име и време првог)."""
    _u_radu(c)
    if k not in P.POTVRDE:
        raise GreskaUnosa("Непознат параф.")
    if (c.get("potvrde") or {}).get(k):
        return c["potvrde"][k]
    ime = (c.get("popunio") or "").strip()
    if not ime:
        raise GreskaUnosa("Пре парафа упишите своје име у поље „Попунио/ла“.")
    if k == "primio":
        grupna_potvrda(c, spisak)
    if k == "spremno":
        ocena = kontrola(c)
        if not ocena["spremno"]:
            raise GreskaUnosa("Предмет још не може на читање — на листу: "
                              + "; ".join(x["poruka"] for x in ocena["crvene"] + ocena["nedostaje"]) + ".")
    if k == "spakovan" and (c.get("odgovori") or {}).get("spisi_slozeni") == "не":
        raise GreskaUnosa("Списи нису сложени редом из пописа прилога — прво их сложите.")
    c.setdefault("potvrde", {})[k] = {"ime": ime, "vreme": sada()}
    _izmenjeno(c)
    return c["potvrde"][k]


def zavrsi(c: dict) -> None:
    """„Заврши чек-листу“: ништа не тражи и ништа не претвара; завршена је само за читање док се не врати у рад."""
    _u_radu(c)
    c["stanje"], c["zavrseno"] = "zavrsena", sada()
    _izmenjeno(c)


def vrati_u_rad(c: dict) -> None:
    if c.get("stanje") == "u_radu":
        return
    c["stanje"] = "u_radu"
    _izmenjeno(c)
