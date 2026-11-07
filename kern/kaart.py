"""Van geboortegegeven naar kaart-JSON. Dit is het contract tussen kern, tekenaar en schil.

Besluit B7 (puntenlijst): Zon t/m Pluto, Noordknoop (true node) en de **dagpars**
(Asc + Maan - Zon, nooit de nachtvariant). Chiron alleen als optie. Vertex en Lilith niet.
"""

from __future__ import annotations

from . import aspecten as _aspecten
from . import efemeride as _eph
from . import formaat as _fmt
from . import tijd as _tijd

# Een bewaard bestand draagt `versie` en `meta` - waaronder `met_chiron` (zodat een bewaarde kaart bij
# het openen dezelfde kaart oplevert) en `efemeride` met een `waarschuwingen`-lijst voor een datum
# buiten 1800-2399. De berekening zelf staat er niet in (T56): de kaart houdt in het geheugen alle
# velden en `opslag.bewaar` schrijft alleen het recept weg. Een bestand van een oudere vorm blijft
# leesbaar - de lezer negeert wat hij niet nodig heeft.
VELDEN = ["naam", "datum", "tijd", "tijdzone_id", "plaats", "lat", "lon",
          "huizenstelsel", "tijdcorrectie", "met_chiron"]

# Wat de kaart zegt als swisseph buiten 1800-2399 op de Moshier-benadering terugviel. In gewone taal,
# met het waarom erbij: de gebruiker hoeft niet te weten wat een efemeridebestand is, wel dat de
# standen hier iets minder precies zijn.
# Twee regels: eerst de mededeling, dan wat het voor de standen betekent. Het
# woord "bestanden" is eruit: dat is ontwikkelaarstaal, een cursist leest "efemeridentabellen".
_MELDING_BENADERING = (
    "Deze datum valt buiten het bereik van de efemeridentabellen (1800 tot 2400).",
    "De standen zijn daarom met de Moshier-benadering berekend: dat scheelt hooguit enkele "
    "boogseconden, minder dan een boogminuut.",
)


