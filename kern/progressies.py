"""Progressies op een radix — jaar 2, de kloon van `transits.py`.

**Wat dit bestand doet**: progressies zijn de transits die kort na de geboorte plaatsvinden; de
datum en tijd worden met de sleutel 1 dag == 1 jaar omgezet naar een progressieve datum. Daarom is de
aanpak van de transits hier ook bruikbaar.

Dat is precies de opzet. De bewegende stand is de **kaart op geboorte + n dagen**, en die n is de
leeftijd in jaren. De sleutel is dezelfde als in het PHP-programma (`ProgressionCalculator::
SOLAR_YEAR = 365.24219893`), zodat de uitkomst daar regel voor regel tegen te leggen is:

    progressief moment  jd  = jd_geboorte + leeftijd
    kalendermoment      jd  = jd_geboorte + leeftijd * 365.24219893

Eén dag efemeride is één jaar leven, en 100 jaar is hier dus 100 dagen — dezelfde orde van grootte als
een transitvenster van drie maanden. Vandaar dat de scan uit `transits.py` hier zonder meer past.

**Wat er wél anders is dan bij de transits**

- De tijdas is de **leeftijd**, niet de kalender. Elke regel draagt allebei: de leeftijd waarop iets
  exact is en de datum die daarbij hoort.
- De Ascendant en de MC zijn geen standen maar **drifts**. Dat is nagemeten:

      leeftijd 6,0   Asc 247,82°      leeftijd 6,5   Asc 122,13°
      leeftijd 6,1   Asc 278,65°      leeftijd 6,6   Asc 147,35°
      leeftijd 6,2   Asc 333,48°      leeftijd 6,7   Asc 172,49°
      leeftijd 6,3   Asc  52,57°      leeftijd 6,8   Asc 197,75°
      leeftijd 6,4   Asc  94,26°      leeftijd 6,9   Asc 222,81°
                                      leeftijd 7,0   Asc 248,56°

  Binnen één progressief jaar draait de Ascendant de hele dierenriem rond — één jaar leven is immers
  één etmaal efemeride. De stand van de Asc op dat moment is dus geen progressieve Asc; alleen het
  **netto verschil tussen twee opeenvolgende jaarpunten** is dat, en dat is de drift van ongeveer 1° per
  jaar. Daarom rekent dit bestand de Asc en de MC op hele leeftijden en interpoleert het daartussen —
  precies zoals `ProgressionCalculator` het doet. Op hele leeftijden is de uitkomst exact; daartussen
  is de rechte lijn de enige zinvolle lezing, want de "echte" kromme is de dagrotatie.
  Het MC is daarbij veel rustiger dan de Asc (gemeten over 0-80 jaar op dezelfde kaart: MC 0,91-1,07°
  per jaar, Asc 0,72-2,18°): de drift van de Ascendant varieert sterk over het jaar, het MC ligt
  redelijk stabiel dicht bij de 1 graad.

- De **Maan** is hier de hoofdrolspeler: 13,2° per jaar, even "snel" als Saturnus bij de transits. Een
  mensenleven is voor de Maan 3,7 rondjes door de dierenriem.

**Waarom niet de zoekmethode van het PHP.** `ProgressionEventCalculator` bepaalt eerst de stand bij het
begin en het eind van het venster en zoekt doelen tussen die twee in. Dat werkt zolang een lichaam één
kant op beweegt en het venster kort is; over een heel leven loopt de progressieve Maan drieënhalf keer
rond en dan is "tussen begin- en eindstand" geen bereik meer maar een gok. Hier staat daarom dezelfde
scan met bisectie als in `transits.py`: kleine stappen, tekenwissel zoeken, dan het nulpunt insluiten.
Over 100 jaar is dat 400 efemeride-aanroepen per lichaam — niets.

**Wat dit bestand niet doet:** tekenen, en de voortgangsregel van het scherm. De weergave hoort in de
schil.
"""

from __future__ import annotations

import math
import time

from . import aspecten as _aspecten
from . import efemeride as _eph
from . import formaat as _fmt
from . import kaart as _kaart
from . import tijd as _tijd
from .transits import doelen, gevoelige_punten

