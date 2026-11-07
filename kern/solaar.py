"""De solaar: het moment waarop de Zon terugkeert op haar natal lengte.

Methode uit het eigen PHP-programma (`src/Calculation/SolarReturnCalculator.php`): een
**Newton-stap op de Zonsnelheid**, met de verjaardag in het
doeljaar als gok. De gok is de sleutel — de Zon staat op de verjaardag altijd binnen een paar
graden van haar natal stand, dus één deling door de snelheid brengt je er vrijwel meteen.

Gemeten op vier data: 3 tot 4 aanroepen, 0,1 ms, restfout onder 0,0001" en
het resultaat binnen 0,002 seconde van een bisectie over hetzelfde jaar. De drempel en het
maximum aantal slagen zijn die van het PHP-programma.

Wat deze module **niet** doet: de zone of de plaats regelen. `moment()` zet het gevonden
UT-moment om naar de kloktijd van de gekozen plaats, omdat het formulier die tijd leest —
een solaar die met UT in het tijdveld staat leest later als een fout.
"""

from __future__ import annotations

from . import efemeride as _eph
from . import tijd as _tijd

# De drempel uit het PHP-programma: 0,0000058 graden, dus 0,02 boogseconde. Dat is een
# **afdrukdrempel** - genoeg om een stand op hele boogseconden te drukken - en bij een tijd hoort
# hij niet: 0,02" is ruim een halve seconde, en dan hangt de seconde die wij teruggeven van de
# drempel af in plaats van van de efemeride (gemeten: 74 ms verschil met een bisectie).
# Daarom blijft DREMPEL de eis waaraan het antwoord moet voldoen, en rekenen we door tot FIJN; dat
# kost één aanroep extra en de seconde is dan stabiel.
DREMPEL = 0.0000058
FIJN = 1e-9
MAX_SLAGEN = 5

# De juliaanse dag van 1970-01-01 00:00 UT: het nulpunt van de epoch-tijd.
_JD_1970 = 2440587.5


def vind(natal_zon, jaar, maand, dag):
    """Juliaanse dag (UT) waarop de Zon terug is op `natal_zon`.

    `maand` en `dag` zijn de geboortedatum: die geven de gok. Geeft `(jd, verslag)` terug, met
    het aantal slagen en de restfout erbij, zodat een niet-uitgekomen iteratie te zien is in
    plaats van stil te verdwijnen.
    """
    jd = _eph.julian_day_ut(jaar, maand, dag, 0.0)
    verschil, slag = 0.0, 0
    for slag in range(1, MAX_SLAGEN + 1):
        lengte, snelheid = _eph.zon_stand(jd)
        # Het verschil terugbrengen tot (-180, 180]: anders slaat een correctie van bijna 360 graden
        # de verkeerde kant op (en dan convergeert hij niet maar divergeert hij).
        verschil = ((lengte - natal_zon + 180.0) % 360.0) - 180.0
        if abs(verschil) < FIJN:
            break
        jd -= verschil / snelheid
    return jd, {"slagen": slag, "rest": verschil,
                "uitgekomen": abs(verschil) < DREMPEL}


def moment(natal_zon, jaar, maand, dag, tijdzone_id, lon):
    """Het solaar-moment als kloktijd van de gekozen plaats, plus het UT-moment.

    Wat het formulier nodig heeft: datum, tijd, zone en de coördinaten. De tijd is de
    **geldende zonetijd van de plaats**, zodat deze horoscoop leest als elke andere; het
    UT-moment gaat mee voor de meldregel (controle), niet voor het tijdveld.

    Let op het verschil tussen rekenwaarde en weergave: `julian_day` is de
    **rekenwaarde** en die is exact; `tijd` en `utc` zijn **weergave** en vallen op hele seconden. Het
    venster vult het formulier met die weergave, en de kaart wordt daarna uit het veld gerekend - dus
    het moment schuift daarbij tot een halve seconde op. Gemeten kost dat op 19-07-1963 Dieren 6,18"
    in de Ascendant (22,7" in het slechtste geval): kleiner dan de korrel van een geboortetijd, dus
    bewust zo gelaten. Zodra de progressies komen moet dit anders: daar is één seconde 365,24 s in de
    kaart (Asc 3,39°), en dan moet de tijd als getal mee, niet als tekst.
    """
    jd, verslag = vind(natal_zon, jaar, maand, dag)
    ts = int(round((jd - _JD_1970) * 86400.0))
    off = _tijd.get_offset(tijdzone_id, lon, ts)
    lokaal = _tijd.van_epoch(ts + off["offset"])
    utc = _tijd.van_epoch(ts)
    return {
        "datum": lokaal.strftime("%Y-%m-%d"),
        "tijd": lokaal.strftime("%H:%M:%S"),
        "utc": utc.strftime("%Y-%m-%d %H:%M:%S"),
        "offset": off["offset"],
        "offset_label": off.get("label", ""),
        "offset_source": off.get("source", ""),
        "tijdzone_id": tijdzone_id,
        "lon": lon,
        "julian_day": jd,
        **verslag,
    }


def bisectie(natal_zon, jaar, maand, dag, dagen=10):
    """Dezelfde terugkeer, maar dan zoekend: alleen om de eerste te controleren (ijking).

    Zoekt de terugkeer **het dichtst bij de verjaardag** in dat jaar - precies de betekenis die de
    iteratie heeft - door rond die dag een venster van `dagen` etmalen af te scannen en het laatste
    etmaal te halveren. Duur (tientallen Zon-aanroepen) en daarom alleen in `ijk-solaar.py`.

    Een kalenderjaar afscannen zou hier juist fout gaan: bij een geboorte op 1 januari ligt de
    terugkeer van "2026" op 31 december 2025, en dan vindt een scan over 2026 een heel ander
    moment (gemeten).
    """
    jd = _eph.julian_day_ut(jaar, maand, dag, 0.0) - dagen

    def zon(j):
        return _eph.zon_stand(j)[0]

    vorige = (zon(jd) - natal_zon) % 360.0
    for d in range(1, 2 * dagen + 1):
        nu = (zon(jd + d) - natal_zon) % 360.0
        if vorige > 180.0 and nu < 180.0:
            lo, hi = jd + d - 1, jd + d
            while hi - lo > 1e-7:
                mid = (lo + hi) / 2
                if (zon(mid) - natal_zon) % 360.0 > 180.0:
                    lo = mid
                else:
                    hi = mid
            return (lo + hi) / 2
        vorige = nu
    return None
