"""Heerschappen - de tweede aanvulling van jaar 1 (plan §14, besluit T13).

**Altijd het moderne schema.** Dat is de standaardreeks:
Ram Mars, Stier Venus, Tweelingen Mercurius, Kreeft Maan, Leeuw Zon, Maagd Mercurius,
Weegschaal Venus, **Schorpioen Pluto**, Boogschutter Jupiter, Steenbok Saturnus,
**Waterman Uranus**, Vissen Neptunus. (Modern verschilt van klassiek op precies drie tekens:
Schorpioen, Waterman en Vissen - daar heeft het klassieke schema Mars, Saturnus en Jupiter.)

Er is geen schakelaar voor klassiek: dat is een vakinhoudelijke keuze en die is gemaakt.
Twee dingen levert dit bestand: het schema zelf, en per huis de heerser van het teken op de
cusp met de plek waar die heerser staat (de klassieke "heersers per huis").
"""

from __future__ import annotations

from . import elementen as _elementen

MODERN = {
    "Ram": "Mars", "Stier": "Venus", "Tweelingen": "Mercurius", "Kreeft": "Maan",
    "Leeuw": "Zon", "Maagd": "Mercurius", "Weegschaal": "Venus", "Schorpioen": "Pluto",
    "Boogschutter": "Jupiter", "Steenbok": "Saturnus", "Waterman": "Uranus",
    "Vissen": "Neptunus",
}

TEKENS = tuple(MODERN)


def schema():
    """Het moderne schema als lijst, in de volgorde van de dierenriem."""
    return [(t, MODERN[t]) for t in TEKENS]


def per_lichaam(kaart, lichamen=_elementen.LICHAMEN):
    """Per lichaam het teken waarin het staat en de heerser van dat teken."""
    punten = {p["naam"]: p for p in kaart["punten"]}
    uit = []
    for naam in _elementen.ORDE:
        if naam not in lichamen or naam not in punten:
            continue
        p = punten[naam]
        uit.append({"naam": naam, "teken": p["positie"]["teken"],
                    "positie": p["positie"]["label"], "heerser": MODERN[p["positie"]["teken"]]})
    return uit


def per_huis(kaart):
    """Per huis de heerser van het teken op de cusp, met de plek waar die heerser staat.

    `heerser_huis` is het huis waarin de heersende planeet zelf valt; dat is de verbinding
    waar de duiding op steunt (heerser van 7 in 10, enzovoort).
    """
    punten = {p["naam"]: p for p in kaart["punten"]}
    uit = []
    for h in kaart["huizen"]:
        teken = h["positie"]["teken"]
        heerser = MODERN[teken]
        p = punten.get(heerser)
        uit.append({
            "huis": h["nr"],
            "cusp": h["positie"]["label"],
            "teken": teken,
            "heerser": heerser,
            "heerser_huis": (p["huis"] if p else None),
            "heerser_positie": (p["positie"]["label"] if p else None),
        })
    return uit
