"""Efemeride: posities en huizen via pyswisseph.

Conventies (besluit T11b, bevestigd in zijn eigen programma): tropisch, geocentrisch,
Noordknoop als **true node**, huizenstelsel **Koch** (`b'K'` is hier de standaard).

Draaien met `/usr/bin/python3` - daar staat pyswisseph in (2.10.03). Zie de skill
`sweph-experiments`.
"""

from __future__ import annotations

import os
import threading

import swisseph as swe

from . import paden

# De efemeriden liggen in de projectmap (`efemeriden/`) en niet meer op een
# vast pad van deze machine: de bundel moet ze meenemen, en dan is een absoluut pad naar
# de ontwikkelmachine onbruikbaar. `ASTRO_EPHE_PATH` wint nog steeds (de ijkingen gebruiken dat).
EPHE_PATH = os.environ.get("ASTRO_EPHE_PATH") or paden.bron("efemeriden")

# Puntenlijst besluit B7: Zon t/m Pluto, Noordknoop (True Node), dagpars; Chiron optioneel.
LICHAMEN = [
    (swe.SUN, "Zon"),
    (swe.MOON, "Maan"),
    (swe.MERCURY, "Mercurius"),
    (swe.VENUS, "Venus"),
    (swe.MARS, "Mars"),
    (swe.JUPITER, "Jupiter"),
    (swe.SATURN, "Saturnus"),
    (swe.URANUS, "Uranus"),
    (swe.NEPTUNE, "Neptunus"),
    (swe.PLUTO, "Pluto"),
    (swe.TRUE_NODE, "Noordknoop"),
]
# Chiron: de constante van swisseph zelf (15), niet het catalogusnummer 2060. Met 2060 weigert
# swisseph ("illegal planet number") en gaf de optie Chiron een 500. De standen komen uit
# `seas_18.se1` (de hoofasteroiden) in de efemeridenmap; dat bestand staat er.
CHIRON_ID = swe.CHIRON
# Naam -> planetennummer van swisseph, voor de routes die één lichaam per keer vragen.
_IDS = {naam: pid for pid, naam in LICHAMEN}

HUISSTELSELS = {"K": "Koch", "P": "Placidus", "O": "Porphyrius", "R": "Regiomontanus",
                "C": "Campanus", "E": "Equal", "W": "Whole Sign", "A": "Azimuthal"}

# De bestanden die er moeten staan (sepl = planeten, semo = maan, seas = hoofasteroiden/Chiron).
NODIGE_BESTANDEN = ("sepl_18.se1", "semo_18.se1", "seas_18.se1")

# Buiten 1800-2399 (de .se1-bestanden) valt swisseph terug op de Moshier-benadering. Eerst
# weigerde dit huis dat; nu rekenen we door en melden het (zie `_stand`).

_lokaal = threading.local()
_bestanden_gecontroleerd = False


def _controleer_bestanden():
    """Zonder de .se1-bestanden valt swisseph **stil** terug op de Moshier-benadering.

    Dat is precies gebeurd: de schil rekende zonder klacht door met de
    benadering, en de bewaarde kaarten weken daardoor tot 2,88 boogseconde af van de echte
    efemeriden (grootste verschil: de Noordknoop). Daarom hier een harde controle in plaats
    van een stille terugval.
    """
    ontbreekt = [n for n in NODIGE_BESTANDEN if not os.path.exists(os.path.join(EPHE_PATH, n))]
    if ontbreekt:
        raise RuntimeError(
            "De efemeriden in %s ontbreken (%s). Zonder die bestanden berekent swisseph een "
            "benadering in plaats van de echte standen; ik bereken liever niet door. Zet "
            "ASTRO_EPHE_PATH op de map met de .se1-bestanden."
            % (EPHE_PATH, ", ".join(ontbreekt)))


def initialiseer():
    """Zet de efemeridenmap **per thread** en controleer of de bestanden er staan.

    pyswisseph bewaart dat pad per thread, niet per proces. Een schil die per vraag een nieuwe
    thread opent (`ThreadingHTTPServer`) rekende daardoor alleen de **eerste** vraag met de
    echte efemeriden en elke volgende met de Moshier-benadering - tot 2,88 boogseconde ernaast.
    Gemeten (zelfde juliaanse dag: hoofdthread SWIEPH, nieuwe thread MOSEPH).
    Vandaar: het pad per thread zetten, de bestandscontrole maar één keer.
    """
    global _bestanden_gecontroleerd
    if not getattr(_lokaal, "pad_gezet", False):
        swe.set_ephe_path(EPHE_PATH)
        _lokaal.pad_gezet = True
    if not _bestanden_gecontroleerd:
        _controleer_bestanden()
        _bestanden_gecontroleerd = True
    return swe.version


