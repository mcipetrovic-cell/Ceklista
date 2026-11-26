# PyInstaller: један извршни програм Ceklista.exe (без инсталације, без прозора конзоле).
#   pyinstaller --noconfirm Ceklista.spec   →   dist/Ceklista.exe
# Програм користи само стандардну библиотеку Python-а (tkinter, json, zipfile) — нема додатних пакета.
import re
from pathlib import Path

KOREN = Path(SPECPATH)
tekst = (KOREN / "ceklista" / "__init__.py").read_text(encoding="utf-8")
VERZIJA = re.search(r'VERZIJA_BROJ = "([\d.]+)"', tekst).group(1)
brojevi = tuple(int(x) for x in (VERZIJA.split(".") + ["0", "0", "0"])[:4])

# Подаци о програму у Windows-у (Својства → Детаљи)
(KOREN / "build").mkdir(exist_ok=True)
verzija_datoteka = KOREN / "build" / "verzija.txt"
verzija_datoteka.write_text(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={brojevi}, prodvers={brojevi}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1,
                    subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('281A04B0', [
      StringStruct('CompanyName', 'Slavia Brothers, Geneva'),
      StringStruct('FileDescription', 'Чек-листа'),
      StringStruct('FileVersion', '{VERZIJA}'),
      StringStruct('InternalName', 'Ceklista'),
      StringStruct('LegalCopyright', '© 2026 Slavia Brothers, Geneva. All rights reserved.'),
      StringStruct('OriginalFilename', 'Ceklista.exe'),
      StringStruct('ProductName', 'Чек-листа'),
      StringStruct('ProductVersion', '{VERZIJA}')])]),
    VarFileInfo([VarStruct('Translation', [0x281A, 1200])])
  ]
)
""", encoding="utf-8")

a = Analysis(
    ["main.py"],
    pathex=[str(KOREN)],
    datas=[("data/Ceklista.ico", "data")],
    hiddenimports=[],
    excludes=["pytest", "PIL", "numpy", "unittest", "pydoc", "lib2to3", "test"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Ceklista",
    console=False,
    icon=str(KOREN / "data" / "Ceklista.ico"),
    version=str(verzija_datoteka),
    upx=False,
    runtime_tmpdir=None,
)
