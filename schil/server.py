#!/usr/bin/env python3
"""De schil van Astrologie Studio: een klein HTTP-proces op poort 8086.

Offline en lokaal (besluit T21): geen databank, geen accounts. De schil is dom - hij leest het
techniek-register, vraagt de kern om cijfers, geeft ze aan de tekenaar en levert de kaart als JSON
plus SVG aan de pagina.

Eén uitzondering: `POST /api/osm-zoek` vraagt OpenStreetMap naar een plaats
die de eigen lijst niet kent, en alleen als de gebruiker daar zelf om klikt (`schil/osm.py`, met de
regels van Nominatim erin: één verzoek per seconde, een User-Agent met het adres uit de
instellingen, en resultaten in `staat/osm-cache.json`).

Draaien:  /usr/bin/python3 schil/server.py [poort]
Bundel:   `--controle` doet een zelfcontrole (bestanden, efemeriden, een ijkkaart) en sluit af met
          0 of 1; zonder dat start de schil en opent in een bundel zelf de browser.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Waarmee de schil zich op zijn eigen poort bekendmaakt (`/api/leeft`). Zo weet een tweede start
# dat daar geen vreemd programma zit maar hijzelf, en zet hij geen tweede schil naast de eerste.
PROGRAMMA = "astrologie-studio"

# Staat op True in de versie zonder consolevenster (`bouw-windows.bat stil`). Dan is er geen
# scherm om naar te schrijven: geen access-log, en wat een gebruiker moet zien komt als
# Windows-melding in beeld.
STIL = False

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT)

from kern import efemeride as kern_efemeride, kaart as kern_kaart, solaar as kern_solaar  # noqa: E402
from kern import aspecten as kern_aspecten, progressies as kern_progressies  # noqa: E402
from kern import transits as kern_transits  # noqa: E402
from kern import elementen, formaat as kern_formaat, heerschappen  # noqa: E402
from kern import instellingen as kern_instellingen, invoer as kern_invoer  # noqa: E402
from kern import opslag, paden, plaatsen, tijd as kern_tijd   # noqa: E402
from kern.versie import VERSIE            # noqa: E402
from schil import osm                    # noqa: E402
from schil import venster                # noqa: E402
from teken import wiel                    # noqa: E402

# In ontwikkeling is dit de projectmap; in een bundel de uitgepakte map (zie `kern/paden.py`).
STATIC = paden.bron("schil", "static")
TECHNIEKEN = paden.bron("technieken")

# De cursusjaren (besluit T48). Jaar 1 is **het fundament en staat altijd aan**; jaar 2
# en later jaar 3 zijn modules die de gebruiker in het instellingenscherm aanvinkt. De lijst staat in
# `settings.json` en wordt hier bij elke vraag gelezen, zodat aanvinken meteen werkt zonder herstart.
# Geen stille terugval: een jaar waarvoor geen modulebestand bestaat is een leesbare fout, geen gok.


def _module_pad(jaar):
    return os.path.join(TECHNIEKEN, "jaar%d.json" % jaar)


def _beschikbare_jaren():
    """Welke modulebestanden er zijn: jaar1.json, jaar2.json, enzovoort."""
    if not os.path.isdir(TECHNIEKEN):
        return []
    uit = []
    for naam in os.listdir(TECHNIEKEN):
        if naam.startswith("jaar") and naam.endswith(".json") and naam[4:-5].isdigit():
            uit.append(int(naam[4:-5]))
    return sorted(uit)


def _profiel():
    """Het profiel van de aangevinkte cursusjaren: de vereniging van hun technieken.

    Jaar 1 zit er altijd in (dat dwingt `kern/instellingen.py` af). Een jaar zonder modulebestand is
    een `InvoerFout` met een regel in gewone taal; bij het starten wordt dat een stop (zie `_start`).
    """
    jaren = kern_instellingen.modules()
    ontbreekt = [j for j in jaren if not os.path.exists(_module_pad(j))]
    if ontbreekt:
        raise kern_invoer.InvoerFout(
            ["Dit programma kent de module van cursusjaar %s niet (%s ontbreekt). Beschikbaar zijn de "
             "jaren %s." % (" en ".join(str(j) for j in ontbreekt),
                            ", ".join(os.path.basename(_module_pad(j)) for j in ontbreekt),
                            ", ".join(str(j) for j in _beschikbare_jaren()) or "geen")])
    technieken, namen = [], []
    for jaar in jaren:
        module = _lees_json(_module_pad(jaar))
        namen.append(module.get("naam") or ("cursusjaar %d" % jaar))
        for regel in module.get("technieken") or []:
            # Dezelfde techniek in twee modules: de eerste keer wint, zodat de volgorde van de lijst
            # niet van de aangevinkte jaren afhangt.
            if not any(t["id"] == regel["id"] for t in technieken):
                technieken.append(regel)
    return {"jaren": jaren, "naam": " en ".join(namen), "technieken": technieken}


def _profiel_titel():
    """Hoe het kader en de venstertitel het noemen: 'cursusjaar 1' of 'cursusjaren 1 en 2'."""
    jaren = _profiel()["jaren"]
    if len(jaren) == 1:
        return "cursusjaar %d" % jaren[0]
    return "cursusjaren %s" % " en ".join(str(j) for j in jaren)


POORT = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 8086
# Alleen op dit apparaat luisteren. Op 0.0.0.0 zouden de horoscopen van de hele les bereikbaar zijn
# voor iedereen op hetzelfde netwerk, plus een firewall-vraag bij de eerste start. Wie vanaf een
# andere machine wil kijken, zet ASTRO_HOST=0.0.0.0 in het startcommando - als bewuste keuze.
HOST = os.environ.get("ASTRO_HOST", "127.0.0.1")

# Het logbestand met storingen heeft een plafond. `_storing` schrijft er met "a" bij,
# en zonder grens groeit dat door tot het niet meer te openen is - bij een programma dat jaren meegaat
# is dat geen theorie. Boven LOG_MAX regels blijft de nieuwste helft staan, met één regel erboven die
# zegt dat er geknipt is. Dezelfde truc als in `bouw/backup-github.sh`.
LOG_MAX = 400


def _log_plafond(pad, maximum=LOG_MAX):
    """Het logbestand inkorten als het te lang is. Nooit een fout: loggen mag niets blokkeren."""
    try:
        with open(pad, encoding="utf-8") as f:
            regels = f.readlines()
        if len(regels) <= maximum:
            return False
        helft = maximum // 2
        with open(pad, "w", encoding="utf-8") as f:
            f.write("=== ingekort op %s: de oudste %d regels zijn weg ===\n"
                    % (datetime.datetime.now().isoformat(timespec="seconds"), len(regels) - helft))
            f.writelines(regels[-helft:])
        return True
    except FileNotFoundError:
        return False
    except Exception:
        return False


def _lees_json(pad):
    with open(pad, encoding="utf-8") as f:
        return json.load(f)


def _vorm():
    """De namen en tekens die het scherm nodig heeft om een keuze te kunnen tonen.

    Eén bron: `kern/formaat.py` en de lijsten uit `kern/transits.py`. Zonder dit blok zou de pagina
    een tweede tekentabel moeten hebben en dat is precies de duplicatie die uit de pas gaat lopen
    (dezelfde regel als bij `WEG_PUNT`, T42).
    """
    return {
        "lichamen": [{"naam": n, "glyf": kern_formaat.glyf_planeet(n)}
                     for n in kern_transits.LICHAMEN],
        "aspecten": [{"hoek": h, "glyf": kern_formaat.glyf_aspect(h),
                      "naam": next((a["naam"] for a in kern_aspecten.ASPECTEN if a["hoek"] == h),
                                   "%d°" % h)}
                     for h in kern_transits.ASPECTEN],
        "hoeken": [{"naam": "Ascendant", "glyf": "AC"}, {"naam": "MC", "glyf": "MC"}],
    }


def _register():
    profiel = _profiel()
    uit = []
    for regel in profiel["technieken"]:
        pad = os.path.join(TECHNIEKEN, regel["id"] + ".json")
        if os.path.exists(pad):
            t = _lees_json(pad)
            t["aan"] = regel["aan"]
            uit.append(t)
    return {"profiel": profiel, "technieken": uit, "vorm": _vorm()}


def _techniek_aan(techniek_id):
    """Staat deze techniek aan in het jaarprofiel? (de schakelaar uit besluit T2/T13)"""
    for regel in _profiel()["technieken"]:
        if regel["id"] == techniek_id:
            return bool(regel["aan"])
    return False


def _aanvullingen(kaart):
    """De aanvullingen van jaar 1 die in het jaarprofiel aanstaan, als kant-en-klare JSON."""
    uit = {}
    if _techniek_aan("element-kruis"):
        uit["element_kruis"] = elementen.verdeling(kaart)
    if _techniek_aan("heerschappen"):
        uit["heerschappen"] = {"schema": heerschappen.schema(),
                               "per_huis": heerschappen.per_huis(kaart),
                               "per_lichaam": heerschappen.per_lichaam(kaart)}
    return uit


def _invoer(vraag):
    """Eén veld uit het formulier -> de standaardvorm, of niets.

    De pagina vraagt dit als je een veld verlaat: dan komt `19.7.1963` terug als `19-07-1963` en
    `9u30` als `09:30:00`, en schrijft de pagina dat stil in het veld. Leeg of onleesbaar levert
    **geen** sleutel op - en dus ook geen markering: de keuring hoort bij Berekenen, niet bij het
    tabben door de velden. Wat hier terugkomt is altijd wat `lees()` ook zou lezen (zelfde lezer,
    geen tweede set regels in de pagina).
    """
    antwoord = {}
    for sleutel, keur in (("datum", kern_invoer.keur_datum), ("tijd", kern_invoer.keur_tijd)):
        if sleutel not in vraag:
            continue
        try:
            antwoord[sleutel] = keur(vraag.get(sleutel))
        except kern_invoer.InvoerFout:
            continue
    return antwoord


def _rekenen(vraag):
    """Vraag uit het formulier -> kaart, SVG en de aanvullingen.

    Lezen en keuren van de invoer gebeurt in `kern/invoer.py`; wat daar niet door komt is een
    InvoerFout met een boodschap in gewone taal (HTTP 400), geen 500 en geen Engelse fout.
    """
    g = kern_invoer.lees(vraag)
    k = kern_kaart.maak_kaart(
        naam=g["naam"],
        jaar=g["jaar"], maand=g["maand"], dag=g["dag"],
        uur=g["uur"], minuut=g["minuut"], seconde=g["seconde"],
        tijdzone_id=g["tijdzone_id"], lat=g["lat"], lon=g["lon"],
        plaats=g["plaats"],
        huizenstelsel=g["huizenstelsel"],
        tijdcorrectie=g["tijdcorrectie"],
        met_chiron=g["met_chiron"],
    )
    # De sectormaat van het wiel is een instelling in spec.json; de pagina mag hem per vraag
    # meekrijgen (nodig om de twee afdrukken naast elkaar te kunnen leggen, besluit T11b).
    spec = None
    if g["sectoren"]:
        spec = wiel.laad_spec()
        spec["orientatie"]["sectoren"] = g["sectoren"]
    svg, botsingen = wiel.teken(k, spec)
    return {"kaart": k, "svg": svg, "botsingen": botsingen,
            "sectoren": (spec or wiel.laad_spec())["orientatie"]["sectoren"],
            "invoer": {sleutel: g[sleutel] for sleutel in
                       ("naam", "plaats", "datum", "tijd", "tijdzone_id", "lat", "lon",
                        "huizenstelsel", "tijdcorrectie", "met_chiron")},
            # De invoer meldt wat er met de invoer aan de hand is (lege zone, plaats niet in de
            # lijst); de kaart meldt wat er met de berekening aan de hand is (Moshier-benadering).
            "waarschuwingen": g["waarschuwingen"] + list(k.get("waarschuwingen") or []),
            **_aanvullingen(k)}


def _solaar(vraag):
    """Het solaar-moment voor de horoscoop op het scherm.

    De vracht is de invoer van de kaart op het scherm plus het jaar en de plaats waar de solaar
    berekend wordt (`solaar_plaats`, `solaar_lat`, `solaar_lon`, `solaar_zone`). De **kern** rekent
    de natal Zon zelf; het scherm levert dus geen cijfer aan dat de kern niet kan controleren.

    De plaats van de solaar is niet de geboorteplaats: de terugkeer is een moment, en de horoscoop
    hoort bij de plaats waar je dan bent - op vakantie of voor iemand anders.
    """
    g = kern_invoer.lees(vraag)
    natal = kern_kaart.maak_kaart(
        naam=g["naam"], jaar=g["jaar"], maand=g["maand"], dag=g["dag"],
        uur=g["uur"], minuut=g["minuut"], seconde=g["seconde"],
        tijdzone_id=g["tijdzone_id"], lat=g["lat"], lon=g["lon"], plaats=g["plaats"],
        huizenstelsel=g["huizenstelsel"], tijdcorrectie=g["tijdcorrectie"],
        met_chiron=g["met_chiron"])
    natal_zon = kern_efemeride.lengte_van("Zon", natal["punten"])

    try:
        jaar = int(str(vraag.get("jaar") or "").strip())
    except ValueError:
        raise kern_invoer.InvoerFout(["Vul een jaartal in, bijvoorbeeld 2026."], ["jaar"])
    try:
        lat = float(str(vraag.get("solaar_lat") or "").replace(",", "."))
        lon = float(str(vraag.get("solaar_lon") or "").replace(",", "."))
    except ValueError:
        raise kern_invoer.InvoerFout(
            ["Kies een plaats voor de solaar; dan weet het programma de coördinaten."],
            ["plaats"])
    zone = str(vraag.get("solaar_zone") or "").strip()
    if not zone or not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
        raise kern_invoer.InvoerFout(
            ["De plaats van de solaar is niet compleet: kies hem uit de lijst."], ["plaats"])

    moment = kern_solaar.moment(natal_zon, jaar, g["maand"], g["dag"], zone, lon)
    moment["lat"] = lat                       # het formulier vult er zijn breedteveld mee
    waarschuwingen = []
    if kern_efemeride.benadering():
        waarschuwingen.append(
            "Deze datum valt buiten het bereik van de efemeridentabellen (1800 tot 2400); de "
            "standen zijn met de Moshier-benadering berekend.")
    return {"solaar": moment, "natal_zon": natal_zon, "jaar": jaar,
            "plaats": str(vraag.get("solaar_plaats") or "").strip(),
            "waarschuwingen": waarschuwingen}


def _nu_moment():
    """Het moment van de server: datum en tijd zoals hij ze zelf leest, plus UT.

    De pagina vult hiermee bij het openen het formulier (naam "Nu", dit moment, de locatie uit de
    instellingen) en rekent daarna gewoon. Zo blijft er één waarheid voor "nu" en hoeft de pagina
    niets over tijdzones te weten; de klok van een pc mag scheef staan zonder gevolg.
    """
    nu = datetime.datetime.now()
    return {"datum": nu.strftime("%Y-%m-%d"), "tijd": nu.strftime("%H:%M:%S"),
            "utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")}


def _datum_van_leeftijd(kaart, leeftijd):
    """De kalenderdatum (jjjj-mm-dd) die bij een leeftijd hoort — de sleutel, de andere kant op."""
    jd = kaart["meta"]["julian_day_ut"] + leeftijd * kern_progressies.JAAR
    return kern_tijd.van_epoch((jd - 2440587.5) * 86400.0).strftime("%Y-%m-%d")


def _krap_op_de_rand(svg, spec):
    """Knip de tekening op de buitenrand: het canvas draagt wit dat op papier niets doet.

    Het canvas van de bi-stand is 1092 eenheden met de buitenrand op 524 — 22 eenheden (3,75 mm op
    papier) aan elke kant die geen inkt wordt. Op het scherm maakt dat niets uit, want het vak is
    flexibel; op papier is de **breedte** de beperkende factor. Met de knip vult het wiel de volle
    186 mm en worden
    alle maten 4,2 % groter, zonder dat er iets aan de spec verandert en zonder dat er één glyph van zijn
    graad verschuift — dat is het verschil met een eigen papier-spec.
    """
    rand = float(spec["stralen"]["buitenrand"])
    canvas = float(spec["canvas"]["breedte"])
    marge = (canvas - 2.0 * rand) / 2.0
    if marge <= 0.5:
        return svg
    return re.sub(r'viewBox="0 0 [\d.]+ [\d.]+"',
                  'viewBox="%g %g %g %g"' % (marge, marge, 2.0 * rand, 2.0 * rand), svg, count=1)


def _moment_jd(moment):
    """Een UT-moment ("2026-11-04T20:40") naar een Juliaanse dag, of None als het niet deugt.

    UT en niet de plaatselijke tijd van de kaart. Een transitmoment is een berekend ogenblik, geen
    burgerklok: met UT is een uur
    stappen altijd een uur, ook in de nacht van de zomertijd, toen de plaatselijke klok 02:30 oversloeg
    of twee keer aanwees. De plaatselijke tijd van de geboorteplaats is voor dit veld een *etiket*
    (afgeleid uit `tijdzone_id` van de kaart), geen invoer.
    """
    try:
        m = datetime.datetime.strptime(str(moment).strip(), "%Y-%m-%dT%H:%M")
    except (TypeError, ValueError):
        return None
    if not 1800 <= m.year <= 2400:
        return None
    return kern_efemeride.julian_day_ut(m.year, m.month, m.day, m.hour + m.minute / 60.0)


# --- Het venster en de schil sluiten samen  -----------------------------------------
# Het venster is van de browser, de schil is het programma: zonder boekhouding stopt het ene niet als
# het andere stopt - het kruisje laat de schil draaien (±101 MB en een luisterende poort) en
# Bestand > Afsluiten laat het venster staan. Eén boekhouding dekt beide richtingen.
#
# Elke pagina meldt zich bij het laden met een eigen id (`POST /api/venster?id=…`) en meldt zich af
# met een beacon (`/api/afgesloten?id=…`) op `pagehide`. **Gemeten in Chromium (Xvfb +
# openbox, venster gesloten via WM_DELETE zoals het kruisje): `beforeunload` én `pagehide` komen
# allebei aan, en de beacon arriveert nog terwijl de pagina al weg is.** De schil stopt pas als er
# géén venster meer over is - en pas na een korte wachttijd, want bij een verversing meldt de oude
# pagina zich af en de nieuwe zich meteen weer aan; zonder die wachttijd zou elke F5 het programma
# stoppen.
VENSTERS: dict = {}
VENSTERS_SLOT = threading.Lock()
WACHT_NA_SLUITEN = 3.0          # seconden: ruimte voor een verversing van de pagina
# Hoe lang het consolevenster blijft staan nadat het programma gestopt is: lang genoeg om de laatste
# mededeling te lezen, kort genoeg om niet te hoeven wachten. Geen toets, want een afsluiting hoort
# geen taak te zijn.
NASTAREN = 5
# Alles van het verkeer op het scherm (`--log` of ASTRO_LOG=1). Zonder dat alleen wat misgaat: een
# geslaagd verzoek is geen mededeling aan de gebruiker.
ALLES_OP_HET_SCHERM = "--log" in sys.argv[1:] or os.environ.get("ASTRO_LOG") == "1"


def _is_console():
    """Zit dit programma in een echt consolevenster (en niet in een pijp of een logbestand)?"""
    for stroom in (sys.stdin, sys.stdout):
        try:
            if stroom is None or not stroom.isatty():
                return False
        except Exception:
            return False
    return True


def _venstertitel(tekst):
    """De titel van het consolevenster: in de taakbalk zie je dan welke versie draait."""
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleTitleW(tekst)
            return
        except Exception:
            pass                    # geen console (of geen Windows): dan gewoon niet
    try:
        if sys.stdout.isatty():
            sys.stdout.write("\033]0;%s\007" % tekst)
            sys.stdout.flush()
    except Exception:
        pass



# De maat van het laatst geprinte kader: het aftellen onder het sluitblok schrijft één regel opnieuw
# in plaats van het hele kader te herdrukken.
_LAATSTE_KADER = {}


def _kader(titel, regels, breedte=None, telt=False):
    """Een kader om een paar regels: ASCII, meteen geflusht.

    Waarom ASCII en geen kadertekens als `╔═╗`: het consolevenster van Windows kan in een andere
    codepage staan (de .bat-bestanden zijn er al op aangepast) en dezelfde tekst kan in `fouten.log`
    belanden. Waarom flushen geen luxe is: zodra de uitvoer naar een bestand of pijp gaat, buffert
    Python blokgewijs en zie je van een afgebroken proces niets terug.

    `breedte` is de kleinste **binnenmaat**: het start- en het sluitblok horen even breed te zijn,
    ook als het sluitblok kortere regels heeft - hier allebei 64 tekens breed.
    `telt` zegt dat de laatste regel de aftelregel is; `_tel_af()` gebruikt de maat hieronder om die
    regel later te overschrijven.
    """
    alles = ([titel] if titel else []) + list(regels)
    binnen = max(max(len(r) for r in alles) + 2, breedte or 0)
    streep = "+" + "=" * binnen + "+"
    uit = ["", streep]
    if titel:
        uit.append("| " + titel.ljust(binnen - 1) + "|")
        uit.append(streep)
    for regel in regels:
        uit.append("| " + regel.ljust(binnen - 1) + "|")
    uit.append(streep)
    print("\n".join(uit), flush=True)
    _LAATSTE_KADER.update({"binnen": binnen, "streep": streep, "telt": bool(telt)})


def _ansi_kan():
    """Kan deze console de cursor verplaatsen (ANSI)?

    Nodig voor het aftellen, want dat schrijft dezelfde regel elke seconde opnieuw. Het consolevenster
    van Windows doet dat pas als het proces `ENABLE_VIRTUAL_TERMINAL_PROCESSING` aanzet, en dat zet
    Python niet zelf. Lukt het niet, dan blijft de regel staan en wordt er alleen gewacht — liegen
    doet het programma dan niet.
    """
    if not _is_console():
        return False
    if os.name != "nt":
        return True                 # Linux en macOS: ANSI is de standaard
    try:
        import ctypes
        kernel = ctypes.windll.kernel32
        greep = kernel.GetStdHandle(-11)                 # STD_OUTPUT_HANDLE
        stand = ctypes.c_uint32()
        if not kernel.GetConsoleMode(greep, ctypes.byref(stand)):
            return False
        if stand.value & 0x0004:                         # stond al aan
            return True
        return bool(kernel.SetConsoleMode(greep, stand.value | 0x0004))
    except Exception:
        return False


def _teller_regel(seconde):
    """De onderste regel van het sluitblok: "1 seconde", "0 seconden"."""
    return "Dit venster sluit vanzelf over %d seconde%s." % (seconde, "" if seconde == 1 else "n")


def _kan_aftellen(binnen):
    """Komt het aftellen ook echt in beeld?

    Drie voorwaarden: een echt consolevenster, een cursor die vooruit kan (ANSI), en een venster dat
    breder is dan het kader — anders wikkelt een regel en zet de sprong van twee regels de tekst op
    de verkeerde plek.
    """
    if not _ansi_kan():
        return False
    try:
        return shutil.get_terminal_size().columns > binnen + 2
    except Exception:
        return False


def _tel_af(seconden):
    """Tel af in de onderste regel van het laatste kader: "over 4 ... 0 seconden".

    Twee regels omhoog (de aftelregel en de streep eronder), de nieuwe tekst, en de streep weer
    neerzetten — het kader blijft staan en alleen die regel verandert.
    Zonder console of zonder ANSI wordt er niets geschreven en alleen gewacht.
    """
    kader = dict(_LAATSTE_KADER)
    if not kader.get("telt") or not _kan_aftellen(kader["binnen"]):
        time.sleep(seconden)
        return
    for seconde in range(int(seconden) - 1, -1, -1):
        try:
            time.sleep(1.0)
        except (KeyboardInterrupt, OSError):
            return
        sys.stdout.write("\033[2A\r| " + _teller_regel(seconde).ljust(kader["binnen"] - 1)
                         + "|\n" + kader["streep"] + "\n")
        sys.stdout.flush()


def _venster_meld(tid):
    """Een venster doet mee. Geeft het aantal open vensters terug."""
    with VENSTERS_SLOT:
        if tid:
            VENSTERS[tid] = time.monotonic()
        return len(VENSTERS)


def _venster_weg(tid, server):
    """Een venster is weg. Was het de laatste, dan gaat de aftelling lopen."""
    with VENSTERS_SLOT:
        VENSTERS.pop(tid, None)
        open_ = len(VENSTERS)
    if open_ == 0:
        threading.Thread(target=_stop_na_aftellen, args=(server, WACHT_NA_SLUITEN, True),
                         daemon=True).start()
    return open_


# --- stoppen: één boekhouding  ----------------------------------------------------
# Twee routes kunnen het programma laten stoppen: Bestand > Afsluiten (`/api/afsluiten`) en het
# laatste venster dat zich afmeldt (het kruisje). Zonder slot lopen ze allebei het héle ritueel af:
# "AFSLUITEN" en "GESTOPT" staan er dan twee keer, met twee tellers die over elkaar heen schrijven.
# Daarom is er één slot: de eerste aanvraag telt en print, elke volgende zwijgt.
STOP_SLOT = threading.Lock()
STOP_BEZIG = False              # er loopt al een aftelling
STOP_KLAAR = False              # het ritueel is klaar: nooit meer opnieuw beginnen
STOP_NU = threading.Event()     # de gebruiker vroeg intussen om af te sluiten: meteen stoppen


def _stop_na_aftellen(server, seconden, kan_terug):
    """Tel af en stop de schil - één keer, hoe vaak er ook om gevraagd wordt.

    `kan_terug` hoort bij het kruisje: komt er binnen de wachttijd weer een venster (een verversing),
    dan gaat het programma door en zegt dat ook. Bij Bestand > Afsluiten heeft de gebruiker het
    gevraagd en telt hij gewoon af.

    Komt Afsluiten binnen terwijl het kruisje al aftelt, dan is dat een opdracht en geen tweede
    aftelling: `STOP_NU` laat de lopende teller meteen ophouden.
    """
    global STOP_BEZIG, STOP_KLAAR
    with STOP_SLOT:
        if STOP_KLAAR:
            return
        if STOP_BEZIG:
            if not kan_terug:
                STOP_NU.set()
            return
        STOP_BEZIG = True
    gestopt = False
    try:
        gestopt = _stop_ritueel(server, seconden, kan_terug)
    finally:
        with STOP_SLOT:
            STOP_BEZIG = False
            if gestopt:
                STOP_KLAAR = True


def _stop_ritueel(server, seconden, kan_terug):
    """Het eigenlijke stoppen. Geeft terug of de schil ook echt gestopt is.

    **Beide routes printen hetzelfde blok** (T36): één afsluiting hoort één tekst te zijn, en de drie
    seconden zijn een **technische marge** (een verversing meldt de oude pagina af en
    de nieuwe meteen aan; zonder die marge zou elke F5 het programma stoppen). Die marge is stil.

    Het sluitblok zegt **waar de horoscopen staan** - dat is na afloop het enige wat een gebruiker wil
    terugvinden, en het scheelt een herhaling in het startblok - en het zegt dat het venster vanzelf
    sluit. Die laatste regel wordt door `_tel_af()`
    elke seconde bijgewerkt zodra dit blok geprint is.
    """
    if STIL:
        einde = time.monotonic() + seconden
        while time.monotonic() < einde and not STOP_NU.wait(0.1):
            pass
        with VENSTERS_SLOT:
            if VENSTERS and kan_terug:
                return False
        server.shutdown()
        return True
    rest = float(seconden)
    while rest > 0 and not STOP_NU.is_set():
        time.sleep(min(1.0, rest))
        rest -= 1.0
        if kan_terug:
            with VENSTERS_SLOT:
                terug = bool(VENSTERS)
            if terug:
                return False
    regels = ["Je horoscopen zijn opgeslagen op je computer.",
              "",
              "Locatie:",
              paden.standaardmap()]
    telt = _kan_aftellen(64)
    if telt:
        regels += ["", _teller_regel(int(NASTAREN))]
    _kader("Astrologie Studio is afgesloten", regels, breedte=64, telt=telt)
    server.shutdown()
    return True


# De lijst is om te lezen, niet om te dumpen: een lijst van 2000 regels is onbruikbaar.
# Eén regel voor álle lichamen: hoogstens dit aantal regels
# in de lijst, en de kop zegt hoeveel regels er zijn en waar de lijst stopt. Geen tijdplafond per
# planeet — het aantal regels hangt aan de selectie (doelen × aspecten), niet aan het lichaam: de Maan
# over een jaar met alles is 1.920 regels, met alleen Asc en MC 320.
#
# **500**. Het argument is papier: op een A4 in de opmaak van dit programma gaan 39 tot 47 regels
# (gemeten: 5,0 mm per regel strak, 6,1 mm in de schermstijl, 273 mm bruikbaar min kop en voet).
# 500 regels is dus ±11 vel; duizend zou ±22 vel zijn - geen lijst meer maar een brochure. In gewoon gebruik bijt de grens bijna nooit (een jaar met de vijf trage lichamen is 45
# regels, een maand Maan 160); wat hij tegenhoudt is "alles, over jaren" (23.320 regels).
GRENS_LIJST = 500


class Handler(BaseHTTPRequestHandler):
    server_version = "AstrologieStudio/%s" % VERSIE

    def log_message(self, fmt, *args):
        # Geen access-log in de stille versie: daar is geen console om het in te tonen, en de
        # cursist hoort geen log te zien. Fouten gaan via `_storing` naar fouten.log.
        if STIL:
            return
        # Alleen wat misgaat komt op het scherm. Een geslaagd verzoek is geen
        # mededeling aan de gebruiker, en met een stuk of zeven regels per paginalading verdween
        # elk kader tussen de ruis. `--log` (of ASTRO_LOG=1) zet alles weer aan.
        if not ALLES_OP_HET_SCHERM:
            try:
                if int(args[1]) < 400:
                    return
            except (IndexError, ValueError):
                pass
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _stuur(self, code, body, soort="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", soort)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _storing(self, e, vraag=None, wat="het verzoek"):
        """Een onverwachte fout: gewone taal op het scherm, de details naar `fouten.log`.

        In de bundel is er geen terminal om op terug te kijken - het venster sluit en de fout is
        weg. Zonder dit bestand is een melding als "[Errno 22] Invalid argument" niet na te lopen:
        er staat niet bij welke regel het misging. De traceback gaat daarom naar de map met de
        horoscopen, met de vraag erbij, zodat de melding van een gebruiker te reproduceren is.
        """
        spoor = traceback.format_exc()
        traceback.print_exc()
        try:
            _log_plafond(paden.staat("fouten.log"))
            with open(paden.staat("fouten.log"), "a", encoding="utf-8") as f:
                f.write("\n=== %s  %s\n" % (datetime.datetime.now().isoformat(timespec="seconds"),
                                            self.path))
                if vraag is not None:
                    f.write("vraag: %s\n" % json.dumps(vraag, ensure_ascii=False,
                                                        default=str)[:2000])
                f.write(spoor)
        except Exception:
            pass            # een mislukt logbestand mag de melding niet verbergen
        return self._stuur(500, {
            "fout": "Er ging iets mis bij %s: %s. De technische details staan in fouten.log, "
                    "in de submap staat van je horoscopenmap." % (wat, e),
            "spoor": spoor[-800:]})

    # --- de transits: een stroom met voortgang  --------------------------------
    def _stroom_begin(self, soort="application/x-ndjson; charset=utf-8"):
        """Begin een antwoord dat in stukken komt: geen Content-Length, dus de verbinding bepaalt
        het einde (HTTP/1.0). De browser leest de regels terwijl ze komen, en dat is precies wat een
        voortgangsbalk nodig heeft."""
        self.send_response(200)
        self.send_header("Content-Type", soort)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")
        # Zonder deze regel houdt de verbinding zich aan keep-alive en ziet de browser het einde van
        # de stroom nooit: de laatste regel blijft dan in de buffer staan en de balk blijft op 100%
        # hangen (gemeten bij 9.621 regels). De stroom eindigt bij het sluiten van de
        # verbinding, dus die moet dicht.
        self.send_header("Connection", "close")
        self.close_connection = True
        self.end_headers()

    def _stroom_regel(self, obj):
        self.wfile.write((json.dumps(obj, ensure_ascii=False, default=str) + "\n").encode("utf-8"))
        self.wfile.flush()

    def _transits_nu(self, vraag):
        """De standen van dit moment, met hun radixhuis.

        Dit is de enige techniek-vraag die geen tijdvak heeft: het antwoord is het hier en nu tegen
        de geladen horoscoop. De huizen komen uit de kaart, de standen uit de efemeride van het
        moment van de **server** (dezelfde regel als bij /api/nu: één waarheid voor "nu").
        """
        kaart = vraag.get("kaart")
        if not isinstance(kaart, dict) or not kaart.get("punten") or not kaart.get("huizen"):
            return self._stuur(400, {"fout": "Bereken eerst een horoscoop."})

        # De datumstapper bij het bi-wheel. Alleen de **buitenring** rekent mee; de
        # radix staat er al en verandert niet. Dit antwoord bevat daarom geen standentabel en geen
        # `volgend`: de pagina vraagt dit bij elke toetsaanslag, en 0,16 s zoeken naar het volgende
        # aspect zou het stappen laten haperen.
        moment = vraag.get("moment")
        if moment is not None:
            jd_beeld = _moment_jd(moment)
            if jd_beeld is None:
                return self._stuur(400, {"fout": "Het moment moet een UT-datum en -tijd tussen 1800 "
                                                "en 2400 zijn, als jjjj-mm-dd uu:mm."})
            spec = wiel.laad_spec(biwiel=True)
            try:
                ring = kern_transits.standen(jd_beeld, kaart)
                svg, _botsingen = wiel.teken(kaart, spec, transits=ring)
            except (ValueError, KeyError) as e:
                return self._stuur(400, {"fout": "De standen op dat moment konden niet berekend "
                                                "worden: %s" % e})
            if vraag.get("krap"):
                svg = _krap_op_de_rand(svg, spec)
            antwoord = {"moment": moment, "svg": svg}
            # De afdruk van de bi-stand heeft ook de standen nodig (planeet, graad, huis); de
            # datumstapper bij het wiel niet, en die vraagt dit bij elke toetsaanslag.
            if vraag.get("met_standen"):
                antwoord["standen"] = ring
            return self._stuur(200, antwoord)

        jd_nu = kern_efemeride.julian_day_van_timestamp(time.time())
        try:
            standen = kern_transits.standen(jd_nu, kaart)
        except (ValueError, KeyError) as e:
            return self._stuur(400, {"fout": "De standen konden niet berekend worden: %s" % e})
        # Het bi-wheel: dezelfde tekening als het Wiel-tabblad, met de standen van dit moment in de
        # band die vrijkwam: de huidige transits geven de data voor de buitenste standen van het
        # bi-wheel. De pagina zet hem in de stand "Huidige transits"; de tik van
        # twintig seconden tekent hem opnieuw, net als de Nu-kaart in het hoofdscherm.
        #
        # **Geen hoeken in de band**. De planeten zijn
        # geocentrisch, de Ascendant en MC van een moment zijn plaatsgebonden; in één band zou dat twee
        # soorten dingen op één hoop gooien. Ze leven in de Nu-kaart, waar ze het kader zijn.
        svg = ""
        try:
            svg, _botsingen = wiel.teken(kaart, wiel.laad_spec(biwiel=True), transits=list(standen))
        except (ValueError, KeyError):
            # Een wiel dat niet lukt mag de standenlijst niet tegenhouden.
            svg = ""
        # Het eerstvolgende aspect per lichaam. Zeven hoeken, dezelfde als de lijst, en vijf
        # jaar vooruit - gemeten 0,16 s voor alle tien, dus geen voortgangsbalk. Een lichaam zonder
        # exact aspect binnen die horizon houdt `null` en dat is op het scherm een streepje.
        try:
            volgend = kern_transits.volgende(kaart, jd_nu)
        except (ValueError, KeyError):
            volgend = {}
        return self._stuur(200, {"nu": _nu_moment(), "standen": standen, "svg": svg,
                                 "volgend": volgend,
                                 "volgend_horizon_jaren": round(kern_transits.VOLGEND_HORIZON / 365.25)})

    def _transits(self, vraag):
        """De transits van een radix: de standen van nu en de momenten van exactheid in een tijdvak.

        Het antwoord komt als **stroom** (NDJSON): eerst een regel per voortgangsstap, dan één regel
        met het resultaat. Een balk die uit een klok komt liegt; deze telt de lichamen die klaar zijn
        en het deel van het venster dat binnen een lichaam gedaan is - een eerlijke stand voor
        berekeningen die lang duren.
        """
        kaart = vraag.get("kaart")
        if not isinstance(kaart, dict) or not kaart.get("punten") or not kaart.get("huizen"):
            return self._stuur(400, {"fout": "Bereken eerst een horoscoop."})

        def _jd(tekst, welk):
            try:
                standaard = kern_invoer.keur_datum(tekst)
            except kern_invoer.InvoerFout:
                raise kern_invoer.InvoerFout(["De datum bij %s is niet te lezen (DD-MM-JJJJ)." % welk])
            dag, maand, jaar = (int(d) for d in standaard.split("-"))
            return kern_efemeride.julian_day_ut(jaar, maand, dag, 0.0)

        van = _jd(vraag.get("van"), "Van")
        tot = _jd(vraag.get("tot"), "Tot")
        if tot <= van:
            raise kern_invoer.InvoerFout(["Het einde van de periode moet na het begin liggen."])

        lichamen = vraag.get("lichamen") or list(kern_transits.TRAGE)
        if not isinstance(lichamen, list):
            raise kern_invoer.InvoerFout(["De lichamen horen als lijst te komen."])
        aspecten = tuple(vraag.get("aspecten") or ())
        doelen = vraag["doelen"] if "doelen" in vraag else None
        if doelen is not None and not isinstance(doelen, list):
            raise kern_invoer.InvoerFout(["De radixdoelen horen als lijst te komen."])

        # De momentopname is van nu en kost elf aanroepen; die gaat mee in de laatste regel.
        jd_nu = kern_efemeride.julian_day_van_timestamp(time.time())
        standen = kern_transits.standen(jd_nu, kaart)
        nu = _nu_moment()

        self._stroom_begin()
        laatst = {"procent": -1}

        def voortgang(m):
            procent = int(100.0 * (m["index"] + m["fractie"]) / max(1, m["totaal"]))
            if procent == laatst["procent"]:
                return
            laatst["procent"] = procent
            self._stroom_regel({"voortgang": {"procent": procent, "lichaam": m["lichaam"],
                                              "regels": m["doorgangen"]}})

        try:
            uit = kern_transits.doorgangen(
                kaart, van, tot, lichamen=tuple(lichamen), aspecten=aspecten, doelnamen=doelen,
                huis_ingress=bool(vraag.get("huis_ingress")), stations=bool(vraag.get("stations")),
                voortgang=voortgang)
        except ValueError as e:
            self._stroom_regel({"fout": str(e)})
            return
        # Buiten 1800-2399 vallen de efemeridebestanden weg en rekent swisseph met de Moshier-
        # benadering. Dat is geen grens van dit programma maar wel iets dat de gebruiker hoort te
        # weten (dezelfde regel als bij een kaart buiten dat bereik).
        let_op = None
        if van < kern_efemeride.julian_day_ut(1800, 1, 1, 0.0) or \
                tot > kern_efemeride.julian_day_ut(2400, 1, 1, 0.0):
            let_op = ("Een deel van dit tijdvak valt buiten 1800-2400: die momenten zijn met de "
                      "Moshier-benadering berekend en kunnen enkele boogseconden afwijken.")

        # De grens op de lijst, en de telling per lichaam over de **hele** lijst (niet over het
        # zichtbare deel: anders zou de wenk bij een afgekapte lijst het verkeerde lichaam noemen).
        alle = uit["doorgangen"]
        per_lichaam = {}
        for regel in alle:
            per_lichaam[regel["lichaam"]] = per_lichaam.get(regel["lichaam"], 0) + 1
        zicht = alle[:GRENS_LIJST]
        # De momentopname gaat mee in de laatste regel, en het eerstvolgende aspect hoort bij die
        # momentopname: dezelfde tabel staat in deze stand ook. Zonder dit vel zou
        # de kolom na een berekening weer leeg zijn.
        try:
            volgend = kern_transits.volgende(kaart, jd_nu)
        except (ValueError, KeyError):
            volgend = {}
        self._stroom_regel({"klaar": True, "van_jd": van, "tot_jd": tot,
                            "nu": nu, "standen": standen, "doorgangen": zicht,
                            "volgend": volgend,
                            "volgend_horizon_jaren": round(kern_transits.VOLGEND_HORIZON / 365.25),
                            "totaal": len(alle), "grens": GRENS_LIJST,
                            "afgekapt": len(alle) > len(zicht),
                            "per_lichaam": per_lichaam, "let_op": let_op})

    def _progressies_nu(self, vraag):
        """De progressieve standen bij de leeftijd van vandaag.

        De tegenhanger van `_transits_nu`, met één verschil dat de hele techniek samenvat: de tijd is
        hier geen moment maar een **leeftijd**. De leeftijd komt uit de kaart en de klok van de server
        (dezelfde regel als overal: één waarheid voor "nu"), en daar hangt alles aan — de standen, de
        drift van Ascendant en MC, en de datum die erbij hoort.

        De Ascendant en MC gaan **niet** in de ring van het bi-wheel: dat zijn drifts en geen standen, en
        in één band met de planeten zou dat twee soorten dingen op één hoop gooien (dezelfde regel als
        bij de transits). Ze staan wél in de tabel.
        """
        kaart = vraag.get("kaart")
        if not isinstance(kaart, dict) or not kaart.get("punten") or not kaart.get("huizen"):
            return self._stuur(400, {"fout": "Bereken eerst een horoscoop."})

        # De leeftijd komt uit het verzoek als het wiel op een leeftijd is gezet (de twee veldjes van de
        # progressiestand), anders uit de klok - dezelfde regel als overal: één waarheid voor "nu".
        # Zonder `leeftijd` is dit dus de kaart van vandaag; met `leeftijd` is het de kaart van die
        # leeftijd, en dat is precies de knop die het wiel nodig heeft.
        gevraagd = vraag.get("leeftijd")
        try:
            if gevraagd is None or gevraagd == "":
                leeftijd = kern_progressies.leeftijd_op(kaart)
            else:
                leeftijd = float(gevraagd)
            if not -50.0 < leeftijd < 200.0:
                raise ValueError("de leeftijd %g valt buiten de efemeride" % leeftijd)
            standen = kern_progressies.standen(kaart, leeftijd)
        except (TypeError, ValueError, KeyError) as e:
            return self._stuur(400, {"fout": "De progressieve standen konden niet berekend worden: %s" % e})

        ring = [s for s in standen if s["naam"] not in kern_progressies.HOEKEN]
        svg = ""
        spec = wiel.laad_spec(biwiel=True)
        try:
            svg, _botsingen = wiel.teken(kaart, spec, transits=ring)
        except (ValueError, KeyError):
            svg = ""            # een wiel dat niet lukt mag de tabel niet tegenhouden
        # De A4-afdruk vraagt `krap`: dan gaat het wit van het canvas eraf en vult het wiel
        # de breedte van het papier. Precies dezelfde stap als bij de transits, zodat de twee bladen
        # hetzelfde staan - het is dezelfde tekening, alleen zonder de rand die geen inkt wordt.
        if svg and vraag.get("krap"):
            svg = _krap_op_de_rand(svg, spec)
        return self._stuur(200, {"leeftijd": leeftijd, "datum": _datum_van_leeftijd(kaart, leeftijd),
                                 "standen": standen, "svg": svg})

    def _maanfasen(self, vraag):
        """De acht progressieve maanfasen vanaf de nieuwe maan vóór de geboorte tot nu.

        De leeftijd van vandaag is de grens: de lijst loopt tot en met de eerste fase daarna.
        """
        kaart = vraag.get("kaart")
        if not isinstance(kaart, dict) or not kaart.get("punten") or not kaart.get("huizen"):
            return self._stuur(400, {"fout": "Bereken eerst een horoscoop."})
        now = datetime.datetime.now(datetime.timezone.utc)
        jd_nu = kern_efemeride.julian_day_ut(now.year, now.month, now.day,
                                             now.hour + now.minute / 60.0)
        leeftijd_nu = kern_progressies.leeftijd_op(kaart, jd_nu)
        aantal = vraag.get("fasen", 8)
        try:
            aantal = int(aantal)
        except (TypeError, ValueError):
            aantal = 8
        return self._stuur(200, kern_progressies.maanfasen(kaart, tot_leeftijd=leeftijd_nu,
                                                           aantal=aantal))

    def _progressies(self, vraag):
        """De progressies van een radix: de momenten van exactheid tussen twee kalenderdatums.

        De invoer is een **tijdvak in datums**, net als bij de transits — dat is wat een gebruiker
        intypt. De kern rekent in leeftijden, dus hier gebeurt de omzetting: dezelfde sleutel, de andere
        kant op (`leeftijd_op`). Elke regel in de lijst draagt daarna allebei: de leeftijd waarop het
        exact is en de datum die daarbij hoort.

        Het antwoord komt als stroom, om dezelfde reden als bij de transits: een berekening over een
        leven hoort te laten zien dat hij bezig is, ook al is hij met 0,7 s meestal snel klaar.
        """
        kaart = vraag.get("kaart")
        if not isinstance(kaart, dict) or not kaart.get("punten") or not kaart.get("huizen"):
            return self._stuur(400, {"fout": "Bereken eerst een horoscoop."})

        def _jd(tekst, welk):
            try:
                standaard = kern_invoer.keur_datum(tekst)
            except kern_invoer.InvoerFout:
                raise kern_invoer.InvoerFout(["De datum bij %s is niet te lezen (DD-MM-JJJJ)." % welk])
            dag, maand, jaar = (int(d) for d in standaard.split("-"))
            return kern_efemeride.julian_day_ut(jaar, maand, dag, 0.0)

        van = kern_progressies.leeftijd_op(kaart, _jd(vraag.get("van"), "Van"))
        tot = kern_progressies.leeftijd_op(kaart, _jd(vraag.get("tot"), "Tot"))
        if tot <= van:
            raise kern_invoer.InvoerFout(["Het einde van de periode moet na het begin liggen."])

        lichamen = vraag.get("lichamen") or (list(kern_progressies.LICHAMEN) + list(kern_progressies.HOEKEN))
        if not isinstance(lichamen, list):
            raise kern_invoer.InvoerFout(["De lichamen horen als lijst te komen."])
        aspecten = tuple(vraag.get("aspecten") or ())
        doelen = vraag["doelen"] if "doelen" in vraag else None
        if doelen is not None and not isinstance(doelen, list):
            raise kern_invoer.InvoerFout(["De radixdoelen horen als lijst te komen."])

        self._stroom_begin()
        laatst = {"procent": -1}

        def voortgang(m):
            procent = int(100.0 * (m["index"] + m["fractie"]) / max(1, m["totaal"]))
            if procent == laatst["procent"]:
                return
            laatst["procent"] = procent
            self._stroom_regel({"voortgang": {"procent": procent, "lichaam": m["lichaam"],
                                              "regels": m["doorgangen"]}})

        try:
            uit = kern_progressies.doorgangen(
                kaart, van, tot, lichamen=tuple(lichamen), aspecten=aspecten, doelnamen=doelen,
                huis_ingress=bool(vraag.get("huis_ingress")),
                teken_ingress=bool(vraag.get("teken_ingress")),
                stations=bool(vraag.get("stations")), voortgang=voortgang)
        except ValueError as e:
            self._stroom_regel({"fout": str(e)})
            return

        # De efemeridegrens geldt voor het **progressieve** moment, niet voor de kalenderdatums: bij
        # honderd jaar leven schuift de efemeride maar honderd dagen op.
        let_op = None
        jd_prog_van = kaart["meta"]["julian_day_ut"] + van
        jd_prog_tot = kaart["meta"]["julian_day_ut"] + tot
        if jd_prog_van < kern_efemeride.julian_day_ut(1800, 1, 1, 0.0) or \
                jd_prog_tot > kern_efemeride.julian_day_ut(2400, 1, 1, 0.0):
            let_op = ("Een deel van deze progressie valt buiten 1800-2400: die momenten zijn met de "
                      "Moshier-benadering berekend en kunnen enkele boogseconden afwijken.")

        alle = uit["doorgangen"]
        per_lichaam = {}
        for regel in alle:
            per_lichaam[regel["lichaam"]] = per_lichaam.get(regel["lichaam"], 0) + 1
        zicht = alle[:GRENS_LIJST]
        leeftijd_nu = kern_progressies.leeftijd_op(kaart)
        self._stroom_regel({"klaar": True, "van_leeftijd": van, "tot_leeftijd": tot,
                            "leeftijd_nu": leeftijd_nu,
                            "van_datum": _datum_van_leeftijd(kaart, van),
                            "tot_datum": _datum_van_leeftijd(kaart, tot),
                            "doorgangen": zicht, "totaal": len(alle), "grens": GRENS_LIJST,
                            "afgekapt": len(alle) > len(zicht),
                            "per_lichaam": per_lichaam, "let_op": let_op})

    def _van_eigen_pagina(self):
        """Alleen de eigen pagina mag de schil iets laten doen - of laten stoppen.

        Een willekeurige website kan een POST sturen zonder het antwoord te lezen, dus dit is niet
        alleen netheid: zonder deze regel kan elke pagina die openstaat het programma afsluiten.

        De herkomst wordt vergeleken met de **Host waarop dit verzoek binnenkwam**, niet met een
        vaste lijst van 127.0.0.1 en localhost. Staat de schil op het netwerk (`ASTRO_HOST=0.0.0.0`),
        dan stuurt de eigen pagina het eigen adres als `Origin` mee, en dat
        viel buiten de vaste lijst: de meldingen van het venster kregen 403 en de vensterstaat werd
        stil niet bewaard. Een andere site stuurt zijn eigen herkomst mee en valt nog steeds af; de
        vaste lijst blijft staan voor het geval er iets tussen de browser en de schil zit dat de Host
        herschrijft.
        """
        herkomst = (self.headers.get("Origin") or "").rstrip("/")
        if not herkomst:
            return True
        poort = int(getattr(self.server, "server_port", 0))
        if herkomst in ("http://127.0.0.1:%d" % poort, "http://localhost:%d" % poort):
            return True
        eigen = (self.headers.get("Host") or "").strip()
        return bool(eigen) and herkomst == "http://" + eigen

    def do_GET(self):
        pad = self.path.split("?")[0]
        try:
            if pad in ("/", "/index.html"):
                with open(os.path.join(STATIC, "index.html"), encoding="utf-8") as f:
                    return self._stuur(200, f.read(), "text/html; charset=utf-8")
            if pad == "/api/technieken":
                return self._stuur(200, _register())
            if pad == "/api/leeft":
                # Waarmee het programma zich op zijn eigen poort bekendmaakt: een tweede start
                # (dubbelklik, en in de stille versie zie je daar niets van) kan zo zien dat er al
                # een schil draait en hoeft er geen tweede naast te zetten.
                return self._stuur(200, {"programma": PROGRAMMA, "versie": VERSIE,
                                         "pid": os.getpid(),
                                         "horoscopen": paden.standaardmap(),
                                         "vensters": len(VENSTERS)})
            if pad == "/api/nu":
                # Alleen de tijd van de server. De klokstand van de pagina vraagt
                # elke 20 seconden hoe laat het is en rekent de horoscoop van nu opnieuw. Dit staat
                # hier en niet bij /api/instellingen: dat antwoord vult ook het venster
                # Instellingen, en een tik van de klok hoort daarin niets te veranderen.
                return self._stuur(200, {"nu": _nu_moment()})
            if pad == "/api/kaarten":
                return self._stuur(200, opslag.lijst())
            if pad == "/api/instellingen":
                # De huidige locatie; `instellingen` is None als er nog niets is ingesteld (dan
                # vraagt de pagina erom). `nu` is het moment van de **server** - één waarheid, en
                # het blijft kloppen als de klok van een pc scheef staat. De pagina vult daarmee bij
                # het openen het formulier: naam "Nu", dat moment en de locatie, en rekent gewoon.
                # Zo is de kaart van nu geen eigen scherm of eigen endpoint maar de gewone weg.
                bestand = kern_instellingen.bestandspad()
                try:
                    inhoud = kern_instellingen.lees()
                except kern_invoer.InvoerFout as e:
                    return self._stuur(400, {"fout": " ".join(e.meldingen),
                                             "fouten": e.meldingen, "velden": e.velden,
                                             "bestand": bestand})
                return self._stuur(200, {"instellingen": inhoud, "bestand": bestand,
                                         "nu": _nu_moment()})
            if pad == "/api/plaatsen":
                vraag = urllib.parse.parse_qs(self.path.partition("?")[2])
                zoek = (vraag.get("zoek") or [""])[0]
                try:
                    limiet = int((vraag.get("limiet") or [plaatsen.LIMIET])[0])
                except ValueError:
                    limiet = plaatsen.LIMIET
                # `zones` gaat mee voor de keuzelijst van het tijdzoneveld: de
                # cursist hoeft geen IANA-naam te kennen, hij kiest er een of het script vult hem.
                return self._stuur(200, {"zoek": zoek, "plaatsen": plaatsen.zoek(zoek, limiet),
                                         "bron": plaatsen.bron(), "zones": plaatsen.zones()})
            if pad == "/favicon.ico":
                # Het pictogram van het venster. De pagina verwijst ernaar met een
                # `<link rel="icon">`, maar een browser (of een andere bezoeker van deze poort) kan om
                # /favicon.ico vragen; zonder deze route staat daar een 404 in de console, precies de
                # eerste regel na het startblok.
                bestand = os.path.join(STATIC, "favicon.ico")
                if os.path.exists(bestand):
                    with open(bestand, "rb") as f:
                        return self._stuur(200, f.read(), "image/x-icon")
                return self._stuur(204, b"", "image/x-icon")
            if pad.startswith("/static/"):
                bestand = os.path.normpath(os.path.join(STATIC, pad[len("/static/"):]))
                if not bestand.startswith(STATIC) or not os.path.exists(bestand):
                    return self._stuur(404, {"fout": "niet gevonden"})
                soort = {"css": "text/css", "js": "text/javascript",
                         "html": "text/html", "svg": "image/svg+xml",
                         "ico": "image/x-icon"}.get(
                    bestand.rsplit(".", 1)[-1], "application/octet-stream")
                with open(bestand, "rb") as f:
                    # Alleen tekst krijgt een tekenset mee; bij een pictogram of lettertype hoort die
                    # er niet.
                    tekenstel = ("; charset=utf-8"
                                 if soort.startswith("text/") or soort.endswith("svg+xml") else "")
                    return self._stuur(200, f.read(), soort + tekenstel)
            return self._stuur(404, {"fout": "onbekende route", "route": pad})
        except kern_invoer.InvoerFout as e:
            # Een bestand dat niet te lezen is hoort een regel in gewone taal te geven, geen 500.
            return self._stuur(400, {"fout": " ".join(e.meldingen), "fouten": e.meldingen,
                                     "velden": e.velden})
        except Exception as e:
            return self._storing(e, wat="het openen van deze pagina")

    def do_DELETE(self):
        """Een eigen plaats uit `data/eigen-plaatsen.tsv` halen.

        Sleutel is naam + coordinaten: die combinatie is uniek in het bestand en overleeft het met de
        hand bewerken ervan, wat een regelnummer niet doet.
        """
        lengte = int(self.headers.get("Content-Length") or 0)
        try:
            vraag = json.loads(self.rfile.read(lengte) or b"{}")
        except Exception as e:
            return self._stuur(400, {"fout": "geen geldige JSON: %s" % e})
        try:
            if self.path == "/api/eigenplaats":
                weg = plaatsen.verwijder_eigen(vraag.get("naam"), vraag.get("lat"), vraag.get("lon"))
                if weg is None:
                    return self._stuur(404, {"fout": "Die plaats staat niet (meer) in "
                                                     + os.path.basename(plaatsen.EIGEN) + "."})
                return self._stuur(200, {"verwijderd": weg.split("\t")[0],
                                         "bestand": os.path.basename(plaatsen.EIGEN)})
            return self._stuur(404, {"fout": "onbekende route"})
        except kern_invoer.InvoerFout as e:
            return self._stuur(400, {"fout": " ".join(e.meldingen), "fouten": e.meldingen,
                                     "velden": e.velden})
        except Exception as e:
            return self._storing(e, vraag, wat="het weghalen van deze plaats")

    def do_POST(self):
        # De twee meldingen van het venster komen vóór het JSON-lezen: `sendBeacon`
        # stuurt een lege tekst mee, geen JSON. Het lichaam wordt wel weggelezen, anders blijft het
        # in de verbinding staan en verstoort het het volgende verzoek op die verbinding.
        pad = self.path.split("?")[0]
        lengte = int(self.headers.get("Content-Length") or 0)
        if pad in ("/api/venster", "/api/afgesloten"):
            if lengte:
                self.rfile.read(lengte)
            if not self._van_eigen_pagina():
                return self._stuur(403, {"fout": "Deze oproep komt niet van de eigen pagina."})
            vraag = urllib.parse.parse_qs(self.path.partition("?")[2])
            tid = (vraag.get("id") or [""])[0][:64]
            if pad == "/api/venster":
                return self._stuur(200, {"ok": True, "open": _venster_meld(tid)})
            return self._stuur(200, {"ok": True, "open": _venster_weg(tid, self.server)})
        try:
            vraag = json.loads(self.rfile.read(lengte) or b"{}")
        except Exception as e:
            return self._stuur(400, {"fout": "geen geldige JSON: %s" % e})
        try:
            if self.path == "/api/afsluiten":
                # Afsluiten: eerst antwoorden, dan pas stoppen - anders krijgt de
                # pagina een dode verbinding in plaats van een nette melding.
                # Alleen vanaf de eigen pagina: zie `_van_eigen_pagina`.
                if not self._van_eigen_pagina():
                    return self._stuur(403, {"fout": "Deze oproep komt niet van de eigen pagina."})
                # Wachten in de console terwijl het venster zichzelf sluit: dezelfde marge als bij
                # het kruisje (één getal, één gedrag), zodat beide routes hetzelfde blok printen.
                threading.Thread(target=_stop_na_aftellen,
                                 args=(self.server, WACHT_NA_SLUITEN, False), daemon=True).start()
                return self._stuur(200, {"ok": True,
                                         "melding": "Astrologie Studio is afgesloten."})
            if self.path == "/api/vensterstaat":
                # De maten van het venster: de pagina meldt ze zodat de volgende start
                # hetzelfde venster opent (volledig scherm, gemaximaliseerd, of die maat).
                if not self._van_eigen_pagina():
                    return self._stuur(403, {"fout": "Deze oproep komt niet van de eigen pagina."})
                try:
                    bewaar_vensterstaat(vraag)
                except ValueError as e:
                    return self._stuur(400, {"fout": str(e)})
                return self._stuur(200, {"ok": True})
            if self.path == "/api/rekenen":
                return self._stuur(200, _rekenen(vraag))
            if self.path == "/api/solaar":
                return self._stuur(200, _solaar(vraag))
            if self.path == "/api/transits/nu":
                # De standen van dit moment in de huizen van de geladen horoscoop. Dit is de eerste
                # stand van de Transits-tab en de basis van het latere bi-wheel. Zelfde
                # berekening als de momentopname in /api/transits, maar zonder de lijst: 0,15 ms, en
                # dus licht genoeg om elke 20 seconden te tikken.
                return self._transits_nu(vraag)
            if self.path == "/api/transits":
                return self._transits(vraag)
            if self.path == "/api/progressies/nu":
                # De standen bij de leeftijd van vandaag. De eerste stand van de
                # Progressies-tab, en de buitenring van het bi-wheel in de stand "progressies".
                return self._progressies_nu(vraag)
            if self.path == "/api/progressies":
                return self._progressies(vraag)
            if self.path == "/api/maanfasen":
                # De progressieve maanfasen (les 20-II): alleen de hoek tussen de progressieve Zon en
                # Maan, in acht stukken van 45 graden. Klein genoeg om in één keer te antwoorden.
                return self._maanfasen(vraag)
            if self.path == "/api/invoer":
                # Wat de kern van één veld maakt, zodat het formulier de standaardvorm kan tonen
                # zonder de lezer na te bouwen. Nooit een 400: zwijgen is het antwoord
                # op een waarde die nog niet af is.
                return self._stuur(200, _invoer(vraag))
            if self.path == "/api/bewaren":
                # `id` in de vraag is de kaart die overschreven wordt (het anker, niet de
                # bestandsnaam: die verandert als de gebruiker de kaart hernoemt). Zonder id, of
                # met een onbekend id, is het een nieuwe kaart.
                pad, nieuw, cid = opslag.bewaar(vraag["kaart"], vervang=vraag.get("id"))
                return self._stuur(200, {"bewaard": pad, "bestand": os.path.basename(pad),
                                         "nieuw": nieuw, "id": cid})
            if self.path == "/api/instellingen":
                # De huidige locatie opslaan; het bestand staat vast (ASTRO_INSTELLINGEN of naast de
                # kaarten) - er is geen veld om ergens anders te schrijven. `nu` gaat mee zodat
                # de pagina de kaart van nu meteen opnieuw kan rekenen met de nieuwe locatie.
                # De cursusjaren liften mee op hetzelfde verzoek (T48): één venster, één knop. Ze
                # worden hier gekeurd tegen de modulebestanden, zodat er nooit een jaar in het
                # instellingenbestand komt dat dit programma niet kan uitvoeren.
                gevraagd = vraag.get("modules")
                if gevraagd is not None:
                    if not isinstance(gevraagd, list) or not all(
                            isinstance(j, int) and not isinstance(j, bool) and j >= 1 for j in gevraagd):
                        raise kern_invoer.InvoerFout(
                            ["De cursusjaren horen als lijst met jaartallen te komen."])
                    onbekend = [j for j in gevraagd if j not in _beschikbare_jaren()]
                    if onbekend:
                        raise kern_invoer.InvoerFout(
                            ["Dit programma kent de module van cursusjaar %s niet (wel: %s)."
                             % (", ".join(str(j) for j in onbekend),
                                ", ".join(str(j) for j in _beschikbare_jaren()))])
                antwoord = kern_instellingen.bewaar(vraag, modules_=gevraagd)
                antwoord["nu"] = _nu_moment()
                return self._stuur(200, antwoord)
            if self.path == "/api/osm-zoek":
                # OpenStreetMap als aanvulling op de eigen lijst, via de eigen proxy op
                # studio.astrosofica.nl: de gebruiker heeft geen e-mailadres nodig, want de proxy
                # vraagt met de gegevens van de beheerder. Alleen op een
                # expliciete klik van de gebruiker.
                tekst = str(vraag.get("q") or "").strip()
                return self._stuur(200, {"q": tekst, "plaatsen": osm.zoek(tekst),
                                         "bron": "OpenStreetMap, © OpenStreetMap contributors (ODbL)"})
            if self.path == "/api/eigenplaats":
                # Een plaats toevoegen aan data/eigen-plaatsen.tsv (de schrijfkant).
                plaats, bestond = plaatsen.voeg_eigen_toe(
                    naam=vraag.get("naam"), lat=vraag.get("lat"), lon=vraag.get("lon"),
                    land=vraag.get("land"), zone=vraag.get("zone"),
                    streek=vraag.get("streek"), gemeente=vraag.get("gemeente"),
                    bron=vraag.get("bron"))
                return self._stuur(200, {"plaats": plaats, "bestond": bestond,
                                         "bestand": os.path.basename(plaatsen.EIGEN)})
            if self.path == "/api/lees":
                # Het verzoek heeft geen `map`-veld. Zo'n parameter wees elke map op de schijf als
                # kaartenmap aan, en `/api/verwijder` wiste daar dan een `.json` in. De map komt uit
                # de instellingen en nergens anders vandaan.
                return self._stuur(200, opslag.lees(vraag["bestand"]))
            if self.path == "/api/verwijder":
                naam = opslag.verwijder(vraag["bestand"])
                return self._stuur(200, {"verwijderd": naam})
            return self._stuur(404, {"fout": "onbekende route"})
        except kern_invoer.InvoerFout as e:
            # Invoer die niet klopt is geen storing: 400 met de regels in gewone taal.
            return self._stuur(400, {"fout": " ".join(e.meldingen), "fouten": e.meldingen,
                                     "velden": e.velden})
        except Exception as e:
            return self._storing(e, vraag, wat="het verwerken van deze vraag")


# --- de zelfcontrole van de gebouwde app ------------------------------------------------------
# `--controle` is wat de bouw na het verpakken aanroept. Het controlepunt dat er echt toe doet is
# niet of een bestand in het archief zit, maar of het programma er ook bij kan: daarom rekent deze
# controle een kaart en kijkt of de standen uit Swiss Ephemeris komen en niet uit de Moshier-
# benadering. Dat is precies de stille terugval die een bundel kan veroorzaken.

def _static_bestanden():
    """Elk bestand onder `schil/static`, als pad vanaf de leesmap.

    De opmaak staat in `schil/static/css` en de bediening in `schil/static/js`; de pagina laadt ze
    los. Ze meetellen in de bundelcontrole kan alleen door de map te lopen - een
    lijst met namen raakt achterop zodra er een bestand bij komt, en dan valt een half scherm pas op
    als een gebruiker het ziet.
    """
    uit = []
    for basis, _mappen, bestanden in os.walk(paden.bron("schil", "static")):
        for naam in bestanden:
            uit.append(os.path.relpath(os.path.join(basis, naam), paden.bron("")))
    return sorted(uit)


NODIG_VOOR_DE_BUNDEL = (
    "efemeriden/sepl_18.se1", "efemeriden/semo_18.se1", "efemeriden/seas_18.se1",
    "data/plaatsen.json", "data/glyph-maten.json", "data/osm-dienst.json",
    "data/eigen-plaatsen.tsv",
    # De map schil/static wordt hieronder in zijn geheel nagelopen:
    # de pagina, de fonts en alles in css/ en js/. Losse namen zouden een nieuw bestand stilzwijgend
    # buiten de controle laten.
    "teken/spec.json",
    "technieken/jaar1.json", "technieken/jaar2.json", "technieken/chiron.json",
    "technieken/dominant.json", "technieken/solaar.json", "technieken/wiel.json",
    "technieken/radix.json",
    "technieken/aspecten.json", "technieken/heerschappen.json",
    "technieken/element-kruis.json", "technieken/afdruk.json", "technieken/opslag.json",
    "LICENSE", "README.md",
    "data/fonts/LICENTIE-AstroSans.txt", "data/fonts/LICENTIE-Selawik.txt",
    "data/fonts/bron/Source_Sans_3-OFL.txt", "data/fonts/bron/StarfisherUni-OFL.txt",
)


def _controle():
    """Zelfcontrole: (1) de bestanden, (2) of ze leesbaar zijn, (3) of de efemeriden echt gebruikt
    worden, (4) of er geschreven kan worden waar het programma schrijft. Exit 0 of 1."""
    fouten = []

    def meld(goed, regel, detail=""):
        print(("ok    " if goed else "FOUT  ") + regel + ((" - " + detail) if detail else ""))
        if not goed:
            fouten.append(regel)

    print("Astrologie Studio - zelfcontrole")
    print("vorm:       %s" % ("bundel" if paden.GEBUNDELD else "bronmap"))
    print("leesmap:    %s" % paden.bron(""))
    print("schrijfmap: %s" % paden.standaardmap())
    print("")

    # De statische map in zijn geheel: de pagina laadt de css- en js-bestanden los, dus die horen
    # allemaal in de bundel te zitten. Een ontbrekend bestand zou een half scherm geven zonder fout.
    vast = list(NODIG_VOOR_DE_BUNDEL) + _static_bestanden()
    ontbreekt = [n for n in vast
                 if not (os.path.isfile(paden.bron(n)) and os.path.getsize(paden.bron(n)) > 0)]
    meld(not ontbreekt, "%d bestanden aanwezig" % len(vast),
         ("ontbreekt of is leeg: " + ", ".join(ontbreekt)) if ontbreekt else "")

    # De efemeriden: een kaart rekenen en kijken welke efemeride er gebruikt is. Bewust een datum
    # vóór 1970: op Windows gaat het daar mis (negatieve tijdstempel -> Errno 22), en een ijkpunt
    # uit 1985 zou dat niet blootleggen.
    try:
        k = kern_kaart.maak_kaart("Controle", 1963, 7, 19, 16, 51, 26, "Europe/Amsterdam",
                                  51.675, 4.27917, plaats="Controleplaats")
        soort = k["meta"]["efemeride"]
        meld(soort == "Swiss Ephemeris", "efemeriden in gebruik", soort)
    except Exception as e:
        k, soort = None, str(e)
        meld(False, "efemeriden in gebruik", soort)

    # De standen zelf: tegen het ijkpunt dat bij deze bronversie hoort (tolerantie 0,001 graad).
    try:
        with open(paden.bron("bouw", "controle-verwacht.json"), encoding="utf-8") as f:
            verwacht = json.load(f)
        punten = {p["naam"]: p["lengte"] for p in k["punten"]} if k else {}
        gemeten = {"Zon": punten.get("Zon"), "Maan": punten.get("Maan"),
                   "Ascendant": (k["ascendant"]["lengte"] if k else None),
                   "MC": (k["mc"]["lengte"] if k else None)}
        tolerantie = float(verwacht.get("tolerantie", 0.001))
        mis = [n for n, w in verwacht["standen"].items()
               if gemeten.get(n) is None or abs(gemeten[n] - w) > tolerantie]
        meld(not mis, "standen gelijk aan het ijkpunt (%s, %g graden)" % (
            verwacht["kaart"]["datum"] + " " + verwacht["kaart"]["tijd"] + " "
            + verwacht["kaart"]["plaats"], tolerantie),
            ("wijkt af: " + ", ".join(
                "%s %s tegen %s" % (n, gemeten.get(n), verwacht["standen"][n]) for n in mis))
            if mis else "")
    except Exception as e:
        meld(False, "standen gelijk aan het ijkpunt", str(e))

    # Het wiel: tekent het, en zit het meegeleverde font er als data-URI in?
    try:
        svg, botsingen = wiel.teken(k)
        # `botsingen` is een dict ({"paren": [...], "aantal": n}); `len` daarvan is altijd 2 en zou
        # "2 botsingen" melden waar er nul zijn. De zelfcontrole telt het werkelijke aantal.
        meld(len(svg) > 1000 and "data:font/ttf;base64" in svg, "wiel getekend met het eigen font",
             "%d tekens, %d botsingen" % (len(svg), botsingen.get("aantal", 0)))
    except Exception as e:
        meld(False, "wiel getekend met het eigen font", str(e))

    # De precisie-afspraak (besluit T47): afronding mag alleen waar het de weergave betreft, nooit in de
    # data waarmee gerekend wordt. Een stand die halverwege
    # is afgerond kun je niet terugrekenen, dus deze controle bewaakt de bron zelf. `round` mag alleen
    # waar het om *tijd* gaat, en dat zijn twee bestanden met een eigen reden; afkappen op hele graden
    # of boogminuten hoort in `formaat`, niet in de rekenkern.
    try:
        if paden.GEBUNDELD:
            meld(True, "geen afronding in de rekenkern", "overgeslagen: de bron is in een bundel niet te lezen")
        else:
            toegestaan = {("solaar.py", "round"), ("tijd.py", "round")}
            gevonden = []
            for bestand in sorted(os.listdir(paden.bron("kern"))):
                if not bestand.endswith(".py"):
                    continue
                with open(paden.bron("kern", bestand), encoding="utf-8") as f:
                    for nummer, regel in enumerate(f, 1):
                        code = regel.split("#")[0]
                        for naam in ("round(", "math.floor(", "math.ceil(", "math.trunc("):
                            if naam in code and (bestand, naam[:-1]) not in toegestaan:
                                gevonden.append("%s:%d %s" % (bestand, nummer, naam[:-1]))
            # En de standen zelf: een lengte die op een hele boogminuut valt is afgerond, en dan is de
            # controle hierboven er alsnog langs gekomen (bijvoorbeeld via een omweg).
            afgerond = []
            if k:
                for punt in k["punten"]:
                    minuten = punt["lengte"] * 60.0
                    if abs(minuten - round(minuten)) < 1e-6:
                        afgerond.append(punt["naam"])
            meld(not gevonden and not afgerond, "geen afronding in de rekenkern",
                 ("gevonden: " + ", ".join(gevonden[:5])) if gevonden else
                 ("afgerond op een boogminuut: " + ", ".join(afgerond)) if afgerond else
                 "alleen tijd (solaar, tijd); de standen houden hun decimalen")
    except Exception as e:
        meld(False, "geen afronding in de rekenkern", str(e))

    # De plaatsenlijst.
    try:
        treffers = plaatsen.zoek("Dieren")
        meld(bool(treffers), "plaatsenlijst leesbaar",
             (treffers[0].get("naam", "?") if treffers else "geen treffer voor Dieren"))
    except Exception as e:
        meld(False, "plaatsenlijst leesbaar", str(e))

    # De OSM-dienst (de proxy) moet in de bundel zitten; of hij bereikbaar is, is een netwerkvraag
    # en hoort niet in deze controle.
    try:
        with open(osm.DIENST_BESTAND, encoding="utf-8") as f:
            dienst = json.load(f)["dienst"]
        meld(bool(dienst), "dienst voor OpenStreetMap ingesteld", dienst)
    except Exception as e:
        meld(False, "dienst voor OpenStreetMap ingesteld", str(e))

    # Schrijven: de horoscopen, de instellingen en de cache moeten in de schrijfmap kunnen.
    try:
        proef = paden.gebruikersmap("controle-schrijfproef.tmp")
        with open(proef, "w", encoding="utf-8") as f:
            f.write("controle")
        os.remove(proef)
        meld(True, "schrijfmap beschrijfbaar", paden.standaardmap())
    except Exception as e:
        meld(False, "schrijfmap beschrijfbaar", str(e))

    # En de staat-map apart: daar komen de vensterstand, de OSM-cache en fouten.log.
    # Zonder deze controle zou een onbeschrijfbare submap pas opvallen als een fout niet in het log
    # staat - en dan is de melding aan de gebruiker ("de details staan in fouten.log") een leugen.
    try:
        proef = paden.staat("controle-schrijfproef.tmp")
        with open(proef, "w", encoding="utf-8") as f:
            f.write("controle")
        os.remove(proef)
        meld(True, "staat-map beschrijfbaar", paden.staat())
    except Exception as e:
        meld(False, "staat-map beschrijfbaar", str(e))

    print("")
    if fouten:
        print("NIET IN ORDE: %d van de controles faalt." % len(fouten))
        raise SystemExit(1)
    print("In orde: alle controles geslaagd.")
    raise SystemExit(0)


def _maak_server():
    """De schil op de eerste vrije poort vanaf POORT (10 pogingen)."""
    laatste = None
    for poort in range(POORT, POORT + 10):
        try:
            return ThreadingHTTPServer((HOST, poort), Handler), poort
        except OSError as e:
            laatste = e
    raise SystemExit("Geen vrije poort tussen %d en %d (%s)." % (POORT, POORT + 9, laatste))


def _draait_al(poort):
    """Antwoordt op deze poort ons eigen programma? Dan is een tweede start niet nodig."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/api/leeft" % poort, timeout=0.7) as a:
            return json.load(a).get("programma") == PROGRAMMA
    except Exception:
        return False


