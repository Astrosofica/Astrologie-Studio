"""Plaatsen: de lijst waaruit het invulscherm een plaats opzoekt (besluit T19).

Twee bestanden, allebei gewoon te lezen:

  - `data/plaatsen.json` - de gedownloade lijst (GeoNames, CC BY 4.0), gebouwd met
    `data/maak-plaatsen.py`: elke bewoonde plaats van Nederland en Belgie met al zijn
    naamsvarianten, plus de plaatsen elders in de wereld vanaf 15.000 inwoners (met varianten vanaf
    100.000 inwoners). De plaatsen staan er **een keer** in, met de namen als verwijzingen:

        "plaatsen": [[naam, breedte, lengte, land, zone, inwoners, streek, gemeente], ...]
        "streken":  ["Overijssel", "Gelderland", ...]      (streek en gemeente zijn nummers hierin)
        "namen":    {"dieren": [123], "antwerpen": [456], ...}

    De laatste twee velden zijn het **streek- en gemeentelabel**: gelijknamige plaatsen zijn anders
    alleen aan hun coordinaten te onderscheiden en die zeggen een
    gebruiker niets. Welk veld dat per land is staat in `etiketten` in het bestand: Nederland de
    provincie en de gemeente, Belgie de provincie (adm2, want adm1 is daar alleen het gewest) en de
    gemeente, elders de adm1-naam en geen gemeente. `etiket()` hieronder maakt er het label van dat
    de keuzelijst toont - een ontbrekend veld laat hij gewoon weg.

  - `data/eigen-plaatsen.tsv` - eigen aanvullingen van de gebruiker, **over** de gedownloade lijst heen
    (nooit de gedownloade lijst zelf bewerken: die wordt bij een volgende build vervangen).
    Vorm, een plaats per regel, velden met een tab ertussen:

        naam<TAB>breedte<TAB>lengte<TAB>land<TAB>zone[<TAB>streek[<TAB>gemeente]]
        Mijn ouderlijk huis<TAB>52.0529<TAB>6.0995<TAB>NL<TAB>Europe/Amsterdam<TAB>Gelderland

    Een regel die met # begint en een lege regel worden overgeslagen; ontbreekt het land of de zone,
    dan wordt de zone van het land genomen (NL/BE); blijft die leeg, dan zegt de lezer van de invoer
    dat de zone onbekend is in plaats van er iets van te maken. De streek en de gemeente zijn vrij:
    laat je ze weg, dan toont het label alleen de naam en het land.


De gedownloade lijst wordt een keer gelezen en onthouden; het eigen bestand bij elke vraag, zodat een
aanvulling meteen werkt zonder de schil te herstarten (net als `teken/spec.json`).
"""

from __future__ import annotations

import bisect
import datetime
import json
import math
import os
import unicodedata
import zoneinfo

from .invoer import InvoerFout
from . import paden

BESTAND = paden.bron("data", "plaatsen.json")
# De eigen aanvullingen staan in de gebruikersmap en niet meer in de
# projectmap: in een bundel is de projectmap een tijdelijke uitleesmap, dus wat je daar schrijft
# is bij de volgende start weg. `TEMPLATE` is de meegeleverde lege lijst met de uitleg in de kop;
# die wordt bij het eerste gebruik naar de gebruikersmap gekopieerd, zodat er iets te bewerken valt.
TEMPLATE = paden.bron("data", "eigen-plaatsen.tsv")
EIGEN = paden.gebruikersmap("eigen-plaatsen.tsv")

ZONE_VAN_LAND = {"NL": "Europe/Amsterdam", "BE": "Europe/Brussels"}
LIMIET = 20
# Een lege tijdzone wordt opgezocht bij de coördinaten: een cursist kent geen IANA-naam, dus neemt
# het script hem over. We zoeken een plaats in hetzelfde land binnen
# deze straal; in landen met meer dan één zone (VS, Rusland, Brazilië) eerst een grote plaats, want
# die draagt de zone van zijn eigen streek.
ZONE_ZOEK_KM = 300.0
# 25.000 inwoners. Lager grijpt eerder raak en geeft de zone van de eigen streek; hoger zou in dun bezette
# landen telkens naar een stad verderop grijpen. In Nederland en België doet deze trap weinig: die
# lijst is heel fijnmazig (elk gehucht, maar GeoNames vult daar zelden een inwonertal), en het land
# heeft toch één zone.
ZONE_GROTE_STAD = 25000
MAX_NAAMVAK = 2000        # hoeveel namen per stap hoogstens worden nagelopen

