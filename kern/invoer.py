"""Invoer van geboortegegevens: lezen en keuren, met een boodschap in gewone taal.

De schil is de voordeur van het formulier, maar het lezen en keuren hoort bij de kern: dan geldt
dezelfde controle voor de pagina, voor een bewaarde kaart en voor een proefscript, en is het te
ijken zonder de schil te starten.

Wat er aanvaard wordt - alles wat een mens intypt, niet alleen wat de pagina stuurt:

- datum: 1985-03-14, 14-03-1985, 14/03/1985, 14.3.1985 (het jaar moet voluit)
- tijd:  16:51:26, 16:51, 16.51   (seconden mogen weg)
- coordinaten: 51.6736, 51,6736, 51.6736 N, 4.2811 O, 51°40' N, -4.2811
- huizenstelsel: de letter (K) of de naam (Koch, koch)
- tijdzone: leeg = Europe/Amsterdam; een onbekende zone is een **waarschuwing**, geen stilte
- tijdcorrectie: leeg/volgens tijdzone, UT, LMT
- sectoren: eigen-graden, vast-30; leeg = laat spec.json beslissen

Alle fouten worden verzameld en in één keer gemeld, zodat een ronde niet tien keer heen en weer
gaat. Er komt geen Engelse fout en geen 500 meer naar buiten voor iets wat de invoer betreft.
"""

from __future__ import annotations

import datetime as _dt
import math
import re
import zoneinfo

from . import efemeride as _eph

STANDAARD_TIJDZONE = "Europe/Amsterdam"
STANDAARD_HUISSTELSEL = "K"
SECTOREN = ("eigen-graden", "vast-30")
# Het bereik van de Moshier-benadering is ±3000 v.C. tot 3000 n.C.; de efemeridenbestanden dekken
# 1800-2399. Binnen dat laatste rekent het programma exact, daarbuiten met Moshier en met een melding
# dubbelzinnig (geen jaar 0).
JAAR_MIN, JAAR_MAX = 1, 2999
_CORRECTIES = {"": None, "zone": None, "tijdzone": None, "volgens tijdzone": None,
               "utc": "utc", "ut": "utc", "lmt": "lmt", "plaatselijke tijd": "lmt",
               "plaatselijke tijd (lmt)": "lmt"}
_JA = ("1", "true", "ja", "aan", "j", "yes")
_NEE = ("", "0", "false", "nee", "uit", "n", "no", "none")


class InvoerFout(Exception):
    """Eén of meer regels in gewone taal over wat er aan de invoer niet klopt.

    `velden` loopt gelijk op met `meldingen` en zegt bij welke **soort** gegeven de klacht hoort
    (`datum`, `tijd`, `breedte`, `lengte`, `plaats`, `tijdcorrectie`); het scherm kan daarmee het
    foute veld aanwijzen. De namen zijn die van het gegeven, niet van het invulveld: welke id
    daarbij hoort weet alleen de pagina (formulier of instellingenscherm).
    """

    def __init__(self, meldingen, velden=None):
        self.meldingen = [str(m) for m in meldingen]
        self.velden = [str(v) for v in (velden or [])]
        super().__init__(" ".join(self.meldingen))


def _geen_locatie(vraag):
    """Waar als de plaats én beide coördinaten leeg zijn: dan is er geen locatie, geen twee fouten."""
    return not any(str(vraag.get(sleutel) or "").strip() for sleutel in ("plaats", "lat", "lon"))


