"""Заједничко за пробе: свака проба има своје привремене фасцикле (ништа се не пише у Документе корисника).
У пробама су само измишљена лица (ПЕТАР ПЕТРОВИЋ, ЈЕЛЕНА ЈОВАНОВИЋ) — ни ЈМБГ ни подаци исправа се не уносе."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

KOREN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOREN))

from ceklista import logika as L  # noqa: E402

PETAR, JELENA = "ПЕТАР ПЕТРОВИЋ", "ЈЕЛЕНА ЈОВАНОВИЋ"


@pytest.fixture(autouse=True)
def fascikle(tmp_path, monkeypatch):
    monkeypatch.setenv("CEKLISTA_FASCIKLA", str(tmp_path / "cekliste"))
    monkeypatch.setenv("CEKLISTA_LOKALNO", str(tmp_path / "lokalno"))
    return tmp_path


@pytest.fixture
def prodaja():
    """Продаја: ПЕТАР продаје (располаже), ЈЕЛЕНА купује (стиче)."""
    c = L.nova("ОПУ 12/2026", "продаја")
    L.dodaj_lice(c, PETAR, "продавац")
    L.dodaj_lice(c, JELENA, "купац")
    return c


def ima_ekran() -> bool:
    if sys.platform == "win32":
        return True
    if not os.environ.get("DISPLAY"):
        return False
    try:
        import tkinter as tk

        k = tk.Tk()
        k.destroy()
        return True
    except Exception:  # noqa: BLE001
        return False