_lijst: list = []
_namen: dict = {}
_sleutels: list = []
_streken: list = []
_bron: dict = {}
_gevuld = False


def _zonder_accenten(tekst):
    s = unicodedata.normalize("NFKD", str(tekst)).encode("ascii", "ignore").decode()
    return s.lower().strip()


def laad():
    """De gedownloade lijst, een keer in het geheugen. Geeft (plaatsen, namen, sleutels)."""
    global _lijst, _namen, _sleutels, _streken, _bron, _gevuld
    if not _gevuld:
        try:
            with open(BESTAND, encoding="utf-8") as f:
                inhoud = json.load(f)
            _lijst = inhoud.get("plaatsen", []) if isinstance(inhoud, dict) else []
            _namen = inhoud.get("namen", {}) if isinstance(inhoud, dict) else {}
            _streken = inhoud.get("streken", []) if isinstance(inhoud, dict) else []
            _bron = inhoud if isinstance(inhoud, dict) else {}
        except Exception:
            _lijst, _namen, _streken, _bron = [], {}, [], {}
        _sleutels = sorted(_namen)
        _gevuld = True
    return _lijst, _namen, _sleutels


def bron():
    """Wat er in de lijst zit: bron, licentie, datum en aantallen (voor het scherm).

    Leest niets opnieuw: het bestand is bij `laad()` al een keer gelezen. Zonder dat was deze
    functie per verzoek 300 ms bezig (gemeten) omdat de pagina hem bij elke
    toetsaanslag vraagt.
    """
    laad()
    return {sleutel: _bron.get(sleutel) for sleutel in
            ("bron", "licentie", "gebouwd", "aantal", "aantallen")}


def _streek(plaats, plek):
    """De naam uit de `streken`-tabel waar een plaats met een nummer naar verwijst.

    Een nummer buiten de tabel (of -1, geen streek) geeft een lege tekst: een plaats zonder streek
    is geen fout, want buiten Nederland en Belgie is er vaak geen.
    """
    if len(plaats) <= plek:
        return ""
    nummer = plaats[plek]
    if not isinstance(nummer, int) or nummer < 0 or nummer >= len(_streken):
        return ""
    return _streken[nummer] or ""


def _labeldelen(plaats):
    """De stukjes achter de naam: de gemeente (alleen als die anders heet), de streek, het land.

    De regel: de gemeente alleen als die **anders** heet dan de
    plaats zelf, anders lees je "Hengelo, Hengelo, Overijssel". Wat er ontbreekt wordt overgeslagen,
    dus een eigen aanvulling zonder streek geeft gewoon "Zomerhuis, IT". Enkele waarheid voor het
    label in de keuzelijst en voor de meldregel na het kiezen.
    """
    laad()
    uit = []
    gemeente = _streek(plaats, 7)
    if gemeente and gemeente.lower() != plaats[0].lower():
        uit.append("gem. " + gemeente)
    streek = _streek(plaats, 6)
    if streek:
        uit.append(streek)
    if len(plaats) > 3 and plaats[3]:
        uit.append(plaats[3].upper())
    return uit


def etiket(plaats):
    """Het volledige label van een plaats: naam, gemeente (indien afwijkend), streek en land."""
    return ", ".join([plaats[0]] + _labeldelen(plaats))


def onder(plaats):
    """De tweede regel van een rij in de keuzelijst: alles behalve de naam."""
    return ", ".join(_labeldelen(plaats))


_accent_nummers = None