def maak_kaart(naam, jaar, maand, dag, uur, minuut, seconde,
               tijdzone_id, lat, lon, plaats="", huizenstelsel="K",
               tijdcorrectie=None, met_chiron=False):
    utc_ts, off = _tijd.local_to_utc(jaar, maand, dag, uur, minuut, seconde,
                                     tijdzone_id, lon, tijdcorrectie)
    # `_tijd.van_epoch` en niet `datetime.fromtimestamp`: dat laatste gaat op Windows door de
    # C-functie `gmtime`, die negatieve waarden (dus alles vóór 1970) met Errno 22 weigert.
    utc = _tijd.van_epoch(utc_ts)
    hour_ut = utc.hour + utc.minute / 60.0 + utc.second / 3600.0
    jd = _eph.julian_day_ut(utc.year, utc.month, utc.day, hour_ut)

    posities = _eph.posities(jd, met_chiron=met_chiron)
    # Buiten 1800-2399 rekent swisseph met de Moshier-benadering; dat gaat door, maar de kaart zegt
    # het (geen foutmelding, wel melden dat de standen minder nauwkeurig zijn).
    benadering = _eph.benadering()
    cusps, asc, mc, vertex = _eph.huizen(jd, lat, lon, huizenstelsel)

    zon = _eph.lengte_van("Zon", posities)
    maan = _eph.lengte_van("Maan", posities)
    dagpars = (asc + maan - zon) % 360.0

    # Asc en MC als bewegende hoekpunten: snelheid numeriek (nodig voor A/S bij aspecten)
    d = 0.01
    _, asc2, mc2, _ = _eph.huizen(jd + d, lat, lon, huizenstelsel)
    snel_asc = ((asc2 - asc + 180) % 360 - 180) / d
    snel_mc = ((mc2 - mc + 180) % 360 - 180) / d

    punten = []
    for p in posities:
        punten.append(_punt(p["naam"], p["lengte"], p["snelheid"], p["retrograde"],
                            "planeet", cusps))
    punten.append(_punt("Dagpars", dagpars, 0.0, False, "punt", cusps))
    punten.append({"naam": "Ascendant", "lengte": asc, "snelheid": snel_asc,
                   "retrograde": False, "is_hoek": True, "huis": 1, "soort": "hoek",
                   "positie": _positie(asc)})
    punten.append({"naam": "MC", "lengte": mc, "snelheid": snel_mc,
                   "retrograde": False, "is_hoek": True, "huis": 10, "soort": "hoek",
                   "positie": _positie(mc)})

    aspecten = _aspecten.bereken(punten)
    cellen = _aspecten.matrix(punten, aspecten)
    matrix = []
    for i in range(len(punten)):
        rij = []
        for j in range(len(punten)):
            if i == j:
                rij.append(None)
                continue
            a, b = (i, j) if i < j else (j, i)
            inhoud = cellen.get((a, b), [])
            rij.append([{"glyf": x["glyf"], "orb": x["orb_afgekapt"],
                         "letter": x["letter"], "hoek": x["hoek"],
                         "dominant": x["dominant"]} for x in inhoud])
        matrix.append(rij)

    huizen = []
    for k, c in enumerate(cusps, start=1):
        huizen.append({"nr": k, "lengte": c, "positie": _positie(c)})

    return {
        "versie": "basis-0.6",
        "meta": {
            "naam": naam,
            "datum": f"{jaar:04d}-{maand:02d}-{dag:02d}",
            "tijd": f"{uur:02d}:{minuut:02d}:{seconde:02d}",
            "utc": utc.strftime("%Y-%m-%d %H:%M:%S"),
            "tijdzone_id": tijdzone_id,
            "offset_sec": off["offset"],
            "offset_label": off.get("label", ""),
            "offset_source": off.get("source", ""),
            "tijdcorrectie": tijdcorrectie or "zone",
            "plaats": plaats,
            "lat": lat,
            "lon": lon,
            "huizenstelsel": huizenstelsel,
            "huizenstelsel_naam": _eph.HUISSTELSELS.get(huizenstelsel, huizenstelsel),
            "met_chiron": bool(met_chiron),
            "zodiactype": "Tropisch",
            "centrum": "Geocentrisch",
            "knoop": "True Node",
            "julian_day_ut": jd,
            "efemeride": "Moshier" if benadering else "Swiss Ephemeris",
        },
        "ascendant": _positie(asc),
        "mc": _positie(mc),
        "huizen": huizen,
        "punten": punten,
        "aspecten": aspecten,
        # Welke punten geen aspectlijnen krijgen - de regel staat in `kern/aspecten.py` en de
        # weergave en de tekenaar lezen hem hier, zodat er één lijst is (T42).
        "weg_punt": list(_aspecten.WEG_PUNT),
        "matrix": matrix,
        "waarschuwingen": list(_MELDING_BENADERING) if benadering else [],
    }


def _punt(naam, lengte, snelheid, retrograde, soort, cusps):
    return {
        "naam": naam,
        "lengte": lengte,
        "snelheid": snelheid,
        "retrograde": retrograde,
        "soort": soort,
        "huis": _eph.vind_huis(lengte, cusps),
        "positie": _positie(lengte),
    }


def _positie(lon):
    teken, graad, minuut = _fmt.afgekapt(lon)
    return {
        "lengte": lon,
        "teken_index": teken,
        "teken": _fmt.TEKENS[teken - 1],
        "graad": graad,
        "minuut": minuut,
        "label": f"{graad:02d}° {_fmt.TEKENS_AFK[teken - 1]} {minuut:02d}'",
        "glyf": _fmt.glyf_teken(lon),
    }


# Publieke naam voor de andere kernmodules: de transits bouwen dezelfde standnotatie
# (`kern/transits.py` gebruikt hem voor de momentopname), en een tweede notatiehelper zou
# gegarandeerd uit de pas gaan lopen met deze.
positie = _positie
