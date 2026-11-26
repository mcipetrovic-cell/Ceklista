"""Сажетак као Word документ (.docx) — без спољних библиотека (само zipfile), да програм остане један мали .exe.

Документ има само оно што сажетку треба: наслов, редове заглавља, наслове целина, име странке, ставке са цртицом
(црвене заставице црвено) и напомене. Стилови су у документу (Наслов, Наслов 1, Наслов 2), па их Word препознаје."""

from __future__ import annotations

import datetime as dt
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from . import NAZIV, PROIZVODJAC, sazetak as S
from .fajl import upisi_atomski

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
FONT = "Times New Roman"

TIPOVI = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>"""

VEZE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""

VEZE_DOKUMENTA = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""


def _rpr(velicina: int, bold: bool = False, boja: str = "") -> str:
    return (f'<w:rPr><w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}" w:cs="{FONT}" w:eastAsia="{FONT}"/>'
            + ("<w:b/><w:bCs/>" if bold else "") + (f'<w:color w:val="{boja}"/>' if boja else "")
            + f'<w:sz w:val="{velicina}"/><w:szCs w:val="{velicina}"/><w:lang w:val="sr-Cyrl-RS"/></w:rPr>')


STILOVI = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="{W}">
<w:docDefaults><w:rPrDefault>{_rpr(22)}</w:rPrDefault>
<w:pPrDefault><w:pPr><w:spacing w:after="60" w:line="264" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
<w:pPr><w:spacing w:after="120"/><w:outlineLvl w:val="0"/></w:pPr>{_rpr(32, True, "1F2A44")}</w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
<w:pPr><w:keepNext/><w:spacing w:before="240" w:after="80"/><w:pBdr><w:bottom w:val="single" w:sz="4" w:space="1" w:color="C9BFA8"/></w:pBdr><w:outlineLvl w:val="0"/></w:pPr>{_rpr(24, True, "1F2A44")}</w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
<w:pPr><w:keepNext/><w:spacing w:before="120" w:after="40"/><w:ind w:left="284"/><w:outlineLvl w:val="1"/></w:pPr>{_rpr(22, True, "3B4A6B")}</w:style>
</w:styles>"""


def _pasus(tekst: str, stil: str = "", uvlaka: int = 0, bold: bool = False, boja: str = "", velicina: int = 22,
           crtica: bool = False) -> str:
    ppr = ""
    if stil or uvlaka:
        ppr = "<w:pPr>" + (f'<w:pStyle w:val="{stil}"/>' if stil else "") + \
              (f'<w:ind w:left="{uvlaka}" w:hanging="{227 if crtica else 0}"/>' if uvlaka else "") + "</w:pPr>"
    t = ("– " if crtica else "") + tekst
    rpr = "" if stil and not (bold or boja) else _rpr(velicina, bold, boja)
    return f'<w:p>{ppr}<w:r>{rpr}<w:t xml:space="preserve">{escape(t)}</w:t></w:r></w:p>'


def dokument_xml(s: dict) -> str:
    telo = []
    u_licu = False
    for vrsta, sadrzaj in S.delovi(s):
        tekst = str(sadrzaj)
        if vrsta == "naslov":
            telo.append(_pasus(tekst, "Title"))
        elif vrsta == "podnaslov":
            telo.append(_pasus(tekst, velicina=20, boja="555555"))
        elif vrsta == "odeljak":
            telo.append(_pasus(tekst, "Heading1"))
            u_licu = False
        elif vrsta == "lice":
            telo.append(_pasus(tekst, "Heading2"))
            u_licu = True
        elif vrsta == "stavka":
            telo.append(_pasus(tekst, uvlaka=794 if u_licu else 454, crtica=True))
        elif vrsta == "crveno":
            telo.append(_pasus(tekst, uvlaka=454, crtica=True, bold=True, boja="B00020"))
        else:
            telo.append(_pasus(tekst, velicina=18, boja="666666"))
    sekcija = ('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
               '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1418" w:header="567" w:footer="567" w:gutter="0"/>'
               "</w:sectPr>")
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:document xmlns:w="{W}"><w:body>'
            + "".join(telo) + sekcija + "</w:body></w:document>")


def _core(naslov: str) -> str:
    sad = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            f"<dc:title>{escape(naslov)}</dc:title><dc:creator>{escape(NAZIV)}</dc:creator>"
            f'<dcterms:created xsi:type="dcterms:W3CDTF">{sad}</dcterms:created>'
            f'<dcterms:modified xsi:type="dcterms:W3CDTF">{sad}</dcterms:modified></cp:coreProperties>')


def _app() -> str:
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
            f"<Application>{escape(NAZIV)}</Application><Company>{escape(PROIZVODJAC)}</Company></Properties>")


def docx_bajtovi(s: dict) -> bytes:
    import io

    naslov = "Сажетак чек-листе" + (f" — {s['zaglavlje']['naziv']}" if s["zaglavlje"]["naziv"] else "")
    bafer = io.BytesIO()
    with zipfile.ZipFile(bafer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", TIPOVI)
        z.writestr("_rels/.rels", VEZE)
        z.writestr("word/document.xml", dokument_xml(s))
        z.writestr("word/styles.xml", STILOVI)
        z.writestr("word/_rels/document.xml.rels", VEZE_DOKUMENTA)
        z.writestr("docProps/core.xml", _core(naslov))
        z.writestr("docProps/app.xml", _app())
    return bafer.getvalue()


def sacuvaj(s: dict, putanja: Path) -> Path:
    putanja = Path(putanja)
    upisi_atomski(putanja, docx_bajtovi(s))
    return putanja