def _accentloze_nummers():
    """De naamindex nog eens, maar op de **accentloze** vorm van elke sleutel.

    De index heeft de naam én de naamvarianten als sleutel ("hünningen" en "huenningen"), maar de
    accentloze vorm staat er niet voor elke plaats bij: "hunningen" wijst naar één van de twee
    Hünningens. Wie op de accentloze vorm zoekt, mist er dan een. Gemeten: bij
    1175 namen is de accentloze sleutel onvolledig — "t zand" heeft er drie van de vijf, en de twee
    die ontbreken zijn net de plaatsen waar de coördinatencontrole op afgaat.

    Een keer bouwen (over de 11 duizend sleutels die een accent hebben, ±60 ms) en daarna zoeken.
    """
    global _accent_nummers
    if _accent_nummers is None:
        _, namen, _ = laad()
        _accent_nummers = {}
        for sleutel, nummers in namen.items():
            kaal = _zonder_accenten(sleutel)
            if kaal != sleutel:
                _accent_nummers.setdefault(kaal, set()).update(nummers)
    return _accent_nummers


def _naamgenoten(naam):
    """Alle plaatsen die precies zo heten: (plaats, uit de eigen lijst?).

    Bewust langs de naamindex en niet langs `zoek()`/`kandidaten()`: die bouwen treffers met een
    etiket, en het etiket van een treffer vraagt weer om `kort()` — een lus. Deze weg doet alleen
    de opzoeking, en wel langs beide kanten van de index, zodat een accent geen naamgenoot kwijt
    maakt.
    """
    plaatsen, namen, _ = laad()
    eigen_plaatsen, eigen_namen = eigen()
    vraag = _zonder_accenten(naam or "")
    if len(vraag) < 2:
        return []
    nummers = list(eigen_namen.get(vraag, []))
    uit = [(eigen_plaatsen[i], True) for i in nummers]
    nummers = list(namen.get(vraag, []))
    for nummer in _accentloze_nummers().get(vraag, ()):
        if nummer not in nummers:
            nummers.append(nummer)
    for nummer in nummers:
        plaats = plaatsen[nummer]
        if _zonder_accenten(plaats[0]) == vraag:
            uit.append((plaats, False))
    return uit


def kort(plaats):
    """Het kortste label dat deze plaats tussen zijn naamgenoten eenduidig maakt.

    Het volledige etiket is vaak te veel ("Langstraat, gem.
    Goeree-Overflakkee, Zuid-Holland, NL") en alleen de naam soms te weinig ("Langstraat" bestaat
    drie keer). In plaats van een keuzemenu met formats bepaalt de lijst zelf de lengte: knip
    niveaus van rechts af zolang het label eenduidig blijft. Zo blijft "Dieren" gewoon "Dieren", en
    wordt "Langstraat" tot "Langstraat, gem. Goeree-Overflakkee" — het eerste niveau dat de knoop
    doorhakt, en niet één woord meer.

    Is de naam al uniek, dan is dat de uitkomst; blijven zelfs met land erbij twee plaatsen gelijk
    (dubbelen in de bron), dan is het volledige etiket de beste die we hebben.
    """
    volledig = etiket(plaats).split(", ")
    anderen = [p for p, _ in _naamgenoten(plaats[0])]
    if len(anderen) <= 1:
        return plaats[0]
    for aantal in range(2, len(volledig) + 1):
        labels = [", ".join(etiket(x).split(", ")[:aantal]) for x in anderen]
        if len(set(labels)) == len(labels):
            return ", ".join(volledig[:aantal])
    return etiket(plaats)


def _zorg_voor_bestand():
    """Zet de meegeleverde lege lijst neer als de gebruiker er nog geen heeft.

    Zo staat de uitleg over de vorm van het bestand meteen in de map waarin de gebruiker het
    mag bewerken, en niet in de programmamap (die in een bundel tijdelijk is).
    """
    if os.path.exists(EIGEN):
        return
    try:
        os.makedirs(os.path.dirname(EIGEN), exist_ok=True)
        if os.path.exists(TEMPLATE):
            with open(TEMPLATE, encoding="utf-8") as bron_bestand:
                tekst = bron_bestand.read()
        else:
            tekst = "# Eigen plaatsen voor het invulscherm.\n"
        with open(EIGEN, "w", encoding="utf-8") as doel:
            doel.write(tekst)
    except OSError:
        # Niet kunnen aanmaken is geen reden om het zoeken te laten mislukken: dan is er
        # eenvoudigweg geen eigen lijst.
        pass