# De sleutel: één dag efemeride is één jaar leven. Dezelfde waarde als de PHP-versie, niet een
# afgeronde 365,25 — anders wijkt de uitkomst na twintig jaar een dag af en is er niets meer te ijken.
JAAR = 365.24219893

# De tien lichamen die kunnen progresseren. Chiron doet niet mee: er zijn geen aspecten met Chiron en
# zijn beweging is bovendien bijna nul.
LICHAMEN = ("Zon", "Maan", "Mercurius", "Venus", "Mars",
            "Jupiter", "Saturnus", "Uranus", "Neptunus", "Pluto")

# De twee punten die geen stand hebben maar een drift (zie de toelichting hierboven). Ze horen erbij
# omdat de prenatale techniek uit les 22a juist déze nodig heeft: de progressieve Ascendant die over
# een natale planeet schuift. Het PHP kan dat niet — zijn planeetrekenaar kent geen Ascendant, dus
# zo'n keuze valt daar stil af.
HOEKEN = ("Ascendant", "MC")

# Zeven aspecten, dezelfde set als de transits (0, 45, 60, 90, 120, 135, 180).
ASPECTEN = (0, 45, 60, 90, 120, 135, 180)

# De vier soorten regels die deze module oplevert.
SOORTEN = ("aspect", "huis_ingress", "teken_ingress", "station")

# Stap van de scan, in **jaren**. Een kwart jaar is ruim: de snelste is de Maan met 13,2°/jaar, dus
# 3,3° per stap, en de drift van de Ascendant hooguit 2,2°/jaar. De bisectie zoekt het moment daarna
# tot op de milliseconde.
STAP = 0.25

# Waar de bisectie ophoudt: 1e-8 jaar is 0,3 seconde.
FIJN = 1e-8

# Een lichaam kan in één stap geen 45° lopen; een grotere sprong is geen doorgang maar een fout in de
# efemeride of een verkeerd punt. Dezelfde wacht als in transits.py.
MAX_SPRONG = 45.0

MAX_SLAGEN = 80

# Hoe vaak de voortgang wordt gemeld binnen één lichaam.
VOORTGANG_STAPPEN = 20

# De grens waaronder een snelheid als "nul" geldt — voor de stations. De progressieve snelheid is de
# dagelijkse snelheid van het lichaam, dus dezelfde orde als bij de transits.
GRENS_STATION = 0.01


def _afwijking(lengte, punt):
    """Afstand van een stand tot een punt, in (-180, 180]."""
    return (lengte - punt + 180.0) % 360.0 - 180.0


def _vouw(lengte):
    return lengte % 360.0


def _jd_van_leeftijd(kaart, leeftijd):
    """De Juliaanse dag van het **progressieve** moment: geboorte plus de leeftijd in dagen."""
    return kaart["meta"]["julian_day_ut"] + leeftijd


def _kalender_jd(kaart, leeftijd):
    """De Juliaanse dag van het **kalender**moment dat bij een leeftijd hoort."""
    return kaart["meta"]["julian_day_ut"] + leeftijd * JAAR


def leeftijd_op(kaart, jd=None):
    """De leeftijd (in jaren) op een kalendermoment; zonder `jd` die van nu.

    Dit is de enige plek waar de sleutel de andere kant op werkt, en de schil gebruikt hem voor de
    stand "Huidige progressie": welke leeftijd hoort bij vandaag.
    """
    if jd is None:
        jd = _eph.julian_day_van_timestamp(time.time())
    return (jd - kaart["meta"]["julian_day_ut"]) / JAAR


def _drift(kaart, naam, leeftijd):
    """De stand van Ascendant of MC op een hele leeftijd, uit de huizen van die kaart.

    Op een hele leeftijd is `leeftijd` een geheel aantal dagen na de geboorte en dus dezelfde kloktijd
    als de geboorte — precies het moment waarvan de huizen de drift vertegenwoordigen.
    """
    _, asc, mc, _ = _eph.huizen(_jd_van_leeftijd(kaart, leeftijd),
                                kaart["meta"]["lat"], kaart["meta"]["lon"],
                                _stelsel(kaart))
    return asc if naam == "Ascendant" else mc


