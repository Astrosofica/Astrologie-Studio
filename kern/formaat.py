"""Weergave van graden en minuten.

Besluit T22 (uit de print): **minuten worden afgekapt, niet afgerond**. Van de twaalf
gevallen in de eerste ijkprint waar afkappen en afronden verschillen, komen er twaalf uit op
afkappen (Zon 13,9' -> 13', Jupiter 49,5' -> 49', Neptunus 9,9' -> 09').
"""

from __future__ import annotations

import math

TEKENS = ["Ram", "Stier", "Tweelingen", "Kreeft", "Leeuw", "Maagd",
          "Weegschaal", "Schorpioen", "Boogschutter", "Steenbok", "Waterman", "Vissen"]
TEKENS_AFK = ["Ari", "Tau", "Gem", "Can", "Leo", "Vir", "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis"]

# Codepunten in het glyph-font: de echte Unicode-plaatsen, want `astro-sans.ttf` zet de glyphs op
# hun eigen codepunt. Gebouwd met `data/maak-font.py`.
SIGNE_GLYPH = {1: 0x2648, 2: 0x2649, 3: 0x264A, 4: 0x264B, 5: 0x264C, 6: 0x264D,
               7: 0x264E, 8: 0x264F, 9: 0x2650, 10: 0x2651, 11: 0x2652, 12: 0x2653}
PLANEET_GLYPH = {
    "Zon": 0x2609, "Maan": 0x263D, "Mercurius": 0x263F, "Venus": 0x2640, "Mars": 0x2642,
    "Jupiter": 0x2643, "Saturnus": 0x2644, "Uranus": 0x2645, "Neptunus": 0x2646,
    "Pluto": 0x2647, "Noordknoop": 0x260A, "Chiron": 0x26B7, "Dagpars": 0x2297,
}
RETRO_GLYPH = 0x211E
# De acht aspecten van de kern (kern/aspecten.py). Sextiel, sesquiquadraat en quincunx komen uit de
# glyphs van Symbola; staat een aspect
# niet in het font, dan geeft glyf_aspect() een leeg teken — nooit een letter en nooit een KeyError.
ASPECT_GLYPH = {0: 0x260C, 45: 0x2220, 60: 0x26B9, 90: 0x25A1, 120: 0x25B3,
                135: 0x26BC, 150: 0x26BB, 180: 0x260D}


def _norm(lon):
    lon = math.fmod(lon, 360.0)
    return lon + 360.0 if lon < 0 else lon


def afgekapt(lon):
    """(tekenindex 1-12, graad, minuut) met afgekapte minuten."""
    lon = _norm(lon)
    teken = int(lon // 30) + 1
    rest = lon - (teken - 1) * 30
    graad = int(rest)
    minuut = int((rest - graad) * 60)
    if minuut >= 60:          # alleen bij float-randgevallen; afkappen mag nooit 60 geven
        minuut = 59
    return teken, graad, minuut


def teken_graad_min(lon):
    teken, graad, minuut = afgekapt(lon)
    return f"{graad:02d}° {TEKENS_AFK[teken - 1]} {minuut:02d}'"


def teken_naam_graad_min(lon):
    # De graad altijd twee cijfers (04° en niet 4°), gelijk aan `teken_graad_min` en aan de labels
    # in het wiel: één standaard voor elke weergave van een stand.
    teken, graad, minuut = afgekapt(lon)
    return f"{TEKENS[teken - 1]} {graad:02d}°{minuut:02d}'"


def glyf_teken(lon):
    teken, _, _ = afgekapt(lon)
    return chr(SIGNE_GLYPH[teken])


def glyf_planeet(naam):
    return chr(PLANEET_GLYPH.get(naam, 52))


def glyf_aspect(hoek):
    """Het glyph van een aspect; leeg als het font dat teken niet heeft (zie ASPECT_GLYPH)."""
    cp = ASPECT_GLYPH.get(hoek)
    return chr(cp) if cp else ""


def orb_afgekapt(orb):
    """Orb als (graden, minuten) met afgekapte minuten."""
    orb = abs(orb)
    graden = int(orb)
    minuten = int((orb - graden) * 60)
    return graden, minuten


def orb_kort(orb):
    """Orb zoals in de print: '1S45' wordt door de matrixsamenvatting gemaakt; hier '1°45'."""
    g, m = orb_afgekapt(orb)
    return f"{g}°{m:02d}'"
