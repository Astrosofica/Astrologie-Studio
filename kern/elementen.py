"""Element- en kruisverdeling - de eerste aanvulling van jaar 1 (plan §14, besluit T13).

De vorm komt van de afdruk van een commercieel programma (blok rechtsonder): per
groep staan de glyphs van de **lichamen**, en de Ascendant en de MC staan in hun eigen groep.
Er wordt niets geteld en er staan geen tekenglyphs; de lichamen zelf zijn de verdeling.

Wie er meetellen is een vakinhoudelijke keuze: hier de tien lichamen Zon tot en met Pluto,
zoals in de afdruk. De Noordknoop, de dagpars en Cheiron tellen niet mee (het zijn geen
lichamen met een teken in de zin van de verdeling); dat is één regel onderaan dit bestand.
"""

from __future__ import annotations

LICHAMEN = ("Zon", "Maan", "Mercurius", "Venus", "Mars",
            "Jupiter", "Saturnus", "Uranus", "Neptunus", "Pluto")

# De volgorde waarin de afdruk de lichamen binnen een groep zet: naar omloopsnelheid,
# van de Maan naar Pluto (nagegaan op de Fire- en Cardinal-regel van die afdruk).
ORDE = ("Maan", "Mercurius", "Venus", "Zon", "Mars",
        "Jupiter", "Saturnus", "Uranus", "Neptunus", "Pluto")

ELEMENT = {
    "Ram": "Vuur", "Leeuw": "Vuur", "Boogschutter": "Vuur",
    "Stier": "Aarde", "Maagd": "Aarde", "Steenbok": "Aarde",
    "Tweelingen": "Lucht", "Weegschaal": "Lucht", "Waterman": "Lucht",
    "Kreeft": "Water", "Schorpioen": "Water", "Vissen": "Water",
}

KRUIS = {
    "Ram": "Cardinal", "Kreeft": "Cardinal", "Weegschaal": "Cardinal", "Steenbok": "Cardinal",
    "Stier": "Fixed", "Leeuw": "Fixed", "Schorpioen": "Fixed", "Waterman": "Fixed",
    "Tweelingen": "Mutable", "Maagd": "Mutable", "Boogschutter": "Mutable", "Vissen": "Mutable",
}

ELEMENTEN = ("Vuur", "Aarde", "Lucht", "Water")
KRUISEN = ("Cardinal", "Fixed", "Mutable")

HOEKEN = (("Ascendant", "Asc"), ("MC", "MC"))


def verdeling(kaart, lichamen=LICHAMEN, met_hoeken=True):
    """De lichamen per element en per kruis, in de volgorde van de afdruk (naar snelheid).

    Uitkomst: {"elementen": [(naam, {"lichamen": [...], "hoeken": [...]}), ...],
               "kruisen":   [(naam, {"lichamen": [...], "hoeken": [...]}), ...]}
    """
    punten = {p["naam"]: p for p in kaart["punten"]}

    elementen = {k: {"lichamen": [], "hoeken": []} for k in ELEMENTEN}
    kruisen = {k: {"lichamen": [], "hoeken": []} for k in KRUISEN}

    for naam in ORDE:
        if naam not in lichamen or naam not in punten:
            continue
        p = punten[naam]
        teken = p["positie"]["teken"]
        elementen[ELEMENT[teken]]["lichamen"].append(naam)
        kruisen[KRUIS[teken]]["lichamen"].append(naam)

    if met_hoeken:
        for naam, kort in HOEKEN:
            p = punten.get(naam)
            if not p:
                continue
            teken = p["positie"]["teken"]
            elementen[ELEMENT[teken]]["hoeken"].append(kort)
            kruisen[KRUIS[teken]]["hoeken"].append(kort)

    return {"elementen": list(elementen.items()), "kruisen": list(kruisen.items())}


def tel(verd):
    """Per groep het aantal lichamen - voor een samenvatting in één regel."""
    return {"elementen": {k: len(v["lichamen"]) for k, v in verd["elementen"]},
            "kruisen": {k: len(v["lichamen"]) for k, v in verd["kruisen"]}}