def lees(vraag):
    """Vraag (dict uit het formulier) -> schone waarden, of InvoerFout.

    Sleutels: naam, jaar, maand, dag, uur, minuut, seconde, datum, tijd, tijdzone_id, plaats,
    lat, lon, huizenstelsel, tijdcorrectie, met_chiron, sectoren, waarschuwingen.
    """
    if not isinstance(vraag, dict):
        raise InvoerFout(["De vraag is geen lijst met velden."])

    fouten = []
    velden = []
    let_op = []

    def fout(meldingen, veld):
        """Fouten van één gegeven erbij, met de naam van dat gegeven erbij."""
        meldingen = list(meldingen)
        fouten.extend(meldingen)
        velden.extend([veld] * len(meldingen))

    naam = str(vraag.get("naam") or "").strip() or "zonder naam"
    plaats = str(vraag.get("plaats") or "").strip()

    jaar = maand = dag = None
    try:
        jaar, maand, dag = _datum(vraag.get("datum"))
    except InvoerFout as e:
        fout(e.meldingen, "datum")
    if jaar is not None and not (JAAR_MIN <= jaar <= JAAR_MAX):
        fout([f"De datum valt buiten het bereik van dit programma "
              f"({JAAR_MIN} tot {JAAR_MAX})."], "datum")

    uur = minuut = seconde = None
    try:
        uur, minuut, seconde = _tijd(vraag.get("tijd"))
    except InvoerFout as e:
        fout(e.meldingen, "tijd")

    lat = lon = None
    # Bestand → Nieuw ook de locatie leegmaakt, komt dat bij elke nieuwe horoscoop voor; de melding
    # noemt daarom de plaats, want dat is de handeling die de gebruiker moet doen. Staat er wél een
    # plaats of één coördinaat, dan blijft het bij de melding per veld hieronder.
    if _geen_locatie(vraag):
        fout(["Kies een plaats uit de lijst, of vul de coördinaten in."], "plaats")
    else:
        for sleutel, naam_van_veld, grens in (("lat", "breedte", 90.0), ("lon", "lengte", 180.0)):
            try:
                waarde = _coord(vraag.get(sleutel), naam_van_veld, grens)
            except InvoerFout as e:
                fout(e.meldingen, naam_van_veld)
                waarde = None
            if sleutel == "lat":
                lat = waarde
            else:
                lon = waarde

    try:
        huizenstelsel = _huisstelsel(vraag.get("huizenstelsel"))
    except InvoerFout as e:
        fout(e.meldingen, "huizenstelsel")
        huizenstelsel = None

    try:
        tijdcorrectie = _correctie(vraag.get("tijdcorrectie"))
    except InvoerFout as e:
        fout(e.meldingen, "tijdcorrectie")
        tijdcorrectie = None

    try:
        sectoren = _sectoren(vraag.get("sectoren"))
    except InvoerFout as e:
        fout(e.meldingen, "sectoren")
        sectoren = None

    tijdzone_id, waarschuwing = _tijdzone(vraag.get("tijdzone_id"), lat, lon,
                                         str(vraag.get("land") or ""))
    if waarschuwing:
        let_op.append(waarschuwing)

    met_chiron = _vlag(vraag.get("met_chiron"))

    if not fouten and plaats and lat is not None and lon is not None:
        let_op += plaats_bij_coordinaten(plaats, lat, lon)

    if fouten:
        raise InvoerFout(fouten, velden)

    return {
        "naam": naam,
        "plaats": plaats,
        "jaar": jaar, "maand": maand, "dag": dag,
        "uur": uur, "minuut": minuut, "seconde": seconde,
        "datum": f"{jaar:04d}-{maand:02d}-{dag:02d}",
        "tijd": f"{uur:02d}:{minuut:02d}:{seconde:02d}",
        "tijdzone_id": tijdzone_id,
        "lat": lat, "lon": lon,
        "huizenstelsel": huizenstelsel,
        "tijdcorrectie": tijdcorrectie,
        "met_chiron": met_chiron,
        "sectoren": sectoren,
        "waarschuwingen": let_op,
    }


