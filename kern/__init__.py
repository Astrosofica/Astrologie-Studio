"""Rekenkern van Astrologie Studio (pyswisseph).

Draaien met /usr/bin/python3 (daar staat pyswisseph in), vanuit de projectmap:

    from kern import kaart
    k = kaart.maak_kaart("Print A", 1968, 12, 13, 5, 20, 0, "Europe/Amsterdam", 52+22/60, 6+27/60)
"""

from . import aspecten, efemeride, formaat, invoer, kaart, opslag, tijd   # noqa: F401

__all__ = ["aspecten", "efemeride", "formaat", "invoer", "kaart", "opslag", "tijd"]
__version__ = "basis-0.6"   # gelijk aan "versie" bovenaan de kaart-JSON (kern/kaart.py); samen ophogen
