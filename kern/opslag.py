"""Kaartopslag: één bestand per kaart in een gewone map plus één indexbestand (besluit T21).

Geen databank, geen accounts. De map is met de hand te lezen en te kopiëren; een back-up is
de map kopiëren.

De index (`index.json`) is de kaartenlijst van de pagina: per kaart de bestandsnaam, de naam, het
moment, de plaats, de tijdzone en het huizenstelsel. Daar staat het huizenstelsel als **letter**
(`K`), want dat is wat `kern/kaart.py` verwacht als een bewaarde kaart opnieuw gerekend wordt; de
naam (`Koch`) staat in het kaartbestand zelf. De letter is het contract; de naam zou bij het
opnieuw rekenen een 500 geven.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import unicodedata
from itertools import count

from .efemeride import HUISSTELSELS
from .invoer import InvoerFout
from . import paden

# Waar de kaarten staan: `paden.standaardmap()` (de gebruikersmap, of `ASTRO_HOROSCOPENMAP`). Zo staat
# de schrijfmap los van de map waarin het programma zelf staat.
STANDAARD_MAP = paden.standaardmap()
INDEX = "index.json"

# Twee draden (twee tabbladen, of bewaren terwijl de klok tikt) kunnen elkaars lees-wijzig-schrijf-
# cyclus op `index.json` doorsnijden en elkaars regel overschrijven. Een `RLock`, want `bewaar` houdt
# hem vast en `herbouw`/`_index_bijwerken` worden van binnenuit aangeroepen.
_SLOT = threading.RLock()

# Een eigen nummer per schrijfactie: twee draden in hetzelfde proces hebben hetzelfde pid, en met
# alleen het pid zouden ze elkaar op hetzelfde tijdelijke bestand onder de voet lopen.
_TELLER = count(1)

# De vorm van een datum in een bestandsnaam. Zie `bestandsnaam`.
_DATUM = re.compile(r"\d{4}-\d{2}-\d{2}")


def _schrijf_json(pad, inhoud):
    """Schrijf een JSON-bestand in één beweging: eerst een tijdelijk bestand, dan omwisselen.

    Waarom: `open(pad, "w")` maakt het bestand eerst leeg. Valt de stroom weg of wordt
    het venster midden in die twee regels gesloten, dan staat er een half bestand - en een halve
    index leest als "geen horoscopen", waarna de volgende Bewaren die lege lijst terugschrijft met
    één regel erin. `os.replace` is op Linux én Windows één beweging: het oude bestand blijft staan
    tot het nieuwe er is. Het tijdelijke bestand staat naast het doel, want `os.replace` werkt niet
    over een schijf- of partitiegrens heen.
    """
    tijdelijk = "%s.%d-%d.tmp" % (pad, os.getpid(), next(_TELLER))
    try:
        with open(tijdelijk, "w", encoding="utf-8") as f:
            json.dump(inhoud, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tijdelijk, pad)
    except Exception:
        try:
            os.remove(tijdelijk)
        except OSError:
            pass
        raise


def _slug(naam):
    s = unicodedata.normalize("NFKD", naam).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
    return s or "kaart"


def veilige_naam(bestand):
    """Alleen een kale bestandsnaam uit de eigen map: geen pad, geen `..`, geen index."""
    tekst = str(bestand if bestand is not None else "").strip()
    naam = os.path.basename(tekst)
    if not naam or naam != tekst or naam in (INDEX, ".", "..") or not naam.endswith(".json"):
        raise InvoerFout([f"'{bestand}' is geen horoscoopbestand uit de map met horoscopen."])
    return naam


def kaartmap(map_=None):
    m = os.path.expanduser(map_ or STANDAARD_MAP)
    os.makedirs(m, exist_ok=True)
    return m


def bestandsnaam(kaart):
    """De leesbare bestandsnaam van een kaart: datum en naam, en verder niets.

    **Hier wordt client-data een bestandsnaam**, dus hier wordt hij gekeurd. De eigen
    schil stuurt altijd een datum die de kern zelf gemaakt heeft (`jaar-maand-dag`, zie
    `kern/kaart.py`) en komt hier nooit tegen een fout aan; een handgemaakt verzoek met
    `datum: "../staat/x"` zou zonder deze regel buiten de kaartenmap schrijven. Vandaar twee grendels:
    de vorm van de datum, en de uitkomst door `veilige_naam` - dezelfde controle die bij lezen en
    verwijderen al op de deur staat.
    """
    meta = kaart["meta"]
    datum = str(meta.get("datum") or "").strip()
    if not _DATUM.fullmatch(datum):
        raise InvoerFout([f"De datum '{datum}' is geen datum van de vorm 1963-07-19."])
    return veilige_naam(f"{datum}-{_slug(meta.get('naam'))}.json")


# --- het id van een kaart ----------------------------------------------------------------------
# het anker van de kaart en niet de bestandsnaam, want die volgt uit datum en naam en verandert dus
# zodra de gebruiker de kaart hernoemt (of botst als twee kaarten dezelfde naam en datum hebben).
# Het id staat in de index en, bij het wegschrijven, ook in `meta` van het kaartbestand zelf: de
# index is de waarheid, het bestand is de leesbare kopie. Een kaart van vóór die datum krijgt er
# één bij het lezen van de index, uit de mtime van het bestand - eerlijk: "sinds dan staat hij er".

def _nu_ms():
    return int(time.time() * 1000)


def _als_int(waarde):
    try:
        return int(waarde)
    except (TypeError, ValueError):
        return None


def _id_rij(regel):
    return _als_int((regel or {}).get("id"))


def _vrij_id(index):
    cid = _nu_ms()
    gezet = {_id_rij(r) for r in index}
    while cid in gezet:
        cid += 1
    return cid


def _migreer(m, index):
    """Id's toekennen waar ze ontbreken en dubbele id's uit elkaar trekken. Geeft (index, gewijzigd).

    Twee kaarten met hetzelfde id komt van een gekopieerd bestand of een teruggezette back-up; de
    tweede schuift één milliseconde op, zodat "aanpassen" altijd één kaart raakt en niet twee.
    """
    gewijzigd = False
    gezien = set()
    for regel in index:
        cid = _id_rij(regel)
        if cid is None:
            bestand = regel.get("bestand")
            if bestand:
                try:
                    cid = int(os.path.getmtime(os.path.join(m, veilige_naam(bestand))) * 1000)
                except (OSError, InvoerFout):
                    cid = None
            if cid is None:
                cid = _nu_ms()
            gewijzigd = True
        while cid in gezien:
            cid += 1
            gewijzigd = True
        gezien.add(cid)
        if _id_rij(regel) != cid:
            regel["id"] = cid
            gewijzigd = True
    return index, gewijzigd


def _doelnaam(m, kaart, cid, oud):
    """De bestandsnaam voor deze kaart: leesbaar, en nooit stilletjes die van een ándere kaart."""
    basis = bestandsnaam(kaart)
    if oud and oud.get("bestand") == basis:
        return basis                     # dezelfde kaart, dezelfde naam: overschrijven
    if not os.path.exists(os.path.join(m, basis)):
        return basis
    # De naam is al bezet door een andere kaart: een nummer erachter in plaats van overschrijven -
    # de bestandsnaam moet leesbaar blijven.
    return basis[:-5] + "-" + str(cid) + ".json"


def bewaar(kaart, map_=None, vervang=None):
    """Kaart wegschrijven en de index bijwerken. Geeft (pad, nieuw, id).

    `vervang` is het id van de kaart die overschreven wordt (None of onbekend: een nieuwe kaart).
    Verandert de naam, dan verhuist het bestand mee en gaat het oude bestand weg - anders staan er
    twee kaarten van dezelfde horoscoop.

    **Wat er op schijf komt is het recept, niet de taart**: `versie` + `meta` (~2 kB), en dat is
    genoeg om elke kaart weer op te bouwen. De berekening zelf (`punten`, `huizen`, `aspecten`,
    `matrix`, samen 25-34 kB) staat er niet in: bij openen wordt uit `meta` opnieuw gerekend.

    Een oud bestand met een berekening erin blijft gewoon leesbaar: `lees()` geeft terug wat er staat
    en de pagina gebruikt alleen `meta`. Zo'n bestand wordt pas slank bij de eerstvolgende keer
    bewaren - opruimen hoeft dus niet in één keer, en er is geen migratieronde nodig.

    Waarom dit niet alleen kleiner is maar ook beter: een momentopname in het bestand legt feiten vast
    die daarna niet meer waar hoeven te zijn en die niemand ooit bijwerkt. Een melding die daaruit
    komt kan tegen de berekening van nu in gaan (`meta.met_chiron` in het bestand tegen de berekening
    van nu).
    """
    m = kaartmap(map_)
    with _SLOT:
        return _bewaar_in(m, kaart, vervang)


def _bewaar_in(m, kaart, vervang=None):
    """`bewaar`, maar dan in een map die al bestaat en onder het slot."""
    index = _migreer(m, _index_lezen_of_herstellen(m))[0]
    oud = None
    vervang_id = _als_int(vervang)
    if vervang_id is not None:
        for regel in index:
            if _id_rij(regel) == vervang_id:
                oud = regel
                break
    cid = _id_rij(oud) if oud else None
    if cid is None:
        cid = _vrij_id(index)
    kaart.setdefault("meta", {})["id"] = cid
    naam = _doelnaam(m, kaart, cid, oud)
    pad = os.path.join(m, naam)
    nieuw = oud is None
    slank = {"versie": kaart.get("versie", "basis-0.6"), "meta": kaart["meta"]}
    # Het kaartbestand zelf net zo lief in één beweging: een half geschreven kaart is niet meer te
    _schrijf_json(pad, slank)
    if oud and oud.get("bestand") and oud["bestand"] != naam:
        oudpad = os.path.join(m, veilige_naam(oud["bestand"]))
        if os.path.exists(oudpad):
            os.remove(oudpad)
    _index_bijwerken(m, naam, kaart, cid)
    return pad, nieuw, cid


def _sorteersleutel(regel):
    """Naam, dan datum, dan het id - een **volledige** orde.

    Zonder het id is de volgorde van twee kaarten met dezelfde naam en datum willekeurig: bij het
    bijwerken bepaalt de bestaande lijst de volgorde, bij een herbouw de volgorde van `os.listdir`.
    Hetzelfde stel kaarten gaf dan twee verschillende lijsten, en dat is precies wat een herbouw
    niet mag doen.
    """
    return (regel.get("naam", ""), regel.get("datum", ""), _id_rij(regel) or 0)


def _indexregel(meta, bestand, cid=None, bewaard=None):
    """Eén regel van de kaartenlijst, uit de `meta` van een kaart.

    Op één plek, omdat `_index_bijwerken` en `herbouw` dezelfde vorm moeten maken: lopen die twee uit
    elkaar, dan ziet een herbouwde lijst er anders uit dan een bijgewerkte.
    """
    return {
        "id": cid if cid is not None else _als_int(meta.get("id")),
        # `bewaard` is de laatste bewaartijd: de index is een afgeleide en geen contract, en het `id`
        # blijft het anker voor Aanpassen (dat verandert dus niet als je een kaart opnieuw bewaart).
        # Het paneel sorteert
        # hierop: "recente horoscopen" is "laatst bewaard", niet "laatst aangemaakt". Bij een herbouw
        # is de bewaartijd van de schijf (mtime) het beste wat we nog weten.
        "bewaard": _nu_ms() if bewaard is None else bewaard,
        "bestand": bestand,
        "naam": meta["naam"],
        "datum": meta["datum"],
        "tijd": meta["tijd"],
        "plaats": meta.get("plaats", ""),
        "tijdzone_id": meta.get("tijdzone_id", ""),
        "huizenstelsel": meta.get("huizenstelsel", "K"),
        "huizenstelsel_naam": meta.get("huizenstelsel_naam", "Koch"),
        "met_chiron": bool(meta.get("met_chiron")),
    }


def _index_bijwerken(m, naam, kaart, cid=None):
    pad = os.path.join(m, INDEX)
    index = _lees_index(pad) or []
    regel = _indexregel(kaart["meta"], naam, cid)
    index = [r for r in index
             if r.get("bestand") != regel["bestand"] and _id_rij(r) != regel["id"]]
    index.append(regel)
    index.sort(key=_sorteersleutel)
    _schrijf_json(pad, index)
    return pad


def _lees_index(pad):
    """De index lezen. `None` betekent: er staat een bestand en het is niet te lezen.

    Dat onderscheid is het hele punt. Een lege lijst is een geldige stand; een
    onleesbaar bestand is een beschadiging. Wie die twee op één hoop gooit, schrijft bij de volgende
    Bewaren een lege lijst terug met één regel erin - en dan is de kaartenlijst weg terwijl de kaarten
    er nog staan. `_index_lezen_of_herstellen` is de plek die het verschil gebruikt.
    """
    if not os.path.exists(pad):
        return []
    try:
        with open(pad, encoding="utf-8") as f:
            inhoud = json.load(f)
    except Exception:
        return None
    return inhoud if isinstance(inhoud, list) else None


def _parkeer(pad):
    """Een onleesbare index opzij zetten in plaats van hem te overschrijven.

    De nieuwe naam draagt het moment, zodat er niets verloren gaat en je later kunt zien wat er in
    stond. Lukt het opzij zetten niet, dan gaat de herbouw gewoon door: stilvallen is erger dan een
    lelijk bestand laten staan.
    """
    stempel = time.strftime("%Y%m%d-%H%M%S")
    doel, nummer = f"{pad}.kapot-{stempel}", 1
    while os.path.exists(doel):
        nummer += 1
        doel = f"{pad}.kapot-{stempel}-{nummer}"
    try:
        os.replace(pad, doel)
        return doel
    except OSError:
        return None


def _index_lezen_of_herstellen(m):
    """De index lezen; is hij beschadigd, dan wordt hij eerst uit de kaartbestanden herbouwd."""
    pad = os.path.join(m, INDEX)
    index = _lees_index(pad)
    if index is not None:
        return index
    _parkeer(pad)
    herbouw(m)
    index = _lees_index(pad)
    return index if index is not None else []


def herbouw(map_=None):
    """De kaartenlijst opnieuw opbouwen uit de kaartbestanden in de map.

    De index is een **afgeleide**, geen bron: elke kaart is een eigen bestand met
    `versie` + `meta`, en daar is de lijst uit te herstellen. Dat is het vangnet onder de enige plek
    waar dit programma iets kan kwijtraken - raakt `index.json` zoek of beschadigd, dan staan de
    kaarten er nog en is er niets weg.

    Elk `*.json` in de map telt mee, behalve de index zelf. Een bestand zonder `meta` met `naam`,
    `datum` en `tijd` is geen kaart en wordt overgeslagen: `settings.json` kan hier ook staan.

    Twee dingen die een herbouw **niet** terugbrengt, en dat is de eerlijke prijs van een afgeleide:

    - `bewaard` (wanneer de kaart voor het laatst bewaard is) wordt de mtime van het bestand, en de
      lijst sorteert op naam, datum en id - dus de inhoud en de volgorde kloppen, maar "wat laatst
      bewaard is" is na een herbouw een benadering;
    - het `id` van een kaart **zonder `meta.id`** (van voor de id-migratie): die bestanden hebben er geen,
      dus het id komt uit de mtime. Het kan afwijken van het id dat de index ervoor had (de mtime is
      sinds die migratie immers verschoven), en dan maakt "Aanpassen" één keer een nieuwe kaart in
      plaats van de openstaande bij te werken. Bewust niet opgelost door het id in andermans
      kaartbestand te schrijven: een reparatie hoort niet stil aan de kaarten te komen. Een tweede
      herbouw is wel byte voor byte gelijk - dat is gemeten.

    Geeft `{"kaarten": n, "overgeslagen": m, "index": pad}`.
    """
    m = kaartmap(map_)
    with _SLOT:
        rijen, overgeslagen = [], 0
        for naam in sorted(os.listdir(m)):
            if naam == INDEX or not naam.endswith(".json"):
                continue
            bestand = os.path.join(m, naam)
            try:
                with open(bestand, encoding="utf-8") as f:
                    meta = json.load(f)["meta"]
                if not isinstance(meta, dict) or not all(
                        isinstance(meta.get(sleutel), str) and meta.get(sleutel)
                        for sleutel in ("naam", "datum", "tijd")):
                    raise ValueError("geen kaart")
            except Exception:
                overgeslagen += 1
                continue
            rijen.append(_indexregel(meta, naam, bewaard=int(os.path.getmtime(bestand) * 1000)))
        rijen, _ = _migreer(m, rijen)
        rijen.sort(key=_sorteersleutel)
        pad = os.path.join(m, INDEX)
        _schrijf_json(pad, rijen)
        return {"kaarten": len(rijen), "overgeslagen": overgeslagen, "index": pad}


def lees(bestand, map_=None):
    m = kaartmap(map_)
    naam = veilige_naam(bestand)
    pad = os.path.join(m, naam)
    if not os.path.exists(pad):
        raise InvoerFout([f"De horoscoop '{naam}' staat niet in de map met horoscopen ({m})."])
    with open(pad, encoding="utf-8") as f:
        return json.load(f)


def verwijder(bestand, map_=None):
    """Kaartbestand weggooien en de regel uit de index halen. Geeft de bestandsnaam terug."""
    m = kaartmap(map_)
    naam = veilige_naam(bestand)
    pad = os.path.join(m, naam)
    with _SLOT:
        if not os.path.exists(pad):
            raise InvoerFout([f"De horoscoop '{naam}' staat niet in de map met horoscopen ({m})."])
        os.remove(pad)
        index = [r for r in _index_lezen_of_herstellen(m) if r.get("bestand") != naam]
        _schrijf_json(os.path.join(m, INDEX), index)
    return naam


def lijst(map_=None):
    """De kaartenlijst uit de index; regels zonder bestand vallen af.

    Hier zit ook de migratie: een regel zonder id krijgt er één. Dat
    wordt meteen weggeschreven, zodat het id daarna vastligt en niet bij elke keer lezen uit de
    mtime opnieuw wordt afgeleid.
    """
    m = kaartmap(map_)
    with _SLOT:
        index, gewijzigd = _migreer(m, _index_lezen_of_herstellen(m))
        if gewijzigd:
            _schrijf_json(os.path.join(m, INDEX), index)
    return [_recht(regel) for regel in index if regel.get("bestand")]


def _recht(regel):
    """Een indexregel van de oude vorm rechtzetten.

    Daar staat de **naam** van het huizenstelsel ("Koch") in het veld waar de **letter**
    ("K") hoort. De kaart zelf is niet in orde te maken (die is wat hij is), maar de lijst en
    het openen horen altijd hetzelfde te lezen; daarom hier omzetten bij het lezen.
    """
    uit = dict(regel)
    waarde = str(uit.get("huizenstelsel") or "").strip()
    if len(waarde) > 1:
        for letter, naam in HUISSTELSELS.items():
            if naam.lower() == waarde.lower():
                uit["huizenstelsel"] = letter
                break
    uit.setdefault("huizenstelsel_naam",
                   HUISSTELSELS.get(str(uit.get("huizenstelsel") or ""), ""))
    uit.setdefault("met_chiron", False)
    uit.setdefault("plaats", "")
    uit.setdefault("tijdzone_id", "")
    uit["id"] = _id_rij(uit)          # het anker van de kaart; altijd int of None, nooit een string
    return uit