def eigen():
    """De eigen aanvullingen: (plaatsen, namen) uit de eigen lijst in de gebruikersmap.

    Naast de vijf vaste velden mogen er twee vrije velden achteraan staan: de streek en de gemeente
    (zie de kop van `data/eigen-plaatsen.tsv`, het meegeleverde voorbeeld). Ze komen in dezelfde
    nummertabel terecht als die van de gedownloade lijst, zodat `etiket()` er hetzelfde mee omgaat.
    """
    plaatsen, namen = [], {}
    _zorg_voor_bestand()
    if not os.path.exists(EIGEN):
        return plaatsen, namen
    with open(EIGEN, encoding="utf-8") as f:
        for regel in f:
            regel = regel.strip()
            if not regel or regel.startswith("#"):
                continue
            delen = [d.strip() for d in regel.split("\t")]
            if len(delen) < 3:
                continue
            try:
                lat = float(delen[1].replace(",", "."))
                lon = float(delen[2].replace(",", "."))
            except ValueError:
                continue
            land = (delen[3].upper() if len(delen) > 3 else "")
            zone = (delen[4] if len(delen) > 4 else "") or ZONE_VAN_LAND.get(land, "")
            nummer = len(plaatsen)
            plaatsen.append([delen[0], lat, lon, land, zone, 0] + _eigen_nummers(delen))
            sleutel = _zonder_accenten(delen[0])
            if sleutel and nummer not in namen.setdefault(sleutel, []):
                namen[sleutel].append(nummer)
    return plaatsen, namen


def _eigen_nummers(delen):
    """De vrije streek- en gemeentekolommen van een eigen regel als nummers in de `streken`-tabel.

    De namen uit het eigen bestand staan niet in de tabel van `plaatsen.json` (dat bestand wordt
    opnieuw gemaakt), dus ze worden hier achteraan toegevoegd. Dat gebeurt bij elke vraag opnieuw en
    dat is met een handvol regels geen werk; de eerste keer laden levert de nummers van de tabel.
    """
    laad()
    nummers = []
    for plek in (5, 6):
        naam = delen[plek] if len(delen) > plek else ""
        if naam and naam in _streken:
            nummers.append(_streken.index(naam))
        elif naam:
            _streken.append(naam)
            nummers.append(len(_streken) - 1)
        else:
            nummers.append(-1)
    return nummers


def _treffer(plaats, eigen_plaats):
    laad()
    return {"naam": plaats[0], "lat": plaats[1], "lon": plaats[2], "land": plaats[3],
            "zone": plaats[4], "inwoners": plaats[5] if len(plaats) > 5 else 0,
            "streek": _streek(plaats, 6), "gemeente": _streek(plaats, 7),
            "etiket": etiket(plaats), "onder": onder(plaats), "kort": kort(plaats),
            "eigen": eigen_plaats}