def lees_plaats(vraag):
    """Alleen de plaatsgegevens: naam, etiket, breedte, lengte en zone.

    Voor de huidige locatie in de instellingen. Dezelfde lezer als het formulier
    (`_coord`, `_tijdzone`), zodat de instellingen en een kaart niet uit elkaar kunnen lopen. Een
    ontbrekende naam is een fout: de locatie is een gegeven van de gebruiker en geen standaardwaarde.
    """
    if not isinstance(vraag, dict):
        raise InvoerFout(["De instellingen zijn geen lijst met velden."])

    fouten = []
    velden = []
    let_op = []

    def fout(meldingen, veld):
        meldingen = list(meldingen)
        fouten.extend(meldingen)
        velden.extend([veld] * len(meldingen))

    naam = str(vraag.get("naam") or "").strip()
    if not naam:
        fout(["Vul een plaatsnaam in."], "plaats")
    etiket = str(vraag.get("etiket") or "").strip() or naam

    lat = lon = None
    for sleutel, naam_van_veld, grens in (("lat", "breedte", 90.0), ("lon", "lengte", 180.0)):
        try:
            waarde = _coord(vraag.get(sleutel), naam_van_veld, grens)
        except InvoerFout as e:
            fout(e.meldingen, naam_van_veld)
            waarde = None
        if sleutel == "lat":
            lat = waarde
        else:
            lon = waarde

    tijdzone_id, waarschuwing = _tijdzone(vraag.get("tijdzone_id"), lat, lon,
                                         str(vraag.get("land") or ""))
    if waarschuwing:
        let_op.append(waarschuwing)

    if not fouten and naam and lat is not None and lon is not None:
        let_op += plaats_bij_coordinaten(naam, lat, lon)

    if fouten:
        raise InvoerFout(fouten, velden)

    return {"naam": naam, "etiket": etiket, "lat": lat, "lon": lon,
            "tijdzone_id": tijdzone_id, "waarschuwingen": let_op}


AFSTAND_MAX_KM = 5.0


def _afstand_km(lat1, lon1, lat2, lon2):
    """Afstand tussen twee punten in km (vlakke benadering: op deze schaal ruim genoeg)."""
    dlat = (lat2 - lat1) * 111.0
    dlon = (lon2 - lon1) * 111.0 * math.cos(math.radians(lat1))
    return math.hypot(dlat, dlon)


def _coord_tekst(lat, lon):
    return f"{lat:.4f} / {lon:.4f}"


def _delen(plaats):
    """De delen van een samengesteld label: 'Langstraat, Ooltgensplaat' -> ['Langstraat', 'Ooltgensplaat'].

    Een gebruiker schrijft vaak méér dan de lijst weet: het gehucht met het dorp erachter, de plaats met
    de streek tussen haakjes, of de straat met de gemeente. Dat is geen onbekende plaats, het is een
    preciezer label - geaccepteerd, zij het onder protest.
    """
    return [d.strip() for d in re.split(r"[,;/|()]+", plaats) if d.strip()]


