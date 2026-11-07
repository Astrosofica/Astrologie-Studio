"""OpenStreetMap als aanvulling op de plaatsenlijst — via de eigen proxy.

De lijst van het invulscherm komt uit GeoNames en mist de kleine dingen: buurtschappen,
gehuchten, een straat. Voor die gevallen vraagt de schil het aan OpenStreetMap. Dat is de enige
plek in het programma die naar buiten gaat, en alleen als de gebruiker er zelf om vraagt.

**Via de eigen proxy, niet rechtstreeks.** De vraag gaat naar
`https://studio.astrosofica.nl/osm/` (Apache + PHP op t640). Die proxy legt de vraag met de
gegevens van de beheerder bij Nominatim neer, en dat is de reden: de **User-Agent met een bereikbaar contactadres**
is een eis van Nominatim (https://operations.osmfoundation.org/policies/nominatim/) en dat contact
hoort bij de beheerder, niet bij de cursist. Het e-mailveld bij Instellingen is daarmee vervallen.

Wat hier blijft:

  - **Hoogstens één verzoek per seconde** in dit proces (`MIN_TIJD`). De proxy doet hetzelfde over
    álle gebruikers heen met een `flock`; dit is de tweede grendel, geen vervanging.
  - **Resultaten bewaren** in `staat/osm-cache.json` (hoogstens `MAX_CACHE` vragen, de oudste eruit),
    zodat dezelfde vraag niet nog eens de deur uit gaat. De proxy cachet ook, 30 dagen.
  - **De dienst-URL staat in een bestand, niet in de code**: `data/osm-dienst.json`, met
    `ASTRO_OSM_PROXY` als omgevingsvariabele erover heen. Zo vraagt een andere dienst geen nieuwe
    bundel — dat eist de policy van Nominatim ook.
  - **Geen sleutel.** Een sleutel in de bundel is geen slot: iedereen die de bundel uitpakt kan hem
    lezen, en hij zou met de hand gekopieerd worden naar elke nieuwe versie. Wie de app is, staat
    nu in de header `X-Astro-Versie`; wat de dienst beschermt is een grens per IP-adres. Een oude
    sleutel in `data/osm-dienst.json` wordt niet meer gelezen en stuurt niets mee.

De gegevens zijn van OpenStreetMap (ODbL); de pagina noemt de bron bij de keuzelijst.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from kern import paden, plaatsen, versie
from kern.invoer import InvoerFout

# De dienstgegevens worden meegeleverd (alleen lezen); de cache is van de gebruiker en staat
# daarom in de gebruikersmap: in een bundel is de programmamap een tijdelijke uitleesmap.
CACHE = paden.staat("osm-cache.json")
DIENST_BESTAND = paden.bron("data", "osm-dienst.json")
MIN_TIJD = 1.1          # seconden tussen twee verzoeken; de policy zegt 1 per seconde
HERKANS_WACHT = 1.5     # seconden wachten voor de ene herkansing bij een 429 van de proxy
MAX_CACHE = 200
# Ophogen zodra de vorm van een treffer verandert: de cache bewaart het *bewerkte* antwoord, dus een
# regel met een fout label ("80" in plaats van de straat) blijft anders terugkomen.
CACHE_VERSIE = 3
_laatst = [0.0]         # tijdstip van het laatste verzoek, over alle vragen heen


def _dienst():
    """De dienst-URL, uit `data/osm-dienst.json`; `ASTRO_OSM_PROXY` gaat erover heen.

    Er is geen adres in de code: één plek waar het vandaan komt, anders zou een andere dienst op
    twee plekken veranderd moeten worden en vergeet je er één. Staat er niets (bestand weg,
    onleesbaar, geen `dienst`), dan komt er een lege regel terug en zegt `zoek()` wat er mist.
    Een `sleutel` in dat bestand wordt niet gelezen - de dienst vraagt er niet meer naar.
    """
    url = ""
    try:
        with open(DIENST_BESTAND, encoding="utf-8") as f:
            inhoud = json.load(f)
        if isinstance(inhoud, dict):
            url = str(inhoud.get("dienst") or "").strip()
    except Exception:
        pass
    from_omgeving = (os.environ.get("ASTRO_OSM_PROXY") or "").strip()
    return from_omgeving or url


def _cache_lees():
    try:
        with open(CACHE, encoding="utf-8") as f:
            inhoud = json.load(f)
        return inhoud if isinstance(inhoud, dict) else {}
    except Exception:
        return {}


def _cache_schrijf(cache):
    try:
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        with open(CACHE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=1)
    except Exception:
        pass            # een mislukte cache mag het zoeken niet blokkeren


def _maak(ruw):
    """Eén Nominatim-treffer -> de vorm die de keuzelijst gebruikt (zoals `plaatsen.zoek`).

    De `name` van een adres is bij OpenStreetMap leeg: een huis, een straat en een gebouw hebben geen
    naam, alleen een `address`-blok. Wie dan de eerste regel van `display_name` pakt, ziet "80" staan
    terwijl de coördinaten wél kloppen. Daarom wordt de naam hier opgebouwd uit de delen: straat +
    huisnummer, anders de
    straat, anders het dorp, en pas als laatste de eerste regel van `display_name` — en die laatste
    alleen als het geen kaal nummer is.
    """
    adres = ruw.get("address") or {}
    straat = (adres.get("road") or adres.get("pedestrian") or adres.get("footway") or "").strip()
    nummer = (adres.get("house_number") or "").strip()
    stad = (adres.get("city") or adres.get("town") or adres.get("village")
            or adres.get("hamlet") or adres.get("suburb") or "").strip()
    gemeente = (adres.get("municipality") or adres.get("county") or "").strip()
    streek = (adres.get("state") or adres.get("province") or adres.get("region") or "").strip()
    land = str(adres.get("country_code") or "").upper()

    naam = (ruw.get("name") or "").strip()
    if not naam and straat and nummer:
        naam = f"{straat} {nummer}"
    if not naam and straat:
        naam = straat
    if not naam:
        naam = stad
    if not naam:
        eerste = (ruw.get("display_name") or "").split(",")[0].strip()
        naam = "" if eerste.isdigit() else eerste        # een kaal huisnummer is geen naam
    if not naam:
        return None
    if naam[:1].islower():                               # OSM schrijft straten klein
        naam = naam[:1].upper() + naam[1:]
    try:
        lat = float(ruw["lat"])
        lon = float(ruw["lon"])
    except (KeyError, TypeError, ValueError):
        return None

    # De tijdzone bij de coördinaten: OpenStreetMap geeft er geen, de plaatsenlijst
    # wel. Eén keer opzoeken, want zowel het veld als de meldregel gebruikt de uitkomst.
    _zone = plaatsen.zone_voor(lat, lon, land)

    # Dezelfde regel als het label van de eigen lijst: het dorp eerst (dat is bij een adres de plek
    # die je herkent), dan de gemeente als die anders heet, dan de streek en het land.
    delen = []
    if stad and stad.lower() != naam.lower():
        delen.append(stad)
    if gemeente and gemeente.lower() not in (naam.lower(), stad.lower()):
        delen.append("gem. " + gemeente)
    if streek:
        delen.append(streek)
    if land:
        delen.append(land)
    return {
        "naam": naam,
        "lat": lat,
        "lon": lon,
        "land": land,
        # OpenStreetMap geeft geen IANA-tijdzone; de plaatsenlijst wel. We zoeken
        # hem op bij de coördinaten (`plaatsen.zone_voor`), met het land uit het adres erbij: in
        # landen met meer dan één zone geeft dat de zone van de eigen streek in plaats van niets.
        "zone": _zone.get("zone", ""),
        # Waar die zone vandaan komt, voor de meldregel: "via Novosibirsk (2 km)" of "het land".
        "zone_uit": ("" if not _zone else
                     (f"{_zone['plaats']} ({_zone['km']:.0f} km)" if _zone["bron"] != "land"
                      else "het land " + _zone["land"])),
        "streek": streek,
        "gemeente": gemeente or stad,
        "onder": ", ".join(delen),
        "etiket": naam,
        "eigen": False,
        "bron": "OpenStreetMap",
        "osm": f"{ruw.get('osm_type')}/{ruw.get('osm_id')}",
    }


def _foutregel(e):
    """De regel die de keuzelijst toont als de proxy weigert of stuk is.

    De proxy antwoordt met `{"fout": "..."}` in gewone taal; die tekst is bruikbaar, dus die gaat
    mee. De codes die de gebruiker zelf kan tegenkomen krijgen hun eigen regel, want "fout 429" zegt
    een cursist niets.
    """
    tekst = ""
    try:
        body = json.loads((e.read() or b"{}").decode("utf-8", "replace"))
        tekst = str((body or {}).get("fout") or "").strip()
    except Exception:
        tekst = ""
    if e.code == 403:
        return ("De OSM-proxy weigert het verzoek (403). Zoek de plaats in de eigen lijst "
                "of vul de coördinaten met de hand in.")
    if e.code == 429:
        return ("OpenStreetMap houdt ons even tegen" + (f" ({tekst})" if tekst else "")
                + ". Probeer het over een paar seconden opnieuw, of vul de coördinaten zelf in.")
    if e.code == 400:
        return tekst or "De zoektekst is niet bruikbaar."
    return ("De OSM-proxy antwoordt met fout " + str(e.code) + (f" — {tekst}" if tekst else "")
            + ". De eigen lijst werkt gewoon; je kunt de coördinaten ook met de hand invullen.")


def zoek(tekst, limiet=5):
    """Plaatsen zoeken in OpenStreetMap (via de proxy). Geeft een lijst in de vorm van `plaatsen.zoek`.

    Er is geen contactadres en geen sleutel van de gebruiker nodig: de proxy vraagt met de gegevens
    van de beheerder, en hij ziet aan de header `X-Astro-Versie` welke versie er vraagt.
    """
    tekst = (tekst or "").strip()
    if len(tekst) < 3:
        return []

    voorvoegsel = f"v{CACHE_VERSIE}:"
    cache = {k: v for k, v in _cache_lees().items() if k.startswith(voorvoegsel)}
    sleutel_cache = voorvoegsel + " ".join(tekst.lower().split())
    if sleutel_cache in cache:
        return cache[sleutel_cache]

    dienst = _dienst()
    if not dienst:
        raise InvoerFout(["De dienst voor OpenStreetMap is niet ingesteld (data/osm-dienst.json). "
                          "De eigen lijst werkt gewoon; je kunt de coördinaten ook met de hand "
                          "invullen."])

    wacht = MIN_TIJD - (time.time() - _laatst[0])
    if wacht > 0:
        time.sleep(wacht)
    vraag = urllib.parse.urlencode({"q": tekst, "limit": limiet, "taal": "nl"})
    verzoek = urllib.request.Request(
        dienst + ("&" if "?" in dienst else "?") + vraag,
        headers={"X-Astro-Versie": versie.VERSIE,
                 "User-Agent": f"astrologie-studio/{versie.VERSIE}",
                 "Accept": "application/json"})
    _laatst[0] = time.time()
    # Eén herkansing bij een 429 van de proxy. De proxy houdt één verzoek per seconde aan over álle
    # gebruikers (de policy van Nominatim), dus op een lesavond botst de klas en krijgt de laatste
    # een 429. Zonder deze herkansing ziet een cursist een foutregel voor iets wat vanzelf overgaat en
    # moet hij zelf nog eens klikken; met de herkansing valt de botsing weg. Alleen bij 429: bij een
    # netwerkfout zou een tweede poging de wachttijd verdubbelen.
    ruw = None
    for poging in (1, 2):
        _laatst[0] = time.time()
        try:
            with urllib.request.urlopen(verzoek, timeout=20) as antwoord:
                ruw = json.load(antwoord)
            break
        except urllib.error.HTTPError as e:
            if e.code == 429 and poging == 1:
                time.sleep(HERKANS_WACHT)
                continue
            raise InvoerFout([_foutregel(e)])
        except Exception as e:
            raise InvoerFout([f"De OSM-proxy is niet bereikbaar ({e}). De eigen lijst werkt gewoon; "
                              "je kunt de coördinaten ook met de hand invullen."])

    uit = [p for p in (_maak(r) for r in (ruw or [])) if p]
    cache[sleutel_cache] = uit
    if len(cache) > MAX_CACHE:
        for oud in list(cache)[:len(cache) - MAX_CACHE]:
            cache.pop(oud, None)
    _cache_schrijf(cache)
    return uit