def voeg_eigen_toe(naam, lat, lon, land="", zone="", streek="", gemeente="", bron=""):
    """Een plaats toevoegen aan `data/eigen-plaatsen.tsv` — de schrijfkant.

    Tot nu toe was het eigen bestand alleen te lézen: je moest het met de hand openen en de
    coordinaten zelf kennen. Deze functie doet hetzelfde, met de keuring die erbij hoort:

      - geen tab of regeleinde in een veld (dat breekt het bestand),
      - coordinaten binnen hun bereik, met een komma of een punt als decimaalteken,
      - een zone die leeg mag zijn als het land hem kent (`ZONE_VAN_LAND`), maar als hij ingevuld
        is moet het een bestaande IANA-zone zijn — anders reken je straks met LMT zonder het te
        weten.

    Staat dezelfde plaats (naam en coordinaten) er al in, dan wordt er niets bijgeschreven en komt
    `bestond` op True. Geeft `(plaats, bestond)`, met `plaats` in de vorm van `zoek()`.
    """
    fouten = []

    def veld(waarde, wat):
        tekst = str(waarde if waarde is not None else "").strip()
        if any(t in tekst for t in ("\t", "\n", "\r")):
            fouten.append(f"{wat} mag geen tab of regeleinde bevatten.")
        return tekst

    def coord(waarde, wat, laag, hoog):
        tekst = str(waarde if waarde is not None else "").strip().replace(",", ".")
        try:
            getal = float(tekst)
        except ValueError:
            fouten.append(f"De {wat} is geen getal.")
            return None
        if not (laag <= getal <= hoog):
            fouten.append(f"De {wat} hoort tussen {laag} en {hoog} te liggen.")
            return None
        return getal

    naam = veld(naam, "De naam")
    if not naam:
        fouten.append("De plaats heeft geen naam.")
    elif len(naam) > 80:
        fouten.append("De naam is te lang (hoogstens 80 tekens).")
    lat = coord(lat, "breedte", -90.0, 90.0)
    lon = coord(lon, "lengte", -180.0, 180.0)
    land = veld(land, "Het land").upper()
    if land and (len(land) != 2 or not land.isalpha()):
        fouten.append("Het land is de tweeleterige code (NL, BE, DE ...).")
    zone = veld(zone, "De tijdzone")
    if zone and zone not in zoneinfo.available_timezones():
        fouten.append(f"'{zone}' is geen bekende tijdzone (IANA).")
    streek = veld(streek, "De streek")
    gemeente = veld(gemeente, "De gemeente")
    if fouten:
        raise InvoerFout(fouten)

    if not zone:
        # Een eigen plaats zonder zone: de zone komt uit de buurt, net als bij een lege zone in het
        # formulier. Beter dan een lege zone die pas bij het rekenen opvalt.
        uit = zone_voor(lat, lon, land)
        if uit:
            zone = uit["zone"]

    bestaand, _ = eigen()
    for plaats in bestaand:
        if (plaats[0].lower() == naam.lower()
                and abs(plaats[1] - lat) < 1e-6 and abs(plaats[2] - lon) < 1e-6):
            return _treffer(plaats, True), True

    regel = "\t".join([naam, f"{lat:.5f}", f"{lon:.5f}", land, zone, streek, gemeente]).rstrip("\t")
    kop = "# toegevoegd " + datetime.date.today().isoformat() + " door de schil"
    if bron:
        kop += "\n# bron: " + veld(bron, "De bron").replace("\t", " ")
    _zorg_voor_bestand()
    voorloop = ""
    if os.path.exists(EIGEN):
        with open(EIGEN, encoding="utf-8") as f:
            inhoud = f.read()
        if inhoud and not inhoud.endswith("\n"):
            voorloop = "\n"
    with open(EIGEN, "a", encoding="utf-8") as f:
        f.write(voorloop + kop + "\n" + regel + "\n")

    # De nieuwe regel staat achteraan, dus de laatste van de herlezen lijst is hem.
    na, _ = eigen()
    return _treffer(na[-1], True), False


def verwijder_eigen(naam, lat, lon):
    """Een plaats uit `data/eigen-plaatsen.tsv` halen.

    De sleutel is **naam + coordinaten**, niet een regelnummer: het bestand is met de hand te bewerken,
    dus een nummer zou na een handmatige regel verschuiven. De herkomstregels die `voeg_eigen_toe`
    boven de regel zette (`# toegevoegd ...`, `# bron: ...`) gaan mee weg; de uitleg bovenin het bestand
    blijft staan, want die begint niet met die twee woorden.

    Geeft de verwijderde regel terug, of None als die plaats er niet (meer) in staat.
    """
    naam = str(naam or "").strip()
    try:
        lat = float(str(lat).replace(",", "."))
        lon = float(str(lon).replace(",", "."))
    except (TypeError, ValueError):
        raise InvoerFout(["De breedte en de lengte horen getallen te zijn."])
    if not naam:
        raise InvoerFout(["Zonder naam is niet te zien welke plaats weg moet."])
    if not os.path.exists(EIGEN):
        return None

    with open(EIGEN, encoding="utf-8") as f:
        regels = f.read().split("\n")

    gevonden = None
    for i, regel in enumerate(regels):
        if not regel.strip() or regel.lstrip().startswith("#"):
            continue
        delen = regel.split("\t")
        if len(delen) < 3 or delen[0].strip().lower() != naam.lower():
            continue
        try:
            rlat, rlon = float(delen[1]), float(delen[2])
        except ValueError:
            continue
        if abs(rlat - lat) < 1e-6 and abs(rlon - lon) < 1e-6:
            gevonden = i
            break
    if gevonden is None:
        return None

    begin = gevonden
    while begin > 0 and regels[begin - 1].strip().startswith(("# toegevoegd", "# bron:")):
        begin -= 1
    weg = regels[gevonden]
    nieuw = regels[:begin] + regels[gevonden + 1:]
    while nieuw and not nieuw[-1].strip():
        nieuw.pop()

    tijdelijk = EIGEN + ".tmp"
    with open(tijdelijk, "w", encoding="utf-8") as f:
        f.write("\n".join(nieuw) + "\n")
    os.replace(tijdelijk, EIGEN)
    return weg


