"""De instellingen van het programma: de huidige locatie.

Eén bestand naast de kaarten (`~/astrologie-kaarten/settings.json`), zodat één map kopiëren de
hele back-up is. Het pad is **één functie met een omgevingsvariabele erover**
(`ASTRO_INSTELLINGEN`), net als het efemeridenpad: het einddoel is een app voor Windows en daar
hoort dit bestand in de gebruikersmap (`%APPDATA%`).

Vastgelegd wordt alles wat aan de huidige locatie vastligt: de plaatsnaam, het etiket dat de
keuzelijst toont, de breedte, de lengte en de tijdzone - alle vaste waarden die bij die locatie
horen, zodat het formulier ze niet opnieuw hoeft te vragen.

**Geen stille terugval.** Een ontbrekend bestand is `None` - dan vraagt de pagina om de locatie in
te stellen. Een bestand dat niet te lezen is of velden mist is een fout met een boodschap in gewone
taal (een `InvoerFout`, en de schil antwoordt met 400): nooit een gok en nooit een half ingevulde
locatie, net als bij de efemeriden en de tijdzone.
"""

from __future__ import annotations

import datetime
import json
import os

from . import invoer as kern_invoer
from . import opslag

VERSIE = "instellingen-0.2"
BESTAND = "settings.json"
SLEUTELS = ("naam", "etiket", "lat", "lon", "tijdzone_id")

# De cursusjaren die aan staan (besluit T48). Jaar 1 is **geen module maar het fundament**:
# het staat altijd aan en is niet uit te zetten, dus het staat er altijd in - ook als het bestand het
# niet noemt, want een ouder bestand kent het veld niet. Welk jaar er werkelijk bestaat weet de schil
# (die kent de modulebestanden); hier wordt alleen de vorm gekeurd, zodat een onbekend jaar niet stil
# verdwijnt maar bij de schil een leesbare fout oplevert.
JAAR_BASIS = 1
MODULES_SLEUTEL = "modules"


def bestandspad(pad=None):
    """Het instellingenbestand: naast de kaarten, tenzij de omgeving of de vraag iets anders zegt."""
    if pad:
        return os.path.expanduser(str(pad))
    uit_omgeving = os.environ.get("ASTRO_INSTELLINGEN")
    if uit_omgeving:
        return os.path.expanduser(uit_omgeving)
    return os.path.join(opslag.kaartmap(), BESTAND)


def lees(pad=None):
    """De instellingen als dict, of `None` als ze nog niet ingesteld zijn.

    Een bestand dat niet bestaat is geen fout (dan is er nog niets ingesteld); een bestand dat niet
    te lezen is of velden mist wel.
    """
    p = bestandspad(pad)
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            inhoud = json.load(f)
    except Exception as e:
        raise kern_invoer.InvoerFout(
            [f"Het instellingenbestand '{p}' is niet te lezen ({e}). "
             f"Haal het weg of stel de locatie opnieuw in."])
    if not isinstance(inhoud, dict):
        raise kern_invoer.InvoerFout(
            [f"Het instellingenbestand '{p}' bevat geen instellingen."])
    ontbreekt = [sleutel for sleutel in SLEUTELS if sleutel not in inhoud]
    if ontbreekt:
        raise kern_invoer.InvoerFout(
            [f"Het instellingenbestand '{p}' mist: {', '.join(ontbreekt)}. "
             f"Stel de locatie opnieuw in."])
    return inhoud


def modules(inhoud=None, pad=None):
    """De cursusjaren die aan staan, als gesorteerde lijst met jaar 1 er altijd in.

    Zonder bestand of zonder het veld is het antwoord `[1]`: dat is de uitgegeven versie, waarin jaar 2
    nog niet bestond. Een bestand dat wél jaren noemt levert die jaren op, met jaar 1 ervoor - ook als
    iemand het er zelf uit heeft gehaald, want jaar 1 kan niet uit.
    """
    bron = inhoud if inhoud is not None else lees(pad)
    if not isinstance(bron, dict):
        return [JAAR_BASIS]
    gevraagd = bron.get(MODULES_SLEUTEL)
    if gevraagd is None:
        return [JAAR_BASIS]
    if not isinstance(gevraagd, list):
        raise kern_invoer.InvoerFout(
            ["Het veld 'modules' in het instellingenbestand hoort een lijst met cursusjaren te zijn."])
    jaren = []
    for jaar in gevraagd:
        # `True` is in Python een getal (1); een vlag op deze plek is een vergissing, geen jaar.
        if isinstance(jaar, bool) or not isinstance(jaar, int) or jaar < 1:
            raise kern_invoer.InvoerFout(
                [f"'{jaar}' in het veld 'modules' is geen cursusjaar."])
        if jaar not in jaren:
            jaren.append(jaar)
    if JAAR_BASIS not in jaren:
        jaren.insert(0, JAAR_BASIS)
    return sorted(jaren)


def bewaar(waarden, pad=None, modules_=None):
    """De locatie lezen en keuren (dezelfde lezer als het formulier) en wegschrijven.

    Geeft `{bestand, instellingen, nieuw, waarschuwingen}`: `nieuw` is waar als er nog geen
    instellingenbestand stond. Een onbekende tijdzone is een waarschuwing en geen fout - de lezer
    valt dan stil terug op LMT en dat hoort de pagina te melden.
    """
    # Eerst kijken dát het een object met velden is: zonder deze regel gaf een lijst of een tekst een
    # AttributeError (een 500 in de schil) in plaats van een regel in gewone taal. Gevonden door
    # de ijking, geval "geen lijst met velden".
    if not isinstance(waarden, dict):
        raise kern_invoer.InvoerFout(
            ["De instellingen horen als één object met velden te worden aangeboden "
             "(plaats, etiket, breedte, lengte en tijdzone)."])
    # Een `settings.json` met een `email`-sleutel blijft leesbaar; die sleutel wordt niet bewaard,
    # want OpenStreetMap gaat via de eigen proxy, die met de gegevens van de beheerder vraagt.
    schoon = kern_invoer.lees_plaats(waarden)
    p = bestandspad(pad)
    # De aangevinkte cursusjaren horen bij hetzelfde bestand. Zonder deze regel zou het opslaan van de
    # locatie ze wissen, want hieronder wordt het bestand opnieuw samengesteld.
    if modules_ is None:
        try:
            modules_ = modules(pad=pad)
        except kern_invoer.InvoerFout:
            modules_ = [JAAR_BASIS]      # een onleesbaar bestand wordt hierna toch overschreven
    map_ = os.path.dirname(p)
    if map_:
        os.makedirs(map_, exist_ok=True)
    nieuw = not os.path.exists(p)
    inhoud = {"versie": VERSIE,
              "bijgewerkt": datetime.datetime.now().replace(microsecond=0).isoformat(),
              MODULES_SLEUTEL: sorted(set(modules_) | {JAAR_BASIS}),
              **{sleutel: schoon[sleutel] for sleutel in SLEUTELS}}
    with open(p, "w", encoding="utf-8") as f:
        json.dump(inhoud, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return {"bestand": p, "instellingen": inhoud, "nieuw": nieuw,
            "waarschuwingen": schoon["waarschuwingen"]}