def _controle_met_verslag():
    """`--controle`, met het verslag ook op schijf.

    In de versie zonder consolevenster is er niets om naar te kijken, en dan zou een mislukte
    controle onzichtbaar langskomen. `bouw-windows.bat` leest daarom `controle-uitkomst.txt` in
    plaats van het scherm.
    """
    verslag, echt = [], sys.stdout

    class _Tee:
        def write(self, s):
            verslag.append(s)
            if echt is not None:
                echt.write(s)

        def flush(self):
            if echt is not None:
                echt.flush()

    sys.stdout = _Tee()
    try:
        code = _controle()
    finally:
        sys.stdout = echt
        try:
            with open("controle-uitkomst.txt", "w", encoding="utf-8") as f:
                f.write("".join(verslag))
        except OSError:
            pass
    return code


def _meld(tekst, fout=False):
    """Iets zeggen dat de gebruiker moet zien. Zonder consolevenster gaat dat via Windows.

    `fout` kiest het pictogram: een rood kruis voor iets dat misging, een i voor iets dat gewoon zo
    is (bijvoorbeeld: het programma draait al).
    """
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, tekst, "Astrologie Studio", 0x10 if fout else 0x40)
    except Exception:
        if sys.stderr is not None:
            sys.stderr.write(tekst + "\n")


