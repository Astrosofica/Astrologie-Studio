"""Transits op een radix — jaar 2 (besluit T49).

**Wat dit bestand doet**: een transit is *timing*. De lijst toont de momenten waarop
een aspect **exact** is — niet wat er binnen een orb staat. De orb hoort bij de natal aspectenlijst;
hier is de enige grootheid de tijd. Daarnaast is er de **momentopname**: de standen van dit moment met
hun radixhuis.

**De regels die vastliggen:**

- Aspecten alleen tussen **planeten onderling** en tussen **planeten en de hoeken** (Ascendant, MC).
  Geen Noordknoop, geen pars, geen Chiron — dezelfde regel als de natal lijst (`aspecten.WEG_PUNT`,
  T42). De knoop mag in de momentopname als *stand* staan, want dat is geen aspect.
- **Zeven aspecten**: 0, 45, 60, 90, 120, 135, 180. De 150 doet niet mee: voor transits van minder
  belang. De set is een **parameter**: het formulier vinkt ze per stuk aan.
- **De tijd is de uitkomst**, ook bij Jupiter t/m Pluto: het moment van exactheid tot op de seconde.
  (In de PHP-versie komt de doorgang uit een tabel met dagstanden en is de uitkomst een *dag*; die
  resolutie is daar genoeg omdat snelle lichamen niet meededen. Hier doen ze mee en telt de tijd.)
- **Drie soorten regels**, in één lijst en op één tijdlijn:
  - `aspect` — een transiterend lichaam raakt een radixpunt op een hoek;
  - `huis_ingress` — een transiterend lichaam kruist een radixcusp;
  - `station` — een lichaam keert om van direct naar retrograde of terug (bestaat niet in de PHP-versie;
    daar is `speed < 0` alleen een ℞ in het wiel).
- **De methode** is die van T6/T12: één scan per lichaam over het venster, alle doelen in dezelfde
  doorgang, daarna bisectie voor het moment. Geen positietabel, geen database.

**Wat dit bestand niet doet:** een orb berekenen en iets tekenen. De weergave hoort in de schil.
"""

from __future__ import annotations

from . import aspecten as _aspecten
from . import efemeride as _eph
from . import kaart as _kaart
from . import tijd as _tijd

# De tien lichamen die mogen transiteren. Chiron doet niet mee,
# de Noordknoop en de pars zijn geen planeten.
LICHAMEN = ("Zon", "Maan", "Mercurius", "Venus", "Mars",
            "Jupiter", "Saturnus", "Uranus", "Neptunus", "Pluto")

# De vijf die de PHP-versie aanbood, omdat de rest op een webserver te veel tijd kostte. Hier is dat geen grens meer, maar het blijft de nuttigste stand: dit zijn de
 # lichamen waar een periode-lijst over gaat.
TRAGE = ("Jupiter", "Saturnus", "Uranus", "Neptunus", "Pluto")
SNELLE = ("Zon", "Maan", "Mercurius", "Venus", "Mars")

HOEKEN = ("Ascendant", "MC")

# Zeven aspecten, geen 150.
ASPECTEN = (0, 45, 60, 90, 120, 135, 180)

# De drie soorten regels die deze module oplevert.
SOORTEN = ("aspect", "huis_ingress", "station")

# Stap van de scan, in dagen. Een halve dag is ruim genoeg: de snelste hier is de Maan met ± 7,2° per
# halve dag, en de bisectie zoekt het moment daarna tot op de milliseconde. Fijner stappen maakt de
# uitkomst niet nauwkeuriger.
STAP = 0.5

# Waar de bisectie ophoudt: 1e-8 dag is 0,86 ms.
FIJN = 1e-8

# Een lichaam kan in één stap geen 45° lopen; een tekenwissel met zo'n sprong is geen doorgang maar een
# sprong in de efemeride (of een verkeerd punt).
MAX_SPRONG = 45.0

MAX_SLAGEN = 80

# Hoe vaak de voortgang wordt gemeld binnen één lichaam (het venster in dit aantal delen).
VOORTGANG_STAPPEN = 20