def plaats_bij_coordinaten(plaats, lat, lon):
    """Klopt de plaatsnaam bij de coördinaten? Geeft de let-op-regels terug, of werpt InvoerFout.

    Zonder deze controle rekent het programma stil door met de coördinaten van de **vorige** plaats
    terwijl de nieuwe naam in de kaart komt (gemeten: "Heerlen" boven een kaart die
    met de coördinaten van Dieren was gerekend). Drie uitkomsten zijn goed:

    - de naam staat niet in de plaatsenlijst: dan zeggen we dat en houden we de ingevulde
      coördinaten (een eigen plaats of een gehucht hoort te kunnen);
    - een plaats met precies die naam ligt binnen `AFSTAND_MAX_KM`: dan klopt het;
    - de naam is een **samengesteld label** waarvan één deel bij deze coördinaten ligt
      ("Langstraat, Ooltgensplaat"): dan zijn de coördinaten geverifieerd en zwijgen we. Zonder deze
      trap krijgt de gebruiker een let-op-regel voor een plaats die hij juist preciezer had gemaakt.

    Ligt de dichtstbijzijnde plaats met die naam (of met het dichtstbijzijnde deel) verder weg, dan is
    er geen eerlijke kaart mogelijk en weigeren we — met beide routes erbij (uit de lijst kiezen of de
    coördinaten aanpassen), zodat de gebruiker kiest en het programma niet zelf iets verzint.
    """
    from . import plaatsen

    treffers = plaatsen.kandidaten(plaats)
    if not treffers:
        naaste = None
        for deel in _delen(plaats):
            kand = plaatsen.kandidaten(deel)
            if not kand:
                continue
            dichtst = min(kand, key=lambda t: _afstand_km(lat, lon, t["lat"], t["lon"]))
            km = _afstand_km(lat, lon, dichtst["lat"], dichtst["lon"])
            if km <= AFSTAND_MAX_KM:
                return []
            if naaste is None or km < naaste[0]:
                naaste = (km, deel, dichtst)
        if naaste is None:
            return [f"De plaats '{plaats}' staat niet in de plaatsenlijst: berekend met de ingevulde "
                    f"coördinaten ({_coord_tekst(lat, lon)})."]
        km, deel, dichtst = naaste
        raise InvoerFout(
            [f"De coördinaten {_coord_tekst(lat, lon)} horen niet bij '{deel}': die plaats ligt op "
             f"{_coord_tekst(dichtst['lat'], dichtst['lon'])}, {km:.0f} km verderop. Kies de plaats uit "
             f"de lijst, of pas de coördinaten aan."],
            ["plaats"])
    dichtst = min(treffers, key=lambda t: _afstand_km(lat, lon, t["lat"], t["lon"]))
    km = _afstand_km(lat, lon, dichtst["lat"], dichtst["lon"])
    if km <= AFSTAND_MAX_KM:
        return []
    raise InvoerFout(
        [f"De coördinaten {_coord_tekst(lat, lon)} horen niet bij '{plaats}': die plaats ligt op "
         f"{_coord_tekst(dichtst['lat'], dichtst['lon'])}, {km:.0f} km verderop. Kies de plaats uit "
         f"de lijst, of pas de coördinaten aan."],
        ["plaats"])


def _datum(tekst):
    """Datum -> (jaar, maand, dag). Het jaar moet voluit; dubbelzinnigheid wordt niet geraden.

    Naast 1985-03-14 en 14-03-1985 (met - / . , of spatie) mag ook de aaneengesloten vorm:
    14031985 of 19850314. Daar zit geen scheidingsteken in om op af te gaan, dus beslist de vraag
    welke lezing een bestaande datum oplevert: 14031985 wordt 14-03-1985 (1403-19-85 bestaat niet,
    maand 19), en 19850314 wordt 1985-03-14. Leveren beide lezingen niets op, dan pas een fout —
    raden doen we niet.
    """
    t = str(tekst if tekst is not None else "").strip()
    if not t:
        raise InvoerFout(["Vul een datum in (14-03-1985 of 14031985)."])
    t = re.sub(r"[\s/.,]+", "-", t).strip("-")
    voorbeeld = "schrijf hem als 14-03-1985 of 14031985."
    if re.fullmatch(r"\d{8}", t):
        # (jaar, maand, dag) in beide lezingen: 19850314 als yyyymmdd, 14031985 als ddmmyyyy.
        for js, ms, ds in ((t[:4], t[4:6], t[6:8]), (t[4:8], t[2:4], t[:2])):
            try:
                _dt.date(int(js), int(ms), int(ds))
            except ValueError:
                continue
            return int(js), int(ms), int(ds)
        raise InvoerFout([f"De datum '{tekst}' bestaat niet: {voorbeeld}"])
    delen = [d for d in t.split("-") if d]
    if len(delen) != 3:
        raise InvoerFout([f"De datum '{tekst}' snap ik niet: {voorbeeld}"])
    if len(delen[0]) == 4:
        js, ms, ds = delen
    elif len(delen[2]) == 4:
        ds, ms, js = delen
    else:
        raise InvoerFout([f"De datum '{tekst}' heeft een afgekort jaar: schrijf het jaar voluit "
                          f"(1985 in plaats van 85)."])
    try:
        jaar, maand, dag = int(js), int(ms), int(ds)
    except ValueError:
        raise InvoerFout([f"De datum '{tekst}' snap ik niet: {voorbeeld}"])
    try:
        _dt.date(jaar, maand, dag)
    except ValueError as e:
        raise InvoerFout([f"De datum '{tekst}' bestaat niet: {_nl_datumfout(e, jaar, maand, dag)}"])
    return jaar, maand, dag