# Eén programma tegelijk. Een nieuwe versie installeren terwijl het programma nog openstaat loopt
# mis: Inno Setup probeert het venster te sluiten, dat lukt niet (dit is een console met een server
# erachter, geen venster dat op een sluitbericht reageert), en het programma is daarna niet meer
# netjes af te sluiten - de terminal moet worden gedood.
#
# Daarom werkt het andersom: de app maakt bij het starten een Windows-mutex met een vaste naam, en de installer
# (AppMutex + CloseApplications=no in bouw/astrologie-studio.iss) weigert dan verder te gaan met de
# vraag het programma eerst via Bestand > Afsluiten te sluiten. De naam staat in twee bestanden en moet
# gelijk zijn; de ijking buiten de repo vergelijkt ze met elkaar.
#
# Een grens die je moet kennen: een mutex ziet dát er een proces is, niet of het nog leeft. Hangt het
# programma echt vast, dan houdt de mutex de installatie tegen en is Annuleren + Taakbeheer de uitweg.
MUTEX_NAAM = "AstrologieStudio"
_MUTEX = None


def _kernel32():
    """De Windows-API, of None elders (daar is geen mutex nodig en valt er niets stuk te gaan)."""
    if os.name != "nt":
        return None
    try:
        import ctypes
        return ctypes.windll.kernel32
    except (AttributeError, OSError):
        return None