# **Stations.** De snelheid die swisseph teruggeeft is dicht bij een station te ruisig om de doorgang
# de werkelijke snelheid daar ± 1,6e-8 °/dag is. Daarom zoeken we een station met een centrale differens
# over ± 43 minuten: de ruis valt weg en het nulpunt schuift hooguit ± 1 s (de verschuiving schaalt met
# het kwadraat van de basislijn: 0,125 dag gaf 13 s, 0,25 dag 6 s, 1 dag 129 s).
STATION_H = 0.03        # dag
GRENS_STATION = 0.01    # °/dag: hieronder is de ruwe snelheid niet meer te vertrouwen

# Nulpunt van de Juliaanse dag in epoch-seconden.
_JD_EPOCH = 2440587.5


def _afwijking(lengte, punt):
    """Afstand van een stand tot een punt, in (-180, 180] — het teken zegt aan welke kant hij staat."""
    return (lengte - punt + 180.0) % 360.0 - 180.0


def doelen(kaart, namen=None):
    """De radixdoelen van de transits: standaard de tien planeten plus Ascendant en MC.

    `namen` beperkt dat tot wat het formulier heeft aangevinkt. Een dict `naam -> lengte`; de volgorde
    is die van de kaart, zodat de lijst niet per ronde anders sorteert.
    """
    uit = {}
    for punt in kaart["punten"]:
        if namen is not None:
            if punt["naam"] in namen:
                uit[punt["naam"]] = punt["lengte"]
            continue
        if punt["naam"] in LICHAMEN or punt["naam"] in HOEKEN:
            uit[punt["naam"]] = punt["lengte"]
    return uit


def cuspen(kaart):
    """De twaalf cuspen als `[(naam, lengte)]`, voor de huis-ingress."""
    return [("cusp %d" % huis["nr"], huis["lengte"]) for huis in kaart["huizen"]]


def gevoelige_punten(kaart, aspecten=ASPECTEN, doelnamen=None, huis_ingress=False):
    """De punten die een transiterend lichaam kan raken: `[(doel, hoek, puntlengte, soort)]`.

    Twee per aspect (doel + hoek en doel − hoek), behalve bij 0 en 180: daar vallen beide samen en dan
    zou elke doorgang twee keer in de lijst staan. Dit is dezelfde opbouw als de PHP-versie. Een cusp is
    één punt (geen ± paar) en heeft geen hoek: dat is de `huis_ingress`-soort.
    """
    uit = []
    for naam, lengte in doelen(kaart, doelnamen).items():
        for hoek in aspecten:
            uit.append((naam, hoek, (lengte + hoek) % 360.0, "aspect"))
            if hoek != 0 and hoek != 180:
                uit.append((naam, hoek, (lengte - hoek) % 360.0, "aspect"))
    if huis_ingress:
        for naam, lengte in cuspen(kaart):
            uit.append((naam, None, lengte % 360.0, "huis_ingress"))
    return uit


def _iso_ut(jd):
    """Het UT-moment van een Juliaanse dag als `JJJJ-MM-DDTHH:MM:SSZ` (hele seconden)."""
    ts = (jd - _JD_EPOCH) * 86400.0
    return _tijd.van_epoch(ts).strftime("%Y-%m-%dT%H:%M:%SZ")


def _tijdstempel(jd):
    return (jd - _JD_EPOCH) * 86400.0


def standen(jd, kaart, met_knoop=True):
    """De momentopname: de standen van dit moment, met hun **radixhuis**.

    Dit is wat de PHP-versie op zijn tab *Transits* toont: positie, richting (D of R) en het huis van de
    radix. De huizen zijn dus de **geboortehuizen** — de locatie van nu speelt hier geen rol, en de
    hoeken van dit moment staan er niet in (die horen bij de horoscoop van nu, niet bij deze tabel).
    """
    cusps = [huis["lengte"] for huis in kaart["huizen"]]
    namen = list(LICHAMEN) + (["Noordknoop"] if met_knoop else [])
    uit = []
    for naam in namen:
        lengte, snelheid = _eph.stand_van(naam, jd)
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