def _nl_datumfout(fout, jaar, maand, dag):
    tekst = str(fout)
    # Kijk eerst naar de dag: "day is out of range for month" bevat het woord "month" ook
    if "day is out of range" in tekst:
        return f"dag {dag} bestaat niet in maand {maand} van {jaar}."
    if "month" in tekst:
        return f"maand {maand} bestaat niet (1 tot 12)."
    return tekst


def _tijd(tekst):
    """Tijd -> (uur, minuut, seconde). Uu:mm mag, seconden hoeven niet.

    Als scheidingsteken tussen de delen mag alles wat een mens typt: `:` `.` `,` of `u`/`h`
    ("16u51"). En de aaneengesloten vorm: 1651 of 165126 — dat is niet dubbelzinnig, vier cijfers
    zijn uren en minuten, zes zijn uren, minuten en seconden.
    """
    t = str(tekst if tekst is not None else "").strip().strip(".,:; -")
    if not t:
        # Twee regels, geen muur: het tweede deel (waarom 12:00 niet hetzelfde is) staat er los onder
        # - het is een toelichting, geen eis.
        raise InvoerFout([
            "Vul een tijd in, bijvoorbeeld 09:30 of 09:30:15.",
            "Is de geboortetijd niet bekend? Vul dan 12:00 in. De huizen en de Ascendant kloppen "
            "dan niet, en de Maan kan enkele graden verschoven zijn.",
        ])
    # Alleen een scheidingsteken tússen cijfers telt: "16.51.26" en "16 uur 51" worden "16:51:26",
    # maar een punt of komma achteraan valt weg (die is hierboven al gestript).
    t = re.sub(r"(?<=\d)\s*(?:uur|u|h|\.|,|:)\s*(?=\d)", ":", t, flags=re.IGNORECASE)
    voorbeeld = "schrijf hem als 09:30, 09:30:15 of 0930."
    if re.fullmatch(r"\d{4}|\d{6}", t):
        t = ":".join(t[i:i + 2] for i in range(0, len(t), 2))
    delen = t.split(":")
    if len(delen) == 2:
        delen.append("0")
    if len(delen) != 3:
        raise InvoerFout([f"De tijd '{tekst}' snap ik niet: {voorbeeld}"])
    try:
        uur, minuut, seconde = (int(d) for d in delen)
    except ValueError:
        raise InvoerFout([f"De tijd '{tekst}' snap ik niet: {voorbeeld}"])
    if not (0 <= uur <= 23):
        raise InvoerFout([f"Het uur {uur} bestaat niet: 0 tot 23."])
    if not (0 <= minuut <= 59):
        raise InvoerFout([f"De minuten {minuut} bestaan niet: 0 tot 59."])
    if not (0 <= seconde <= 59):
        raise InvoerFout([f"De seconden {seconde} bestaan niet: 0 tot 59."])
    return uur, minuut, seconde