def maak_mutex(naam=MUTEX_NAAM):
    """De mutex aanmaken waaraan de installer ziet dat dit programma draait.

    Het handvat blijft in `_MUTEX` staan: zolang het proces leeft bestaat de mutex, en bij het
    afsluiten ruimt Windows hem zelf op - er is dus geen opruimcode en geen bestand.

    Een mislukking is voor het programma zelf geen ramp (het start gewoon), maar wel een melding: dan
    kan de installer een draaiend programma niet herkennen. Daarom print een mislukking altijd en een
    gelukte aanmaak nooit: dat laatste is ontwikkelaarsinformatie (dezelfde regel als bij de
    vensterregel).
    """
    global _MUTEX
    if _MUTEX is not None:
        return _MUTEX
    api = _kernel32()
    if api is None:
        return None
    try:
        import ctypes
        api.CreateMutexW.restype = ctypes.c_void_p
        api.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
        _MUTEX = api.CreateMutexW(None, 0, naam)
    except (AttributeError, OSError) as e:
        print("  mutex        niet aangemaakt (%s: %s) - een draaiend programma is voor de installer "
              "niet te herkennen" % (type(e).__name__, e), flush=True)
        return None
    return _MUTEX


def main():
    global STIL
    if "--controle" in sys.argv[1:]:
        return _controle_met_verslag()
    if sys.stdout is None or sys.stderr is None:
        # Zonder consolevenster (PyInstaller `console=False`) is er geen uitvoer: alles wat het
        # programma print gaat dan naar fouten.log in de staat-map, in plaats van
        # ergens te verdwijnen of op een None-object te knallen.
        STIL = True
        try:
            log = open(paden.staat("fouten.log"), "a", encoding="utf-8", buffering=1)
            sys.stdout = sys.stderr = log
        except OSError:
            class _Niets:
                def write(self, s):
                    pass

                def flush(self):
                    pass
            sys.stdout = sys.stderr = _Niets()
    # Vóór de server en het venster: zolang dit programma draait, hoort de installer te weigeren.
    maak_mutex()
    try:
        _start()
    except SystemExit:
        raise
    except Exception as e:
        traceback.print_exc()
        _meld("Astrologie Studio kon niet starten:\n\n%s" % e, fout=True)
        return 1
    return 0