def _snelheid(naam, jd, h=STATION_H):
    """Snelheid in graden per dag als centrale differens over ±h.

    Alleen voor het vinden van een **station**: de snelheid van swisseph zelf is daar te ruisig (zie
    GRENS_STATION). Over een kwartier aan weerskanten is de positie glad genoeg (gemeten: 5e-11°) en
    valt de ruis weg.
    """
    voor = _eph.stand_van(naam, jd - h)[0]
    na = _eph.stand_van(naam, jd + h)[0]
    return ((na - voor + 180.0) % 360.0 - 180.0) / (2.0 * h)


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


def doorgangen(kaart, van_jd, tot_jd, lichamen=None, aspecten=ASPECTEN, doelnamen=None,
               huis_ingress=False, stations=False, stap=STAP, voortgang=None):
    """De momenten waarop iets **exact** gebeurt: een aspect, een cuspkruising of een station.

    Per regel: het lichaam, de soort (`aspect`, `huis_ingress`, `station`), het radixdoel en de hoek
    (leeg bij een cusp of een station), het moment (Juliaanse dag, UT en de zone-offset van de kaart) en
    de richting (D of R).

    `lichamen` is standaard de vijf trage; geef `LICHAMEN` mee voor alle tien. `aspecten` en `doelnamen`
    zijn de selectie uit het formulier. `voortgang` is een functie die per 1/VOORTGANG_STAPPEN van het
    venster wordt aangeroepen met `{"lichaam", "index", "totaal", "fractie", "doorgangen"}`; de schil
    schrijft daar haar voortgangsregel mee. De verhouding `(index + fractie) / totaal`
    is de voortgang over álle gekozen lichamen en ligt tussen 0 en 1.
    """
    if lichamen is None:
        lichamen = TRAGE
    onbekend = [n for n in lichamen if n not in LICHAMEN]
    if onbekend:
        raise ValueError("Onbekend transiterend lichaam: %s" % ", ".join(onbekend))
    if tot_jd <= van_jd:
        raise ValueError("Het einde van de periode moet na het begin liggen.")
    for hoek in aspecten:
        if hoek not in ASPECTEN:
            raise ValueError("Onbekende hoek: %s" % hoek)

    zona = kaart["meta"].get("tijdzone_id") or "Europe/Amsterdam"
    lengtegraad = kaart["meta"].get("lon", 0.0)
    punten = gevoelige_punten(kaart, aspecten or (), doelnamen, huis_ingress)
    lengtes = doelen(kaart)
    breedte = tot_jd - van_jd

    treffers = []
    for nummer, naam in enumerate(lichamen):
        vorige_jd = van_jd
        vorige_lengte, vorige_snelheid = _eph.stand_van(naam, vorige_jd)
        jd = vorige_jd
        volgende_melding = 1
        while jd < tot_jd:
            jd = min(jd + stap, tot_jd)
            lengte, snelheid = _eph.stand_van(naam, jd)

            for doel, hoek, punt, soort in punten:
                a = _afwijking(vorige_lengte, punt)
                b = _afwijking(lengte, punt)
                # Een tekenwissel tussen twee stappen is een doorgang; de sprongwacht houdt een sprong
                # van 180° (verkeerd punt, of een gat in de efemeride) eruit.
                if a * b < 0.0 and abs(a - b) < MAX_SPRONG:
                    lo, hi = _nulpunt(
                        lambda t, n=naam, p=punt: _afwijking(_eph.stand_van(n, t)[0], p),
                        vorige_jd, jd, a)
                    exact = (lo + hi) / 2.0
                    _, s_exact = _eph.stand_van(naam, exact)
                    treffers.append(_regel(kaart, zona, lengtegraad, naam, soort, exact, s_exact,
                                           doel=doel, hoek=hoek, punt_lengte=punt,
                                           doel_lengte=punt if soort == "huis_ingress"
                                           else lengtes.get(doel)))

            # Een station: de snelheid wisselt van teken. Dicht bij nul is de ruwe snelheid niet te
            # vertrouwen, dus daar nemen we de gladde centrale differens (zie STATION_H).
            if stations:
                s_vorig, s_nu = vorige_snelheid, snelheid
                if abs(s_vorig) < GRENS_STATION:
                    s_vorig = _snelheid(naam, vorige_jd)
                if abs(s_nu) < GRENS_STATION:
                    s_nu = _snelheid(naam, jd)
                if s_vorig * s_nu < 0.0:
                    lo, hi = _nulpunt(lambda t, n=naam: _snelheid(n, t), vorige_jd, jd, s_vorig)
                    exact = (lo + hi) / 2.0
                    lengte_exact, _ = _eph.stand_van(naam, exact)
                    # De richting komt van ná het moment: op het station zelf is de snelheid nul.
                    treffers.append(_regel(kaart, zona, lengtegraad, naam, "station", exact,
                                           _snelheid(naam, jd), punt_lengte=lengte_exact))

            vorige_jd, vorige_lengte, vorige_snelheid = jd, lengte, snelheid

            if voortgang is not None:
                fractie = (jd - van_jd) / breedte
                if fractie * VOORTGANG_STAPPEN >= volgende_melding:
                    volgende_melding += 1
                    voortgang({"lichaam": naam, "index": nummer, "totaal": len(lichamen),
                               "fractie": fractie, "doorgangen": len(treffers)})

        if voortgang is not None:
            # `index` is het nummer van het lichaam dat nú gedaan is (0-based) en `fractie` het deel
            # van zijn venster: (index + fractie) / totaal loopt dus van 0 naar 1 en nooit erover.
            voortgang({"lichaam": naam, "index": nummer, "totaal": len(lichamen),
                       "fractie": 1.0, "doorgangen": len(treffers)})

    treffers.sort(key=lambda t: t["jd"])
    return {
        "van_jd": van_jd,
        "tot_jd": tot_jd,
        "lichamen": list(lichamen),
        "soorten": sorted({t["soort"] for t in treffers}),
        "doorgangen": treffers,
    }