# Twee functies voor de schil: dezelfde lezers als hierboven, maar met de standaardvorm als
# uitkomst in plaats van losse getallen. De pagina schrijft die vorm stil terug in het veld, zodat
# het formulier dezelfde notatie toont als het gegevensblok, de horoscopenlijst en de A4.
#
# Eén standaard, overal: de datum als DD-MM-JJJJ en de tijd als UU:MM:SS - ook als er geen
# precies"). Wie 09:30 typt, bedoelt seconde 0; het programma rekent daar ook mee.
#
# Let op wat deze functies **niet** doen: een lege of onleesbare waarde is hier geen fout. Ze
# gooien wel een InvoerFout (dat is de lezer), maar de schil vangt hem en zwijgt - de keuring van
# het formulier hoort bij Berekenen, niet bij het tabben door de velden.

def keur_datum(tekst):
    """De datum in de standaardvorm: 14031985, 14.3.1985 en 1985-03-14 worden alle 14-03-1985."""
    jaar, maand, dag = _datum(tekst)
    return f"{dag:02d}-{maand:02d}-{jaar:04d}"


def keur_tijd(tekst):
    """De tijd in de standaardvorm: 9u30, 0930 en 9.30 worden alle 09:30:00."""
    uur, minuut, seconde = _tijd(tekst)
    return f"{uur:02d}:{minuut:02d}:{seconde:02d}"


def _coord(tekst, naam, grens):
    """Breedte of lengte -> getal. Komma mag, N/O/Z/W/S/E mag, graden en minuten mogen."""
    t = str(tekst if tekst is not None else "").strip().upper()
    if not t:
        raise InvoerFout([f"Vul de {naam} in (bijvoorbeeld 51.6736 of 51°40' N)."])
    voorbeeld = "schrijf hem als 51.6736, 51,6736 of 51°40' N."
    letter = ""
    m = re.match(r"^(.+?)\s*([NOSEZW])$", t)
    if m and any(teken.isdigit() for teken in m.group(1)):
        t, letter = m.group(1).strip(), m.group(2)
    hoek = re.match(r"^([+-]?\d+)\s*°\s*(\d+(?:[.,]\d+)?)?\s*'?$", t)
    if hoek:
        graden = float(hoek.group(1))
        minuten = float((hoek.group(2) or "0").replace(",", "."))
        if minuten >= 60:
            raise InvoerFout([f"De {naam} '{tekst}' heeft {minuten:g} minuten: dat moet onder 60 blijven."])
        waarde = abs(graden) + minuten / 60.0
        if graden < 0:
            waarde = -waarde
    else:
        try:
            waarde = float(t.replace(",", "."))
        except ValueError:
            raise InvoerFout([f"De {naam} '{tekst}' is geen getal: {voorbeeld}"])
    if letter in ("Z", "S", "W"):
        waarde = -abs(waarde)
    elif letter in ("N", "O", "E"):
        waarde = abs(waarde)
    if not (-grens <= waarde <= grens):
        raise InvoerFout([f"De {naam} {waarde:g} ligt buiten het mogelijke bereik "
                          f"(-{grens:g} tot {grens:g})."])
    return waarde


def _huisstelsel(tekst):
    t = str(tekst if tekst is not None else "").strip()
    if not t:
        return STANDAARD_HUISSTELSEL
    if len(t) == 1 and t.upper() in _eph.HUISSTELSELS:
        return t.upper()
    for letter, naam in _eph.HUISSTELSELS.items():
        if naam.lower() == t.lower():
            return letter
    keuze = ", ".join(_eph.HUISSTELSELS.values())
    letters = " ".join(_eph.HUISSTELSELS.keys())
    raise InvoerFout([f"Het huizenstelsel '{tekst}' ken ik niet. Kies uit: {keuze} "
                      f"(of de letters {letters})."])


def _correctie(tekst):
    if tekst is None:
        return None
    t = str(tekst).strip().lower()
    if t in _CORRECTIES:
        return _CORRECTIES[t]
    raise InvoerFout([f"De tijdcorrectie '{tekst}' ken ik niet: kies 'volgens tijdzone', "
                      f"'UT' of 'LMT'."])