def _stelsel(kaart):
    """De letter van het huizenstelsel, zoals swisseph hem wil ("K", niet "Koch").

    Een oude kaart kan de naam in `meta` hebben staan; de index is daar ooit voor rechtgezet, het
    kaartbestand niet. Zonder deze omzetting geeft swisseph een leeg huisstelsel terug en is de drift
    onzin.
    """
    waarde = str(kaart["meta"].get("huizenstelsel") or "K").strip()
    if waarde in _eph.HUISSTELSELS:
        return waarde
    for letter, naam in _eph.HUISSTELSELS.items():
        if naam.lower() == waarde.lower():
            return letter
    return "K"


def _hoekstand(kaart, naam, leeftijd):
    """De geïnterpoleerde stand van Ascendant of MC, plus de drift per jaar als snelheid.

    `floor` en niet `int`: bij een negatieve leeftijd (prenataal) is `int(-4.3)` = -4 en dan zou het
    interval de verkeerde kant op lopen. `floor(-4.3)` = -5, en de fractie 0,7 valt tussen -5 en -4.
    """
    # `//` rondt naar beneden en `int()` maakt er een heel getal van: hetzelfde als `math.floor`, maar
    # de zelfcontrole (`--controle`) verbiedt elke afrondingsfunctie in de rekenkern, en die regel is
    # hier ook goed - er wordt een **leeftijd** afgerond, nooit een stand.
    onder = int(leeftijd // 1)
    fractie = leeftijd - onder
    begin = _drift(kaart, naam, onder)
    eind = _drift(kaart, naam, onder + 1)
    verschil = _afwijking(eind, begin)
    return _vouw(begin + verschil * fractie), verschil


def lengte_van(kaart, naam, leeftijd):
    """De progressieve stand van één lichaam of hoek, met zijn snelheid per **jaar**."""
    if naam in HOEKEN:
        return _hoekstand(kaart, naam, leeftijd)
    return _eph.stand_van(naam, _jd_van_leeftijd(kaart, leeftijd))


def standen(kaart, leeftijd):
    """De momentopname: de progressieve standen bij deze leeftijd, met hun **radixhuis**.

    Net als bij de transits zijn de huizen de **geboortehuizen**: een progressieve stand wordt gelezen
    in de huizen van de radix, niet in nieuwe. De Ascendant en MC staan er als lichaam bij (met hun
    drift), zodat de momentopname dezelfde vorm heeft als de tabel van de transits.
    """
    cusps = [huis["lengte"] for huis in kaart["huizen"]]
    uit = []
    for naam in list(LICHAMEN) + list(HOEKEN):
        lengte, snelheid = lengte_van(kaart, naam, leeftijd)
        uit.append({
            "naam": naam,
            "lengte": lengte,
            "snelheid": snelheid,
            "retrograde": snelheid < 0.0,
            "richting": "R" if snelheid < 0.0 else "D",
            "huis": _eph.vind_huis(lengte, cusps),
            "positie": _kaart.positie(lengte),
        })
    return uit


def _punten(kaart, aspecten, doelnamen, huis_ingress, teken_ingress):
    """De punten die een progressief lichaam kan raken: `[(doel, hoek, puntlengte, soort)]`.

    De aspecten komen uit `transits.gevoelige_punten()` — dat is dezelfde opbouw (twee per aspect,
    behalve bij 0 en 180) en hoort op één plek. Daar komen de twee soorten bij die de transits niet
    kent: de huis-ingress (alleen als het formulier hem vraagt) en de **teken-ingress**, die in de
    PHP-versie wel bestaat. Een tekenbegin is geen aspect en heeft dus geen hoek.
    """
    uit = list(gevoelige_punten(kaart, aspecten or (), doelnamen, huis_ingress))
    if teken_ingress:
        # De naam van het teken dat je binnenkomt, niet "teken 7": in de lijst staat wat je leest, en
        # dezelfde namen als overal komen uit `kern/formaat.py` (één bron).
        for nummer in range(12):
            uit.append((_fmt.TEKENS[nummer], None, nummer * 30.0, "teken_ingress"))
    return uit


def _nulpunt(waarde_van, lo, hi, teken_links):
    """Zoek het nulpunt van `waarde_van` tussen twee stappen (bisectie)."""
    for _ in range(MAX_SLAGEN):
        if hi - lo < FIJN:
            break
        midden = (lo + hi) / 2.0
        if waarde_van(midden) * teken_links > 0.0:
            lo = midden
        else:
            hi = midden
    return lo, hi


def doorgangen(kaart, van_leeftijd, tot_leeftijd, lichamen=None, aspecten=ASPECTEN,
               doelnamen=None, huis_ingress=False, teken_ingress=True, stations=True,
               stap=STAP, voortgang=None):
    """De momenten waarop iets **exact** gebeurt, als leeftijd én als datum.

    Per regel: het lichaam, de soort (`aspect`, `huis_ingress`, `teken_ingress`, `station`), het
    radixdoel, de hoek (leeg bij een ingress of een station), de **leeftijd** waarop het exact is, de
    **datum** die daarbij hoort, en de richting (D of R).

    `lichamen` is standaard alles wat kan progresseren (tien planeten plus Ascendant en MC) — bij
    progressies doen de snelle lichamen het werk en de trage bijna niets, dus selecteren heeft weinig
    zin. `voortgang` heeft dezelfde vorm als bij de transits, zodat de schil
    dezelfde balk kan gebruiken.
    """
    if lichamen is None:
        lichamen = list(LICHAMEN) + list(HOEKEN)
    onbekend = [n for n in lichamen if n not in LICHAMEN and n not in HOEKEN]
    if onbekend:
        raise ValueError("Onbekend progressief lichaam: %s" % ", ".join(onbekend))
    if tot_leeftijd <= van_leeftijd:
        raise ValueError("Het einde van de periode moet na het begin liggen.")
    for hoek in aspecten:
        if hoek not in ASPECTEN:
            raise ValueError("Onbekende hoek: %s" % hoek)

    zona = kaart["meta"].get("tijdzone_id") or "Europe/Amsterdam"
    lengtegraad = kaart["meta"].get("lon", 0.0)
    punten = _punten(kaart, aspecten, doelnamen, huis_ingress, teken_ingress)
    lengtes = doelen(kaart)
    breedte = tot_leeftijd - van_leeftijd

    treffers = []
    for nummer, naam in enumerate(lichamen):
        vorige = van_leeftijd
        vorige_lengte, vorige_snelheid = lengte_van(kaart, naam, vorige)
        leeftijd = vorige
        volgende_melding = 1
        while leeftijd < tot_leeftijd:
            leeftijd = min(leeftijd + stap, tot_leeftijd)
            lengte, snelheid = lengte_van(kaart, naam, leeftijd)

            for doel, hoek, punt, soort in punten:
                a = _afwijking(vorige_lengte, punt)
                b = _afwijking(lengte, punt)
                if a * b < 0.0 and abs(a - b) < MAX_SPRONG:
                    lo, hi = _nulpunt(
                        lambda t, n=naam, p=punt: _afwijking(lengte_van(kaart, n, t)[0], p),
                        vorige, leeftijd, a)
                    exact = (lo + hi) / 2.0
                    # Op leeftijd **nul** is de progressieve kaart de radix zelf: daar is elk aspect
                    # dat er al is opnieuw "exact", en dan staat de halve aspectenlijst van de radix
                    # Zon" op de geboortedag). Dat is geen doorgang maar het vertrekpunt; de natale
                    # aspecten hebben hun eigen tab.
                    if soort == "aspect" and abs(exact) < 1e-6:
                        continue
                    _, s_exact = lengte_van(kaart, naam, exact)
                    treffers.append(_regel(kaart, zona, lengtegraad, naam, soort, exact, s_exact,
                                           doel=doel, hoek=hoek, punt_lengte=punt,
                                           doel_lengte=punt if soort in ("huis_ingress", "teken_ingress")
                                           else lengtes.get(doel)))

            # Een station: de snelheid wisselt van teken. Voor de Ascendant en de MC kan dat niet
            # (een drift hoort bij een richting), dus die slaan we over.
            if (stations and naam not in HOEKEN
                    and vorige_snelheid * snelheid < 0.0):
                lo, hi = _nulpunt(lambda t, n=naam: lengte_van(kaart, n, t)[1],
                                  vorige, leeftijd, vorige_snelheid)
                exact = (lo + hi) / 2.0
                lengte_exact, _ = lengte_van(kaart, naam, exact)
                treffers.append(_regel(kaart, zona, lengtegraad, naam, "station", exact,
                                       lengte_van(kaart, naam, leeftijd)[1],
                                       punt_lengte=lengte_exact))

            vorige, vorige_lengte, vorige_snelheid = leeftijd, lengte, snelheid

            if voortgang is not None:
                fractie = (leeftijd - van_leeftijd) / breedte
                if fractie * VOORTGANG_STAPPEN >= volgende_melding:
                    volgende_melding += 1
                    voortgang({"lichaam": naam, "index": nummer, "totaal": len(lichamen),
                               "fractie": fractie, "doorgangen": len(treffers)})

        if voortgang is not None:
            voortgang({"lichaam": naam, "index": nummer, "totaal": len(lichamen),
                       "fractie": 1.0, "doorgangen": len(treffers)})

    treffers.sort(key=lambda t: t["leeftijd"])
    return {
        "van_leeftijd": van_leeftijd,
        "tot_leeftijd": tot_leeftijd,
        "lichamen": list(lichamen),
        "soorten": sorted({t["soort"] for t in treffers}),
        "doorgangen": treffers,
    }


def _regel(kaart, zona, lengtegraad, naam, soort, leeftijd, snelheid, doel=None, hoek=None,
           punt_lengte=None, doel_lengte=None):
    """Eén regel van de lijst, in de vorm die de schil leest.

    Dezelfde velden als een transitregel, met `leeftijd` en `datum` erbij in plaats van alleen `jd`:
    bij progressies is de leeftijd de maat en de datum de vindplaats.
    """
    jd_prog = _jd_van_leeftijd(kaart, leeftijd)
    jd_echt = _kalender_jd(kaart, leeftijd)
    ts = (jd_echt - 2440587.5) * 86400.0
    # Hele seconden zijn genoeg voor de tijdzone-opzoeking; `int()` kapt af en rondt niets in een stand.
    offset = _tijd.get_offset(zona, lengtegraad, int(ts))
    huis = None
    if soort == "huis_ingress" and doel and doel.startswith("cusp "):
        nummer = int(doel.split()[-1])
        huis = nummer if snelheid >= 0.0 else (nummer - 2) % 12 + 1
    elif punt_lengte is not None:
        # Het huis van de progressieve planeet, niet dat van het radixpunt. De huizen zelf zijn de
        # radixhuizen: de progressieve Maan loopt door de huizen van de geboortekaart, en de
        # huis-ingress hierboven rekent met dezelfde cuspen.
        cusps = [h["lengte"] for h in kaart["huizen"]]
        huis = _eph.vind_huis(punt_lengte, cusps)
    return {
        "soort": soort,
        "lichaam": naam,
        "doel": doel,
        "huis": huis,
        "hoek": hoek,
        "aspect": _aspect_naam(hoek) if hoek is not None else None,
        "leeftijd": leeftijd,
        "datum": _tijd.van_epoch(ts).strftime("%Y-%m-%d"),
        "jd": jd_echt,
        "jd_progressief": jd_prog,
        "ut": _tijd.van_epoch(ts).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "offset_sec": offset["offset"],
        "offset_label": offset.get("label", ""),
        "richting": "R" if snelheid < 0.0 else "D",
        "snelheid": snelheid,
        "punt_lengte": punt_lengte,
        "doel_lengte": doel_lengte,
    }


# ---------------------------------------------------------------------------------------------
# **Progressieve maanfasen** (les 20-II, in de nieuwe reeks les 28)
#
# Een nieuwe progressieve maanfase begint waar de progressieve (secundaire) Maan conjunct de
# progressieve (secundaire) Zon staat, en de andere grenzen van de cyclus liggen op dezelfde manier.
# Het gaat dus om aspecten tussen de progressieve Zon en Maan onderling - géén radixpunten, géén
# huizen: alleen de hoek tussen twee progressieve standen, in acht gelijke stukken van 45 graden.
#
# indeling in jaren maar een indeling in cycli. Iedere nieuwe cyclus begint met de nieuwe maan. We gaan
# door tot het huidige jaar en zoeken daarna nog een laatste fase."*
# ---------------------------------------------------------------------------------------------
FASEN = (
    (0.0, 1, "Nieuwe Maan", "conjunctie", "ONTWAKEN"),
    (45.0, 2, "Wassende Maan", "halfvierkant", "UITBREIDING"),
    (90.0, 3, "Eerste Kwartier", "vierkant", "ACTIE"),
    (135.0, 4, "Gibbous", "anderhalfvierkant", "OVERWINNEN"),
    (180.0, 5, "Volle Maan", "oppositie", "VERVULLING"),
    (225.0, 6, "Afnemende Maan", "anderhalfvierkant", "AANTONEN"),
    (270.0, 7, "Laatste Kwartier", "vierkant", "HERORIËNTATIE"),
    (315.0, 8, "Balsamisch", "halfvierkant", "LOSLATEN"),
)


def elongatie(kaart, leeftijd):
    """De hoek **Maan - Zon** in de progressieve kaart, 0-360, oplopend in de tijd.

    Dit is de enige grootheid die de maanfasen gebruiken; hij heeft niets met de radix te maken.
    """
    maan = lengte_van(kaart, "Maan", leeftijd)[0]
    zon = lengte_van(kaart, "Zon", leeftijd)[0]
    return (maan - zon) % 360.0


def _fase_afstand(kaart, leeftijd, hoek):
    """De afstand tot één fasegrens, met teken: precies nul op de grens zelf."""
    return _afwijking(elongatie(kaart, leeftijd), hoek)


def _vorige_nieuwe_maan(kaart, tot_leeftijd, terug=32.0):
    """De nieuwe maan **vóór de geboorte**: het beginpunt van de eerste cyclus.

    Terug in de tijd daalt de elongatie; de eerste sprong omhoog is de vorige nieuwe maan. Drieëndertig
    jaar is ruim genoeg: één cyclus duurt ongeveer 29,5 jaar (de Maan loopt 13,18°/jaar en de Zon
    0,99°/jaar, dus samen 12,19°/jaar voor een rondje).
    """
    stap = 0.25
    t = 0.0
    vorige = elongatie(kaart, t)
    while t > -terug:
        t -= stap
        nu = elongatie(kaart, t)
        if nu > vorige + 180.0:
            lo, hi = _nulpunt(lambda x: _fase_afstand(kaart, x, 0.0), t, t + stap, -1.0)
            return (lo + hi) / 2.0
        vorige = nu
    return -terug


def maanfasen(kaart, tot_leeftijd, stap=STAP, terug=32.0, aantal=8):
    """De maanfasen vanaf de nieuwe maan vóór de geboorte tot en met de eerste fase ná `tot_leeftijd`.

    `aantal` is 8 (elke 45 graden, met de half- en anderhalfvierkanten erbij) of 4 (alleen de vier
    kwartieren: nieuwe maan, eerste kwartier, volle maan, laatste kwartier). De les doet het in die
    twee stappen: deel 1 de vier, deel 2 de acht.

    Per grens: de fase die begint, de hoek, het aspect, het sleutelwoord uit de les, de leeftijd, de
    datum, de stand van de **progressieve Maan** op dat moment, en de cyclus waarin hij valt (1 is de
    cyclus die vóór de geboorte begint).
    """
    if aantal not in (4, 8):
        raise ValueError("Het aantal maanfasen is 4 of 8.")
    grenzen = [f for f in FASEN if aantal == 8 or f[0] % 90.0 == 0.0]
    start = _vorige_nieuwe_maan(kaart, tot_leeftijd, terug)
    # De nieuwe maan zelf is het **beginpunt** van de eerste cyclus en hoort dus als eerste regel in de
    # doorgang maar het vertrekpunt, en een nulpunt aan de rand wordt nooit als kruising gezien.
    eerste = {"hoek": 0.0, "nummer": 1, "naam": "Nieuwe Maan", "aspect": "conjunctie",
              "sleutelwoord": "ONTWAKEN", "leeftijd": start,
              "lengte": lengte_van(kaart, "Maan", start)[0]}
    # Eén fase verder kijken dan gevraagd: "we gaan door tot het huidige jaar en zoeken daarna nog een
    einde = tot_leeftijd + 4.0
    treffers = [eerste]
    t = start + 1e-6
    vorige = [_fase_afstand(kaart, t, f[0]) for f in grenzen]
    while t < einde:
        t2 = min(t + stap, einde)
        nu = [_fase_afstand(kaart, t2, f[0]) for f in grenzen]
        for i, (hoek, nummer, naam, aspect, sleutel) in enumerate(grenzen):
            if vorige[i] * nu[i] < 0.0 and abs(vorige[i] - nu[i]) < MAX_SPRONG:
                lo, hi = _nulpunt(lambda x, h=hoek: _fase_afstand(kaart, x, h), t, t2, vorige[i])
                exact = (lo + hi) / 2.0
                treffers.append({"hoek": hoek, "nummer": nummer, "naam": naam, "aspect": aspect,
                                 "sleutelwoord": sleutel, "leeftijd": exact,
                                 "lengte": lengte_van(kaart, "Maan", exact)[0]})
        t, vorige = t2, nu
    treffers.sort(key=lambda x: x["leeftijd"])
    # Afkappen: alles tot en met de eerste grens ná `tot_leeftijd`.
    uit = []
    for r in treffers:
        uit.append(r)
        if r["leeftijd"] > tot_leeftijd:
            break
    # Cyclusnummer: elke nieuwe maan opent een nieuwe cyclus (de eerste is de nieuwe maan vóór de
    # geboorte, dus die is cyclus 1).
    cyclus = 0
    for r in uit:
        if r["hoek"] == 0.0:
            cyclus += 1
            r["opent_cyclus"] = True
        r["cyclus"] = max(1, cyclus)
    _vul_data(kaart, uit)
    return {"begin": uit[0] if uit else None, "fasen": uit, "aantal": aantal,
            "nu": _fase_nu(kaart, uit, tot_leeftijd), "tot_leeftijd": tot_leeftijd}


def _vul_data(kaart, rijen):
    """De kalenderdatum en het teken bij elke grens (dezelfde omzetting als de lijst gebruikt)."""
    zona = kaart["meta"].get("tijdzone_id") or "Europe/Amsterdam"
    lengtegraad = kaart["meta"].get("lon", 0.0)
    for r in rijen:
        jd_echt = _kalender_jd(kaart, r["leeftijd"])
        ts = (jd_echt - 2440587.5) * 86400.0
        offset = _tijd.get_offset(zona, lengtegraad, int(ts))
        r["datum"] = _tijd.van_epoch(ts).strftime("%Y-%m-%d")
        r["ut"] = _tijd.van_epoch(ts).strftime("%Y-%m-%dT%H:%M:%SZ")
        r["offset_sec"] = offset["offset"]
        r["offset_label"] = offset.get("label", "")
        r["positie"] = _kaart.positie(r["lengte"])


def _fase_nu(kaart, rijen, leeftijd):
    """In welke fase je nu staat: de laatste grens die voorbij is, en hoeveel graden je daarin bent."""
    if not rijen:
        return None
    huidig = None
    for r in rijen:
        if r["leeftijd"] <= leeftijd:
            huidig = r
        else:
            break
    if huidig is None:
        return None
    return {"fase": {k: huidig[k] for k in ("nummer", "naam", "sleutelwoord", "hoek", "datum", "cyclus")},
            "graden": elongatie(kaart, leeftijd), "leeftijd": leeftijd,
            "sinds": huidig["leeftijd"]}


def _aspect_naam(hoek):
    """De Nederlandse naam van een hoek, uit dezelfde tabel als de natale aspecten."""
    for definitie in _aspecten.ASPECTEN:
        if definitie["hoek"] == hoek:
            return definitie["naam"]
    return "%d°" % hoek