# Het venster van de bundel. `webbrowser.open` geeft een gewoon tabblad, en dat kost
# op een laptop met 768 px ongeveer 110 px aan tabbladen, adresbalk en bookmarkbalk - dan valt de
# onderkant van het formulier onder de statusbalk. Chromium-browsers hebben een app-modus
# (`--app=`) zonder die drie balken; Edge staat op elke Windows-pc en wordt daarom als eerste
# geprobeerd. Firefox kent geen app-modus, dus daar blijft het een gewoon tabblad.
APP_VENSTER = (1440, 900)


def _browser_kandidaten():
    """De browsers waarin `--app=` werkt, in de orde waarin we ze proberen.

    `ASTRO_BROWSER` wijst er één aan (handig bij een ongewone installatie, en om dit op de server
    te kunnen proeven).
    """
    if os.environ.get("ASTRO_BROWSER"):
        return [os.environ["ASTRO_BROWSER"]]
    paden_ = []
    if os.name == "nt":
        for map_ in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"),
                     os.environ.get("LOCALAPPDATA")):
            if not map_:
                continue
            paden_ += [os.path.join(map_, r"Microsoft\Edge\Application\msedge.exe"),
                       os.path.join(map_, r"Google\Chrome\Application\chrome.exe"),
                       os.path.join(map_, r"BraveSoftware\Brave-Browser\Application\brave.exe"),
                       os.path.join(map_, r"Chromium\Application\chrome.exe")]
    else:
        for naam in ("microsoft-edge", "google-chrome", "google-chrome-stable",
                     "chromium", "brave-browser"):
            paden_.append(shutil.which(naam))
    return [p for p in paden_ if p and os.path.isfile(p)]