def _stand(jd, pid, naam):
    """Eén lichaam uit de efemeriden, of buiten 1800-2399 uit de Moshier-benadering.

    De bestanden lopen van 1800 tot 2399; daarbuiten valt swisseph **stil** terug op Moshier en mist
    de teruggegeven vlag de SWIEPH-bit. Geen fout en geen belemmering, maar de standen zijn er minder
    nauwkeurig en dat hoort de gebruiker te weten. Het verschil is klein — gemeten op 1 januari: Zon
    0,01-0,06", Maan 0,1-0,65", Mercurius 0,01-0,07", Pluto -3,7" (1800) en +6,1" (2399) — maar het is
    niet nul. Daarom zet deze functie een vlag die `kaart.maak_kaart` in de melding en in
    `meta.efemeride` doorgeeft; de gebruiker ziet het, het programma stopt niet.
    """
    r = swe.calc_ut(jd, pid, swe.FLG_SWIEPH | swe.FLG_SPEED)
    if not r[1] & swe.FLG_SWIEPH:
        _lokaal.benadering = True
    return r


def benadering():
    """True als de laatste standenberekening in deze thread op Moshier terugviel."""
    return bool(getattr(_lokaal, "benadering", False))


def julian_day_ut(year, month, day, hour_ut):
    """Juliaanse dag voor een UT-moment; `hour_ut` decimaal (bv. 4.333333)."""
    initialiseer()
    return swe.julday(year, month, day, hour_ut, swe.GREG_CAL)


def julian_day_van_timestamp(ts):
    from .tijd import van_epoch
    d = van_epoch(ts)
    return julian_day_ut(d.year, d.month, d.day,
                         d.hour + d.minute / 60.0 + d.second / 3600.0)


def posities(jd, met_chiron=False):
    """[{naam, lengte, breedte, snelheid, retrograde}] in vaste volgorde."""
    initialiseer()
    _lokaal.benadering = False
    uit = []
    for pid, naam in LICHAMEN:
        r = _stand(jd, pid, naam)
        lengte = r[0][0]
        uit.append({
            "naam": naam,
            "lengte": lengte,
            "breedte": r[0][1],
            "snelheid": r[0][3],
            "retrograde": r[0][3] < 0,
        })
    if met_chiron:
        r = _stand(jd, CHIRON_ID, "Chiron")
        uit.append({"naam": "Chiron", "lengte": r[0][0], "breedte": r[0][1],
                    "snelheid": r[0][3], "retrograde": r[0][3] < 0})
    return uit


def huizen(jd, lat, lon, stelsel="K"):
    """(cusps[1..12], asc, mc, vertex) volgens het gekozen stelsel."""
    initialiseer()
    cusps, ascmc = swe.houses(jd, lat, lon, stelsel.encode("ascii"))
    return list(cusps), ascmc[0], ascmc[1], ascmc[3]


def lengte_van(naam, lijst):
    for p in lijst:
        if p["naam"] == naam:
            return p["lengte"]
    raise KeyError(naam)


def stand_van(naam, jd):
    """Eén lichaam op één moment: (lengte in graden, snelheid in graden per dag).

    Voor de transitscan (`kern/transits.py`): die loopt per lichaam over een venster en heeft geen
    tien standen per stap nodig. Zelfde weg als de rest (`_stand`), dus ook dezelfde Moshier-melding
    buiten 1800-2399.
    """
    r = _stand(jd, _IDS[naam], naam)
    return r[0][0] % 360.0, r[0][3]


def zon_stand(jd):
    """De Zon op één moment: (lengte in graden, snelheid in graden per dag).

    Nodig voor de solaar-iteratie (`kern/solaar.py`): die vraagt telkens alleen de Zon, en tien
    lichamen uitrekenen om er één te lezen is zonde. Wel dezelfde weg als de rest (`_stand`), dus
    ook dezelfde Moshier-melding buiten 1800-2399.
    """
    r = _stand(jd, swe.SUN, "Zon")
    return r[0][0] % 360.0, r[0][3]


def vind_huis(lon, cusps):
    """Huisnummer 1-12, gelijk aan HousePlanetMatcher::findHouse()."""
    for huis in range(1, 13):
        volgende = huis + 1 if huis < 12 else 1
        start = cusps[huis - 1] % 360.0
        eind = cusps[volgende - 1] % 360.0
        x = lon % 360.0
        if start <= eind:
            if start <= x < eind:
                return huis
        else:
            if x >= start or x < eind:
                return huis
    return 1
