"""Waar het programma leest en waar het schrijft.

Lezen en schrijven zijn twee verschillende mappen. In een bundel van PyInstaller ligt de
programmamap in een tijdelijke uitleesmap (`sys._MEIPASS`) die na het afsluiten verdwijnt. Wie
daarin schrijft — zoals `data/osm-cache.json` en `data/eigen-plaatsen.tsv` — verliest die gegevens
bij de volgende start, en op Windows staat het programma daar soms zelfs geen schrijven toe.

Daarom sinds deze module twee soorten paden:

- `bron(...)`  de meegeleverde bestanden: in de bundel de uitgepakte map, in ontwikkeling de
              projectmap. Alleen lezen.
- `gebruikersmap(...)`  wat de gebruiker maakt: de horoscopen, de instellingen, de eigen
              plaatsen en de OSM-cache. Eén map, naast de horoscopen, zodat één map kopiëren
              alles dekt (dezelfde gedachte als in `kern/instellingen.py`).

`ASTRO_HOROSCOPENMAP` verzet de gebruikersmap; de ijkingen gebruiken dat om in een tijdelijke
map te werken. In de bundel zet `bouw/start.py` hem niet: `~/astrologie-horoscopen` is ook op
Windows een zichtbare map (`C:\\Users\\<naam>\\astrologie-horoscopen`), en een zichtbare map is
beter te back-uppen dan een verborgen `%APPDATA%`.
"""

from __future__ import annotations

import os
import sys

# `sys.frozen` zet PyInstaller in de gebouwde app; in ontwikkeling bestaat het niet.
GEBUNDELD = bool(getattr(sys, "frozen", False))


def bron(*delen: str) -> str:
    """Een pad naar een meegeleverd bestand (alleen lezen)."""
    if GEBUNDELD:
        wortel = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(sys.executable))
    else:
        wortel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(wortel, *delen)


def standaardmap() -> str:
    r"""De gebruikersmap, zonder hem aan te maken.

    `os.path.join` + `normpath` en niet `expanduser("~/astrologie-horoscopen")`: op Windows vervangt
    `expanduser` alléén de tilde, en dan blijft de schuine streep van de rest staan -
    `C:\Users\<naam>/astrologie-horoscopen`. Dat werkt (Windows slikt beide), maar de gebruiker ziet
    het in het startkader en bij Instellingen, en het leest als een programmeerfout.

    (Deze docstring is een r-string omdat er een Windows-pad in staat: zonder de r leest Python
    de backslash voor de U als het begin van een unicode-escape en start het programma niet. Dat
    kostte een meting - zie `references/valkuilen.md`.)
    """
    eigen = os.environ.get("ASTRO_HOROSCOPENMAP")
    if eigen:
        return os.path.normpath(os.path.expanduser(eigen))
    return os.path.normpath(os.path.join(os.path.expanduser("~"), "astrologie-horoscopen"))


def gebruikersmap(*delen: str) -> str:
    """Een pad in de gebruikersmap (schrijfbaar); de map wordt aangemaakt."""
    m = standaardmap()
    os.makedirs(m, exist_ok=True)
    return os.path.join(m, *delen)


def staat(*delen: str) -> str:
    r"""Een pad in de **staat**-map: de wegwerpbestanden (vensterstand, OSM-cache, foutenlog).

    Waarom een eigen submap: de hoofdmap is wat de gebruiker maakt en kopieert —
    horoscopen, instellingen, eigen plaatsen. Daar hoort geen cache, vensterstand of log tussen: die
    drie belanden anders in elke back-up en staan in de weg als iemand de map opent. Een submap houdt
    "één map kopiëren is de back-up" overeind zonder die drie mee te slepen.

    **Geen migratie en geen terugval**, want deze bestanden zijn per definitie wegwerp: de eerste start
    na de wijziging gebruikt gewoon de standaardmaat en een lege cache. Wat in de oude map blijft
    staan is rommel van een paar kB, geen gegeven dat iemand kwijt is.
    """
    m = gebruikersmap("staat")
    os.makedirs(m, exist_ok=True)
    return os.path.join(m, *delen)