# Het venster onthouden. Op een groot scherm in volledig scherm met weergave 150% opent het venster
# zonder deze stand elke keer weer op 1440x900, dus moet dat telkens opnieuw worden ingesteld. De pagina meldt
# de **maten** van het venster (buitenmaat, schermmaat,
# beschikbare schermmaat) en de schil kiest daar bij de volgende start de vlag uit. De drempels staan
# hier en niet in de pagina: één plek, en de getallen komen van de machine waar het venster opent.
#
# Bewust een eigen bestand (`venster.json`) en niet een sleutel in `settings.json`: dat bestand heeft
# een contract met een versienummer en een keuring per veld, en een venstermaat hoort daar niet in.
VENSTERSTAAT = "venster.json"


def _vensterstaat_pad() -> str:
    return paden.staat(VENSTERSTAAT)


def lees_vensterstaat():
    """De laatst gemelde venstermaten, of None als er nog niets gemeld is."""
    try:
        with open(_vensterstaat_pad(), encoding="utf-8") as f:
            staat = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(staat, dict):
        return None
    return staat


# Hoe dicht twee maten bij elkaar moeten liggen om "hetzelfde" te zijn. Voor de buitenmaat is dat
# exact (een venster dat het scherm vult is even groot), voor het beeldvlak een paar pixels: de rand
# en een schuifbalk kunnen schelen. Een gemaximaliseerd venster zit tientallen pixels onder de
# schermhoogte, dus die marge maakt de twee standen niet aan elkaar gelijk.
MARGE_BUITEN = 2
MARGE_BINNEN = 8