def zones():
    """Alle IANA-namen die in de lijst voorkomen, gesorteerd — voor de keuzelijst in het formulier."""
    laad()
    return sorted({p[4] for p in _lijst if p[4]})


def _afstand_km(lat1, lon1, lat2, lon2):
    """Grote-cirkelafstand in kilometers (haversine)."""
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(min(1.0, math.sqrt(h)))


def zone_van_land(land):
    """De zone die het vaakst bij een land hoort, naar inwoners gewogen; anders de vaste twee."""
    laad()
    land = (land or "").strip().upper()
    if not land:
        return ""
    gewicht = {}
    for p in _lijst:
        if p[3] == land and p[4]:
            gewicht[p[4]] = gewicht.get(p[4], 0) + max(1, p[5] or 0)
    if gewicht:
        return max(gewicht.items(), key=lambda kv: kv[1])[0]
    return ZONE_VAN_LAND.get(land, "")


def zone_voor(lat, lon, land="", straal=ZONE_ZOEK_KM):
    """De IANA-tijdzone bij coördinaten, of None als er niets in de buurt ligt.

    Drie trappen, van nauwkeurig naar grof:

    1. de dichtstbijzijnde **grote** plaats (>= `ZONE_GROTE_STAD` inwoners) in hetzelfde land, binnen
       `straal` km - dat is de zone van de eigen streek, ook in landen met meer dan één zone;
    2. anders de dichtstbijzijnde plaats van welke grootte dan ook in dat land;
    3. anders de zone die bij het land hoort (`zone_van_land`) - grof, maar beter dan niets.

    Zonder land wordt over alle landen gezocht; dat is alleen goed aan een grens die geen zonegrens is
    (NL/DE), dus de schil geeft het land mee als ze het heeft (OpenStreetMap doet dat).

    Geeft `{"zone", "plaats", "land", "km", "bron"}` met bron "grote plaats", "plaats" of "land".
    """
    laad()
    land = (land or "").strip().upper()
    beste = beste_groot = None
    for p in _lijst:
        if not p[4]:
            continue
        if land and p[3] != land:
            continue
        km = _afstand_km(lat, lon, p[1], p[2])
        if km > straal:
            continue
        if (p[5] or 0) >= ZONE_GROTE_STAD and (beste_groot is None or km < beste_groot[0]):
            beste_groot = (km, p)
        if beste is None or km < beste[0]:
            beste = (km, p)
    if beste_groot or beste:
        groot = beste_groot is not None
        km, p = beste_groot or beste
        return {"zone": p[4], "plaats": p[0], "land": p[3], "km": km,
                "bron": "grote plaats" if groot else "plaats"}
    zone = zone_van_land(land)
    if zone:
        return {"zone": zone, "plaats": "", "land": land, "km": None, "bron": "land"}
    return None