# Hoe ver de momentopname vooruitkijkt naar het eerstvolgende aspect. Vijf jaar is niet willekeurig: op de
# proefkaart is Pluto met de zeven hoeken 3,3 jaar onderweg naar zijn eerstvolgende exacte aspect en
# Neptunus 93 dagen. Met deze horizon heeft elk lichaam er één, blijft de berekening onder een kwart
# seconde (gemeten 0,13 s voor alle tien) en hoeft er geen voortgangsbalk bij. Wie verder kijkt, gebruikt
# de periode-lijst - daar is de horizon het tijdvak dat de gebruiker zelf invult.
VOLGEND_HORIZON = 5 * 365.25


def volgende(kaart, van_jd, lichamen=None, aspecten=ASPECTEN, horizon=VOLGEND_HORIZON, stap=STAP):
    """Het **eerstvolgende** exacte aspect per transiterend lichaam, vanaf `van_jd`.

    Geeft `{naam: regel of None}` in de volgorde van `lichamen`; `None` betekent: binnen de horizon wordt
    niets exact. De regel heeft dezelfde vorm als die van `doorgangen()`.

    **Waarom dit niet gewoon `doorgangen()` over de horizon is.** Een periode-lijst sorteert achteraf;
    hier is de vraag per lichaam "wat is het eerst", en dan mag de scan stoppen zodra het antwoord vast
    staat. Dat scheelt bij de trage lichamen jaren aan efemeride-aanroepen: de Maan is na één stap klaar,
    Pluto pas na 2.400.

    **De valkuil die erin zit.** Binnen één stap van een halve dag kan de Maan méér dan één punt passeren
    (gemeten: 11:09 sextiel Venus en 16:31 halfvierkant Mercurius zitten in dezelfde stap).
    Wie de eerste treffer van de binnenste lus neemt, krijgt dus niet de vroegste - daarom houdt deze lus
    de **vroegste van de stap** bij en stopt pas daarna.
    """
    if lichamen is None:
        lichamen = LICHAMEN
    onbekend = [n for n in lichamen if n not in LICHAMEN]
    if onbekend:
        raise ValueError("Onbekend transiterend lichaam: %s" % ", ".join(onbekend))
    for hoek in aspecten:
        if hoek not in ASPECTEN:
            raise ValueError("Onbekende hoek: %s" % hoek)

    zona = kaart["meta"].get("tijdzone_id") or "Europe/Amsterdam"
    lengtegraad = kaart["meta"].get("lon", 0.0)
    punten = gevoelige_punten(kaart, aspecten or ())
    lengtes = doelen(kaart)
    einde = van_jd + horizon
    uit = {}

    for naam in lichamen:
        vorige_jd = van_jd
        vorige_lengte, _s = _eph.stand_van(naam, vorige_jd)
        jd = vorige_jd
        beste = None
        while jd < einde:
            jd = min(jd + stap, einde)
            lengte, _s = _eph.stand_van(naam, jd)
            for doel, hoek, punt, soort in punten:
                a = _afwijking(vorige_lengte, punt)
                b = _afwijking(lengte, punt)
                if a * b < 0.0 and abs(a - b) < MAX_SPRONG:
                    lo, hi = _nulpunt(
                        lambda t, n=naam, p=punt: _afwijking(_eph.stand_van(n, t)[0], p),
                        vorige_jd, jd, a)
                    moment = (lo + hi) / 2.0
                    if beste is None or moment < beste[0]:
                        beste = (moment, doel, hoek, punt)
            vorige_jd, vorige_lengte = jd, lengte
            if beste is not None:
                break
        if beste is None:
            uit[naam] = None
            continue
        moment, doel, hoek, punt = beste
        _, s_exact = _eph.stand_van(naam, moment)
        uit[naam] = _regel(kaart, zona, lengtegraad, naam, "aspect", moment, s_exact,
                           doel=doel, hoek=hoek, punt_lengte=punt, doel_lengte=lengtes.get(doel))
    return uit