def _sectoren(tekst):
    t = str(tekst if tekst is not None else "").strip()
    if not t:
        return None                      # laat spec.json beslissen
    if t in SECTOREN:
        return t
    raise InvoerFout([f"De sectormaat '{tekst}' ken ik niet: kies 'eigen-graden' of 'vast-30'."])


def _afstand_tekst(km):
    """Een afstand in gewone taal: "minder dan 1 km", "7 km"."""
    return "minder dan 1 km" if km < 1 else f"{km:.0f} km"


# De zones die in de cursus voorkomen hebben een Nederlandse naam; voor de rest nemen we het laatste
# deel van de IANA-naam. De waarde in het veld blijft de IANA-naam - alleen de melding praat gewoon
ZONE_NAAM = {
    "Europe/Amsterdam": "Amsterdam",
    "Europe/Brussels": "Brussel",
    "Europe/Paris": "Parijs",
    "Europe/Berlin": "Berlijn",
    "Europe/London": "Londen",
}


def _zone_naam(zone):
    """De zone zoals een cursist hem leest: "Amsterdam", niet "Europe/Amsterdam"."""
    if zone in ZONE_NAAM:
        return ZONE_NAAM[zone]
    return zone.split("/")[-1].replace("_", " ")


def _zone_uit_coordinaten(lat, lon, land=""):
    """(zone, omschrijving) bij coördinaten; ("", "") als er niets te vinden is.

    De cursist hoeft geen IANA-naam te kennen: de zone komt uit de plaatsenlijst,
    die zelf uit GeoNames' tijdzonekolom is gebouwd (54.158 plaatsen, 356 zones). In landen met meer
    dan één zone zoekt `plaatsen.zone_voor` eerst een grote plaats in de buurt.
    """
    if lat is None or lon is None:
        return "", ""
    from . import plaatsen

    uit = plaatsen.zone_voor(lat, lon, land)
    if not uit:
        return "", ""
    zone, bron = uit["zone"], uit["bron"]
    # Waar de zone vandaan komt - de dichtstbijzijnde grote plaats, de zone van het land - is
    # ontwikkelaarsinformatie: de gebruiker hoeft alleen te weten welke tijd er nu geldt.
    naam = _zone_naam(zone)
    if bron == "land":
        return zone, (f"De tijdzone stond leeg; ik heb de kloktijd van {naam} genomen, de zone van "
                      f"{uit['land']}. Kies de zone zelf als dat niet klopt.")
    return zone, (f"De tijdzone stond leeg; ik heb de kloktijd van {naam} genomen. "
                  f"Kies de zone zelf als dat niet klopt.")


def _tijdzone(tekst, lat=None, lon=None, land=""):
    """(tijdzone_id, waarschuwing). Een lege zone komt uit de coördinaten; onbekend is een waarschuwing."""
    t = str(tekst if tekst is not None else "").strip()
    if not t:
        zone, waarom = _zone_uit_coordinaten(lat, lon, land)
        if zone:
            return zone, waarom
        return STANDAARD_TIJDZONE, ("De tijdzone stond leeg en er is geen plaats in de buurt; ik "
                                    "heb de kloktijd van Amsterdam genomen. Kies de zone zelf als "
                                    "dat niet klopt.")
    try:
        zoneinfo.ZoneInfo(t)
    except Exception:
        return t, (f"De tijdzone '{t}' is onbekend: de ingevoerde tijd wordt dan gelezen als de "
                   f"ware plaatselijke tijd van de plaats (WPT).")
    return t, None


def _vlag(waarde):
    if isinstance(waarde, bool):
        return waarde
    t = str(waarde if waarde is not None else "").strip().lower()
    if t in _JA:
        return True
    if t in _NEE:
        return False
    raise InvoerFout([f"De optie '{waarde}' ken ik niet: gebruik ja of nee."])