def zoek(tekst, limiet=LIMIET):
    """Plaatsen zoeken op (een begin van) de naam.

    Orde: de precieze naam eerst, dan wat ermee begint, dan wat het bevat. Binnen een groep:
    eerst de plaatsen waarvan de **eigen naam** met het getypte begint, dan pas de plaatsen die
    alleen via een andere naam gevonden zijn (zoals de Koreaanse spelling van Krasnojarsk), en
    binnen die twee de grootste plaats eerst.
    """
    vraag = _zonder_accenten(tekst or "")
    if len(vraag) < 2:
        return []
    plaatsen, namen, sleutels = laad()
    eigen_plaatsen, eigen_namen = eigen()
    uit, gezien = [], set()

    def voeg_toe(nummer, eigen_plaats):
        plaats = (eigen_plaatsen if eigen_plaats else plaatsen)[nummer]
        merk = (plaats[0].lower(), plaats[1], plaats[2])
        if merk in gezien:
            return
        gezien.add(merk)
        uit.append(_treffer(plaats, eigen_plaats))

    gekozen = []
    for nummer in eigen_namen.get(vraag, []):
        gekozen.append((nummer, True, 0, vraag))
    for nummer in namen.get(vraag, []):
        gekozen.append((nummer, False, 0, vraag))

    for bron_namen, eigen_plaats in ((eigen_namen, True), (namen, False)):
        if len(gekozen) >= limiet:
            break
        if eigen_plaats:
            kandidaten = [s for s in sorted(bron_namen) if s.startswith(vraag) and s != vraag]
        else:
            begin = bisect.bisect_left(sleutels, vraag)
            einde = bisect.bisect_left(sleutels, vraag + "\uffff")
            kandidaten = sleutels[begin:min(einde, begin + MAX_NAAMVAK)]
        for sleutel in kandidaten[:MAX_NAAMVAK]:
            for nummer in bron_namen[sleutel]:
                gekozen.append((nummer, eigen_plaats, 1, sleutel))

    if not gekozen:                           # niets dat ermee begint: ook "er in voor komt"
        for sleutel in sleutels:
            if vraag in sleutel:
                for nummer in namen[sleutel]:
                    gekozen.append((nummer, False, 2, sleutel))
            if len(gekozen) >= MAX_NAAMVAK:
                break

    def rij(g):
        plaats = (eigen_plaatsen if g[1] else plaatsen)[g[0]]
        # Bij een **volledig** getypte naam (groep 0) telt alleen de grootte: dan wint Parijs van
        # het Belgische gehucht Parijs. Zolang er nog getypt wordt (groep 1) gaan de plaatsen
        # waarvan de eigen naam ermee begint vóór de plaatsen die alleen via een andere naam
        # gevonden zijn (de Koreaanse spelling van Krasnojarsk).
        eigen_naam = 0 if g[2] == 0 or _zonder_accenten(plaats[0]) == g[3] else 1
        return (g[2],
                eigen_naam,
                0 if g[1] else 1,                                # eigen aanvulling eerst
                -(plaats[5] if len(plaats) > 5 else 0),          # grootste plaats eerst
                len(plaats[0]), plaats[0].lower())

    gekozen.sort(key=rij)
    for nummer, eigen_plaats, _, _ in gekozen:
        voeg_toe(nummer, eigen_plaats)
        if len(uit) >= limiet:
            break
    return uit


def vind(naam, land=None):
    """De beste treffer voor een plaatsnaam (voor het openen van een bewaarde kaart)."""
    treffers = zoek(naam, limiet=50)
    if land:
        for t in treffers:
            if t["land"].upper() == land.upper():
                return t
    return treffers[0] if treffers else None


def kandidaten(naam):
    """Alle plaatsen die **precies** zo heten (accenten en hoofdletters maken niet uit).

    Anders dan `zoek()`, dat ook begint-met en bevat-treffers geeft: hier gaat het om de vraag of
    een ingevulde plaatsnaam bij ingevulde coördinaten hoort (zie `kern/invoer.py`). Een
    gedeeltelijke naam mag daar geen rol spelen, want dan keurt de ene lezing de andere goed.

    De opzoeking gaat langs `_naamgenoten()`, dus ook langs de accentloze kant
    van de index: zonder dat miste "t zand" twee van de vijf en "Hünningen" één van de twee, en dan
    keurt de coördinatencontrole een juiste plaats af.
    """
    uit, gezien = [], set()
    for plaats, eigen_plaats in _naamgenoten(naam):
        merk = (plaats[0].lower(), plaats[1], plaats[2])
        if merk in gezien:
            continue
        gezien.add(merk)
        uit.append(_treffer(plaats, eigen_plaats))
    return uit