def _regel(kaart, zona, lengtegraad, naam, soort, exact, snelheid, doel=None, hoek=None,
           punt_lengte=None, doel_lengte=None):
    """Eén regel van de lijst, in de vorm die de schil leest."""
    ts = _tijdstempel(exact)
    offset = _tijd.get_offset(zona, lengtegraad, ts)
    # Een huis ingress: welk huis ga je **in**? Een commercieel programma noemt bij een ingress het huis dat je
    # binnenkomt, en dat is ook wat een cursist nodig heeft: "hij gaat retrograde huis 11 in" in
    # plaats van "over cusp 12, R".
    huis = None
    if soort == "huis_ingress" and doel and doel.startswith("cusp "):
        nummer = int(doel.split()[-1])
        huis = nummer if snelheid >= 0.0 else (nummer - 2) % 12 + 1
    elif punt_lengte is not None:
        # Het huis van de **transitplaneet**, niet van het radixpunt: dat laatste is een vast gegeven,
        # en wat je wilt weten is waar de **transiterende** Uranus staat. De cuspen zijn dezelfde als
        # die van de momentopname.
        cusps = [huis["lengte"] for huis in kaart["huizen"]]
        huis = _eph.vind_huis(punt_lengte, cusps)
    return {
        "soort": soort,
        "lichaam": naam,
        "doel": doel,
        "huis": huis,
        "hoek": hoek,
        "aspect": _aspect_naam(hoek) if hoek is not None else None,
        "jd": exact,
        "ut": _iso_ut(exact),
        "offset_sec": offset["offset"],
        "offset_label": offset.get("label", ""),
        "richting": "R" if snelheid < 0.0 else "D",
        "snelheid": snelheid,
        "punt_lengte": punt_lengte,
        "doel_lengte": doel_lengte,
    }


def _aspect_naam(hoek):
    """De Nederlandse naam van een hoek, uit dezelfde tabel als de natal aspecten."""
    for definitie in _aspecten.ASPECTEN:
        if definitie["hoek"] == hoek:
            return definitie["naam"]
    return "%d°" % hoek