def _bijna(a, b, marge=MARGE_BUITEN) -> bool:
    return (a is not None and b is not None
            and abs(a[0] - b[0]) <= marge and abs(a[1] - b[1]) <= marge)


def _maat(waarde):
    """Een bruikbare maat als (breedte, hoogte), of None. Geen `True`/`False`: dat zijn ints."""
    if (isinstance(waarde, list) and len(waarde) == 2
            and all(isinstance(x, (int, float)) and not isinstance(x, bool) and 200 <= x <= 20000
                    for x in waarde)):
        return (int(waarde[0]), int(waarde[1]))
    return None


def bewaar_vensterstaat(staat) -> None:
    """Schrijf de maten weg; onzin wordt geweigerd in plaats van opgeslagen."""
    if not isinstance(staat, dict):
        raise ValueError("geen vensterstaat")
    buiten = _maat(staat.get("buiten"))
    if buiten is None:
        raise ValueError("geen bruikbare venstermaat")
    schoon = {"buiten": list(buiten)}
    for sleutel in ("binnen", "scherm", "beschikbaar"):
        maat = _maat(staat.get(sleutel))
        if maat is not None:
            schoon[sleutel] = list(maat)
    # Waar het venster staat. Niet gebruikt om iets te beslissen (de schil zet geen positie), maar het
    # maakt het bestand leesbaar als een stand niet klopt: volledig scherm begint linksboven.
    links = staat.get("links")
    if isinstance(links, list) and len(links) == 2 and all(isinstance(x, (int, float)) for x in links):
        schoon["links"] = [int(links[0]), int(links[1])]
    # De maat waar "kleiner" naar terugvalt. De pagina meldt hem alleen als het venster niet
    # schermvullend is; anders blijft de vorige bewaarde maat staan, want een melding vanuit volledig
    # scherm zou hem anders met de schermmaat overschrijven.
    rust = _maat(staat.get("rust"))
    if rust is None:
        rust = _maat((lees_vensterstaat() or {}).get("rust"))
    if rust is not None:
        schoon["rust"] = list(rust)
    with open(_vensterstaat_pad(), "w", encoding="utf-8") as f:
        json.dump(schoon, f)


def venster_stand():
    """De stand waarin het venster moet openen, met de maat waar "kleiner" naar terugvalt.

    Geeft `(stand, rust, positie)`: `stand` is "volledig", "gemaximaliseerd" of "gewoon", `rust` een
    (breedte, hoogte) en `positie` een (links, boven) of None. Zonder staat: de vaste maat.

    Volledig scherm als de buitenmaat de **hele** schermmaat vult, gemaximaliseerd als hij de
    beschikbare maat vult (scherm min taakbalk), anders gewoon die maat. Twee signalen voor "vult het
    scherm": de buitenmaat (Linux, gewone browservensters) of het beeldvlak (Windows app-modus, waar
    de buitenmaat blijft staan - gemeten: buiten 1444x900 bij een scherm van 2134x1200, met een
    beeldvlak van 2134x1200).
    """
    staat = lees_vensterstaat() or {}
    buiten = _maat(staat.get("buiten"))
    if buiten is None:
        return venster.STAND_GEWOON, APP_VENSTER, None
    rust = _maat(staat.get("rust")) or buiten
    positie = None
    links = staat.get("links")
    if isinstance(links, list) and len(links) == 2:
        try:
            positie = (int(links[0]), int(links[1]))
        except (TypeError, ValueError):
            positie = None
    binnen = _maat(staat.get("binnen"))
    scherm = _maat(staat.get("scherm"))
    beschikbaar = _maat(staat.get("beschikbaar"))
    # Wat er teruggaat wordt naar het werkblad geklemd. Op een scherm met 150 % weergave
    # is het werkblad kleiner dan de bewaarde maat, en dan valt de onderkant van het venster - met de
    # groene statusbalk - achter de taakbalk. De toetsen hieronder gebruiken de **gemelde** maten: een
    # geklemde buitenmaat zou "vult het scherm" kunnen breken, en dan opent een schermvullend venster
    # als gewoon venster.
    rust = venster.klem_maat(rust, beschikbaar)
    buiten_geklemd = venster.klem_maat(buiten, beschikbaar)
    if _bijna(buiten, scherm) or _bijna(binnen, scherm, MARGE_BINNEN):
        return venster.STAND_VOLLEDIG, rust, positie
    if (beschikbaar and (buiten[1] >= beschikbaar[1] - MARGE_BUITEN
                         or (binnen is not None and binnen[1] >= beschikbaar[1] - MARGE_BINNEN))):
        return venster.STAND_GEMAXIMALISEERD, rust, positie
    return venster.STAND_GEWOON, buiten_geklemd, positie


def venster_vlaggen():
    """De vlaggen waarmee het venster opent: alleen de **beginmaat**.

    De schil zet de stand zelf, met de Windows-API (`schil/venster.py`). Deze
    vlaggen zorgen alleen dat het venster meteen op de goede maat en plaats verschijnt, in plaats van
    eerst op Chromium's standaardmaat (gemeten: 945x1012 op een scherm van 1920x1080) en dan te
    verspringen. Waarom de stand niet meer via de vlaggen gaat, is alle drie gemeten op Windows 11
    met Edge 156:

      * `--start-maximized` maximaliseert wel, maar zet als **herstelmaat** Chromium's eigen standaard
        (945x1012) - dat is het halve scherm bij "kleiner";
      * `--window-size` wint van `--start-maximized`, dus die twee samen openen gewoon op die maat;
      * een browser die al draait negeert alle venstervlaggen van een tweede `--app=`-start.

    `--start-fullscreen` staat er niet bij. Die vlag werkt
    wel bij een verse start, maar zet de herstelmaat op de **schermmaat**: na F11 kwam het venster dan
    op 1920x1080 in plaats van op de rustmaat. Zet de schil eerst de maat en daarna F11, dan landt
    "uit volledig scherm" wél op de rustmaat (gemeten: 900x700). Het venster is dan een tel eerder in
    beeld op de rustmaat - dat is de prijs, en die is kleiner dan een verkeerde herstelmaat.
    """
    _, rust, positie = venster_stand()
    # De beginmaat in de eenheid die de browser leest. Chromium leest `--window-size` in beeldpunten
    # (gemeten: 1440 gevraagd gaf een venster van 1200 CSS-pixels), en dan opent het venster te
    # klein, meet de pagina die maat en bewaart hem als rustmaat - de krimp die daaruit volgt.
    schaal = venster.beginschaal(venster_schermmaat())
    vlaggen = ["--window-size=%d,%d" % (round(rust[0] * schaal), round(rust[1] * schaal))]
    if positie:
        vlaggen.append("--window-position=%d,%d" % (round(positie[0] * schaal),
                                                     round(positie[1] * schaal)))
    return vlaggen


def venster_tekst():
    """De openingsstand in gewone taal, voor het startblok.

    Afgeleid uit de stand, zodat er maar één plek is die hem bepaalt. Nuttig bij het uitzoeken van een
    verkeerde stand: de gebruiker leest dit in zijn console en hoeft geen bestand te openen.
    """
    stand, rust, _ = venster_stand()
    if stand == venster.STAND_VOLLEDIG:
        return "volledig scherm (herstelmaat %d x %d)" % rust
    if stand == venster.STAND_GEMAXIMALISEERD:
        return "gemaximaliseerd (herstelmaat %d x %d)" % rust
    return "%d x %d" % rust


def bewaar_rust(maat) -> None:
    """De rustmaat vastleggen die de schil zojuist heeft gezet.

    De pagina kan dat niet altijd: is het venster eenmaal schermvullend, dan meet ze de schermmaat en
    niet de maat waar "kleiner" naartoe gaat (bij die maat meldt Edge in app-modus gewoon het
    werkblad).
    Zonder deze regel blijft de meting van vlak na het opstarten staan - en dat is de maat waarop de
    browser opende, niet de maat van het programma. Dat is precies de krimp die hij zag.
    """
    staat = lees_vensterstaat()
    if not staat:
        return
    staat["rust"] = [int(maat[0]), int(maat[1])]
    try:
        bewaar_vensterstaat(staat)
    except ValueError:
        pass


def venster_schermmaat():
    """De schermmaat die de pagina meldt, in CSS-pixels (of None).

    Nodig om de schaal te bepalen: de venster-API rekent bij weergave boven 100 % in beeldpunten, en
    het verschil tussen de monitor die de API ziet en deze maat is precies die schaal (zie
    `schil/venster.py`).
    """
    return _maat((lees_vensterstaat() or {}).get("scherm"))


def _pas_venster_toe(stand, rust, positie, kenmerk):
    """De stand toepassen zodra het venster er is (draait op de achtergrond).

    Nooit laten stuklopen op iets wat de Windows-API teruggeeft: het programma moet ook starten als
    het venster niet gevonden wordt of de aanroep faalt. Dan staat er één regel in de console en
    verder verandert er niets.
    """
    gelukt = False
    try:
        regel, gelukt = venster.pas_toe(stand, rust, positie, kenmerk,
                                        scherm=venster_schermmaat())
    except Exception as e:                                          # noqa: BLE001
        regel = "de stand is niet toegepast (%s: %s)" % (type(e).__name__, e)
    if gelukt:
        # De schil heeft de maat net gezet en nagemeten: dat is de rustmaat, wat de pagina ook meldt.
        bewaar_rust(rust)
    if regel and not STIL and (not gelukt or ALLES_OP_HET_SCHERM):
        # Alleen een **mislukking** is een mededeling aan de gebruiker (punt 3 vóór 0.5.0):
        # die verklaart een venster dat niet doet wat hij verwacht. Een gelukte stand is
        # ontwikkelaarsinformatie en hoort achter `--log`/ASTRO_LOG, net als de access-log. Zonder die
        # vlag blijft het scherm dus leeg zolang het venster doet wat het moet doen.
        print("  venster      %s" % regel, flush=True)


def _open_venster(adres):
    """Het venster openen: eerst een browser met app-modus, anders een gewoon tabblad.

    Geeft terug of er iets geopend is; de tweede start gebruikt dat om te weten of er nog iets te
    melden valt.
    """
    stand, rust, positie = venster_stand()
    # Een kenmerk in het adres, dat de pagina in de venstertitel zet. Daarmee vindt de schil het
    # juiste venster terug, ook als er twee openstaan of de browser al draaide.
    kenmerk = venster.token()
    adres = "%s?%s=%s" % (adres, venster.TOKEN_SLEUTEL, kenmerk)
    for exe in _browser_kandidaten():
        try:
            subprocess.Popen([exe, "--app=%s" % adres] + venster_vlaggen(), close_fds=True)
        except OSError:
            continue
        threading.Thread(target=_pas_venster_toe,
                         args=(stand, rust, positie, kenmerk), daemon=True).start()
        return True
    return webbrowser.open(adres)


def _start():
    # De cursusjaren meteen keuren: een jaar waarvoor geen module bestaat hoort bij het starten te
    # vallen en niet pas bij de eerste vraag van het scherm (T48).
    try:
        _profiel()
    except kern_invoer.InvoerFout as e:
        raise SystemExit(str(e))
    # Een tweede start naast een draaiende schil: geen tweede server, maar wel een venster. Een
    # browser haalt een bestaand tabblad niet naar voren, en in app-modus is er geen tabblad om naar
    # terug te gaan: wie het venster dichtklikt, heeft zonder deze regel geen weg terug - en in de
    # stille bundel is er ook geen console om iets uit te leggen. Twee vensters op één schil is
    # ongevaarlijk: er blijft één server, en die is de enige die schrijft. Is de vaste poort door
    # iets anders bezet, dan zoekt `_maak_server` een vrije.
    expliciet = len(sys.argv) > 1 and sys.argv[1].isdigit()
    if not expliciet and _draait_al(POORT):
        bestaand = "http://%s:%d/" % (HOST, POORT)
        if paden.GEBUNDELD and "--geen-browser" not in sys.argv[1:] and _open_venster(bestaand):
            return
        melding = ("Astrologie Studio draait al.\n\nHet venster kon niet geopend worden; ga naar\n"
                   + bestaand)
        if STIL:
            _meld(melding)
        else:
            _kader("Let op - het programma draait al",
                   ["Het venster kon niet geopend worden.",
                    "Ga met je browser naar " + bestaand])
        return
    server, poort = _maak_server()
    adres = "http://%s:%d/" % (HOST, poort)
    if STIL:
        # Geen console (en dus geen kader): één regel naar fouten.log, meer heeft niemand nodig.
        print("Astrologie Studio %s gestart op %s (horoscopen: %s)"
              % (VERSIE, adres, paden.standaardmap()))
    else:
        _kader("Astrologie Studio - %s - versie %s" % (_profiel_titel(), VERSIE),
               ["Dit venster hoort bij Astrologie Studio. Je hoeft hier niets",
                "te doen. Laat het openstaan zolang je met het programma werkt.",
                "",
                "Sluiten kan met het kruisje van dit venster of via",
                "Bestand > Afsluiten in het programma. Beide manieren werken."],
               breedte=64)
        # Ontwikkelaarsinformatie staat buiten het kader en in kleine letters: bruikbaar voor wie
        # meekijkt, onopvallend voor wie het programma alleen gebruikt. Waar de horoscopen staan,
        # staat na afloop in het afsluitblok - daar is het nuttiger, en zo staat het er één keer.
        print("  adres        %s" % adres, flush=True)
        print("  programma    %s" % paden.bron(""), flush=True)
        # De venstermaat is een meetwaarde voor onszelf en staat niet op het scherm: de schil
        # onthoudt hem in `venster.json`, daar is hij te controleren.
        _venstertitel("Astrologie Studio %s - %s" % (VERSIE, _profiel_titel()))
    # In een bundel opent de schil zelf de browser; in ontwikkeling niet, want daar kijk je vanaf
    # een andere machine. `--geen-browser` houdt dat tegen.
    if paden.GEBUNDELD and "--geen-browser" not in sys.argv[1:]:
        threading.Timer(0.8, _open_venster, args=(adres,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        # Ctrl+C is in een consolevenster een gewone manier om te stoppen; dan hoort er ook een
        # afsluitblok te staan in plaats van een kale prompt.
        if not STIL:
            _kader("Astrologie Studio is afgesloten",
                   ["Je hebt het programma met Ctrl+C gestopt.",
                    "",
                    "Locatie:",
                    paden.standaardmap()], breedte=64)
    finally:
        server.server_close()
    # Het venster sluit zichzelf, maar niet zo snel dat de laatste mededeling weg is voor je hem leest.
    # Geen toets: een afsluiting hoort geen taak te zijn, en een wachtend programma kan
    # blijven hangen als er niets op de invoer komt. Alleen in een echt consolevenster, dus niet in een
    # pijp, een logbestand of de stille bundel.
    #
    # Deze staart **telt hardop af**, in de onderste regel van het blok dat net
    # geprint is: "Dit venster sluit vanzelf over 4 ... 0 seconden", en bij nul gaat het venster dicht.
    # Dat is ontwerp: de wachttijd is er toch, en zo is te zien dat het programma bezig is met
    # stoppen in plaats van te hangen. Na een Ctrl+C telt er niets (dat blok heeft geen aftelregel) en
    # wordt er alleen gewacht.
    if not STIL and _is_console():
        try:
            _tel_af(NASTAREN)
        except (KeyboardInterrupt, OSError):
            pass
    if STIL:
        print("Afgesloten.")


if __name__ == "__main__":
    main()
