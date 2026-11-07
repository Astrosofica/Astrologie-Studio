#!/usr/bin/env python3
"""Bouwt het glyph-font van dit programma, en meet de maten opnieuw.

**Waarom een eigen font.** Het font dat erin zat (`symbol.ttf`) komt uit een commercieel astrologiepakket: "© Copyright
2002 Mark Griffin, all rights reserved". Dat mag je niet meeleveren.

**Wat het font wordt.** Eén klein font met drie soorten tekens:
  1. de **34 astrologie-glyphs** op hun echte Unicode-plaatsen (12 tekens, 13 lichamen en
     punten, 8 aspecten en de retrograde-markering) — niet op eigen codeposities zoals het
     oude glyph-font, want dan vraagt elke fontwissel een codewijziging;
  2. de **cijfers, `°` en `'`** — de graden en minuten in de labels;
  3. de **letters en leestekens** van het scherm (basis-Latijn plus Latijn-1), zodat ook het
     formulier en de rest van de pagina hetzelfde font gebruiken.

**Twee bronnen mogen verschillen.** De glyphs en de letters/cijfers komen niet per se uit
hetzelfde font: `--bron` levert de letters en de cijfers, `--glyphs` de astrologie-glyphs.
Dat is de reden om ze te splitsen — **Symbola** (George Douros, publiek domein:
"fonts are free for any use; they may be opened, edited, modified, regenerated, packaged and
redistributed") heeft alle 34 glyphs, met juist de drie aspecten die DejaVu mist (sextiel
U+26B9, sesquiquadraat U+26BC, quincunx U+26BB); de letters met accent zitten daar echter
niet in (58 van de 96 Latijn-1-tekens ontbreken). De glyphs worden bij het inbouwen geschaald
naar de em van het doelfont (`--glyph-schaal` erover heen), want de bronfonts hebben een
verschillende em: Symbola 2048, de meeste tekstfonts 1000.

**Licentie.** Wat eruit komt is een afgeleide van beide bronnen; de licentie van allebei gaat
mee in `LICENTIE-AstroSans.txt`. Bitstream Vera (DejaVu) staat wijzigen en verspreiden toe
zolang het font een eigen naam heeft; de OFL vraagt hetzelfde plus de licentietekst zelf
(`--licentie-bijlage`) en dat een gereserveerde fontnaam niet in de afgeleide terugkomt —
ons font heet Astro Sans, dus dat is geregeld.

Gebruik:
    /usr/bin/python3 data/maak-font.py                        # alles uit de systeem-DejaVu
    /usr/bin/python3 data/maak-font.py --glyphs Symbola.ttf   # glyphs uit Symbola, letters uit DejaVu
    /usr/bin/python3 data/maak-font.py --bron Inter.ttf --gewicht 600 --glyphs Symbola.ttf \\
        --glyph-schaal 0.85 --uit-map /tmp/proef --licentie-bijlage Inter-OFL.txt
    /usr/bin/python3 data/maak-font.py --bron Source_Sans_3.ttf --gewicht 600 \\
        --glyphs StarFisherUni.ttf --glyph-vanaf 2609=263C --glyph-vanaf 2651=E021*1.241 \\
        --glyph-vanaf 2647=E023*1.179 --uit-map /tmp/proef --licentie-bijlage SFU_OFL.txt

Schrijft (in `--uit-map`, standaard de echte plekken):
    astro-sans.ttf         het font (de pagina laadt het, het wiel zet het in de SVG)
    glyph-maten.json       de gemeten maten per glyph
    LICENTIE-AstroSans.txt de licentie en de herkomst van beide bronnen
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

VANAF = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(VANAF)
BRON_STANDAARD = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_STANDAARD = os.path.join(PROJECT, "schil", "static", "astro-sans.ttf")
MATEN_STANDAARD = os.path.join(VANAF, "glyph-maten.json")
LICENTIE_STANDAARD = os.path.join(VANAF, "fonts", "LICENTIE-AstroSans.txt")

FAMILIE = "Astro Sans"
SCHUUR = 200          # de rastermaat waarin gemeten wordt (was ook 200 in het oude bestand)

# De glyphs van dit programma: sleutel -> Unicode
GLYPHS = {
    "Ram": 0x2648, "Stier": 0x2649, "Tweelingen": 0x264A, "Kreeft": 0x264B,
    "Leeuw": 0x264C, "Maagd": 0x264D, "Weegschaal": 0x264E, "Schorpioen": 0x264F,
    "Boogschutter": 0x2650, "Steenbok": 0x2651, "Waterman": 0x2652, "Vissen": 0x2653,
    "Zon": 0x2609, "Maan": 0x263D, "Mercurius": 0x263F, "Venus": 0x2640, "Mars": 0x2642,
    "Jupiter": 0x2643, "Saturnus": 0x2644, "Uranus": 0x2645, "Neptunus": 0x2646,
    "Pluto": 0x2647, "Noordknoop": 0x260A, "Chiron": 0x26B7,
    "Pars Fortuna": 0x2297, "retrograde": 0x211E,
}
# De acht aspecten. Sextiel, sesquiquadraat en quincunx komen uit Symbola; DejaVu heeft ze niet.
# Ontbreekt er een in de bron, dan meldt het script dat en gaat de rest door
# (glyf_aspect() in kern/formaat.py geeft voor een ontbrekend aspect een leeg teken).
ASPECTEN = {
    "conjunctie": 0x260C, "halfvierkant": 0x2220, "vierkant": 0x25A1, "driehoek": 0x25B3,
    "oppositie": 0x260D, "sextiel": 0x26B9, "sesquiquadraat": 0x26BC, "quincunx": 0x26BB,
}
CIJFERS = [ord(c) for c in "0123456789°'"]

LICENTIE_KOP = """Astro Sans — licentie en herkomst
=====================================

Dit font is een subset en bewerking van de hieronder genoemde bronnen, teruggebracht tot de
tekens die dit programma gebruikt (de astrologie-glyphs, de cijfers met het graadteken en de
minuutstreep, en de letters van het scherm) en hernoemd naar "Astro Sans". De naamtabellen
(copyright, familie, versie, deze licentie) zijn opnieuw gezet.

Gebouwd met `data/maak-font.py`.
"""

# De volledige Bitstream Vera-licentie hoort bij DejaVu Sans; die blijft hier staan zodat het
# licentiebestand ook klopt als alleen de letters en de cijfers daaruit komen.
BITSTREAM = """
Licentie van de letters en de cijfers (Bitstream Vera, zoals meegeleverd bij DejaVu)
------------------------------------------------------------------------------------
DejaVu fonts — Copyright (c) 2003 by Bitstream, Inc. All Rights Reserved.
Bitstream Vera is een merk van Bitstream, Inc. De DejaVu-wijzigingen zijn in het publieke domein.

Permission is hereby granted, free of charge, to any person obtaining a copy of the fonts
accompanying this license ("Fonts") and associated documentation files (the "Font
Software"), to reproduce and distribute the Font Software, including without limitation the
rights to use, copy, merge, publish, distribute, and/or sell copies of the Font Software,
and to permit persons to whom the Font Software is furnished to do so, subject to the
following conditions:

The above copyright and trademark notices and this permission notice shall be included in
all copies of one or more of the Font Software typefaces.

The Font Software may be modified, altered, or added to, and in particular the designs of
glyphs or characters in the Fonts may be modified and additional glyphs or characters may
be added to the Fonts, only if the fonts are renamed to names not containing either the
words "Bitstream" or the word "Vera".

This License becomes null and void to the extent applicable to Fonts or Font Software that
has been modified and is distributed under the "Bitstream Vera" names.

The Font Software may be sold as part of a larger software package but no copy of one or
more of the Font Software typefaces may be sold by itself.

THE FONT SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
INCLUDING BUT NOT LIMITED TO ANY WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
PURPOSE AND NONINFRINGEMENT OF COPYRIGHT, PATENT, TRADEMARK, OR OTHER RIGHT. IN NO EVENT
SHALL BITSTREAM OR THE GNOME FOUNDATION BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, INCLUDING ANY GENERAL, SPECIAL, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL DAMAGES,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF THE USE OR
INABILITY TO USE THE FONT SOFTWARE OR FROM OTHER DEALINGS IN THE FONT SOFTWARE.
"""

SYMBOLA = """
Licentie en herkomst van de astrologie-glyphs (Symbola)
-------------------------------------------------------
Symbola — Copyright (C) 2007-2015 George Douros (Unicode Fonts for Ancient Scripts,
http://users.teilar.gr/~g1951d/). De licentiebeschrijving in het font zelf luidt
"Fonts in this site are free for any use"; het copyrightbestand van Debian (pakket
fonts-ancient-scripts) zegt het vollediger: "Fonts are free for any use; they may be opened,
edited, modified, regenerated, packaged and redistributed." Het handelsmerk in het font zegt:
"Symbola is not a merchandise."

De glyph-vormen van de dierenriemtekens, de lichamen, de punten en de aspecten komen uit dit
font en zijn bij het inbouwen geschaald naar de em van het doelfont.
"""

SOURCE_SANS = """
Licentie en herkomst van de letters en de cijfers (Source Sans 3)
-----------------------------------------------------------------
Source Sans 3 — Copyright 2010-2024 Adobe (https://github.com/adobe-fonts/source-sans), onder de
SIL Open Font License 1.1 ("Source" is een gereserveerde naam; ons font heet Astro Sans). De
volledige licentietekst staat in data/fonts/BRON-Source-Sans-3-OFL.txt, en in de OFL staat ook
dat de gereserveerde naam niet in een afgeleide terug mag komen.

Uit dit font komen de letters, de cijfers, het graadteken en de minuutstreep, op gewicht 600.
"""

STARFISHER = """
Licentie en herkomst van de astrologie-glyphs (StarfisherUni)
-------------------------------------------------------------
StarfisherUni — Copyright (c) 2008/2014 Kenneth Hirst (Laser Printing Solutions / Cosmorama),
http://sites.google.com/site/cosmoramaent/home/download. De glyphs BOVEN tekencode 127 vallen
onder de SIL Open Font License 1.1 ("StarFisher" is daar de Reserved Font Name; ons font heet
Astro Sans, dus dat is geregeld); de kale Latijnse tekens 33-127 komen uit Bitstream Vera en
blijven onder die licentie. De volledige brontekst van beide licenties staat in
data/fonts/BRON-StarfisherUni-OFL.txt. Het bestand is opgehaald van
https://fontlibrary.org/en/font/starfisheruni (zip met StarfisherUni.ttf, de FontForge-bron
`StarfisherUni.sfd`, de symbollijst `Starfisher-UNI.pdf` en `SFU_OFL.txt`).

Uit dit font komen de astrologie-glyphs, geschaald naar de em van het doelfont; de Zon staat daar
op U+263C en Steenbok en Pluto komen uit `capricornalt` (U+E021) en `plutoalt2` (U+E023) — zie de
regels met `--glyph-vanaf` in de opdracht hieronder.
"""


def tekens(met_aspecten=True):
    """Alles wat in het font moet: de glyphs, de aspecten, de cijfers en de letters."""
    uit = set(GLYPHS.values()) | set(CIJFERS)
    if met_aspecten:
        uit |= set(ASPECTEN.values())
    uit |= set(range(0x20, 0x7F))      # basis-Latijn: letters, cijfers, leestekens
    uit |= set(range(0xA0, 0x100))     # Latijn-1: é ë ï ü ó ç enzovoort
    return sorted(uit)


def _sha256(pad):
    with open(pad, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _instantieer(font, gewicht):
    """Een variabel font op een gewicht zetten (anders blijft het de standaardinstantie)."""
    if "fvar" not in font:
        return font, None
    from fontTools.varLib import instancer
    assen = {a.axisTag: a.defaultValue for a in font["fvar"].axes}
    if "wght" not in assen or gewicht == assen["wght"]:
        return font, None
    assen["wght"] = gewicht
    if "wdth" in assen:
        assen["wdth"] = 100
    return instancer.instantiateVariableFont(font, assen, inplace=False,
                                             updateFontNames=False), gewicht


def lees_vanaf(lijst):
    """`DOEL=BRON[*SCHAAL]`-regels omzetten naar {doelcodepunt: (broncodepunt, schaal)}.

    Nodig zodra een glyphbron zijn tekens op andere codepunten heeft (StarfisherUni zet de Zon
    op U+263C) of zodra één teken uit een *andere* glyph van de bron moet komen (Steenbok uit
    `capricornalt` U+E021). De schaal erachter is per teken: een glyph uit een ander font is
    zelden even hoog als degene die hij vervangt.
    """
    uit = {}
    for regel in lijst:
        doel, _, bron = regel.partition("=")
        if not bron:
            raise SystemExit(f"--glyph-vanaf verwacht DOEL=BRON[*SCHAAL], kreeg {regel!r}")
        schaal = 1.0
        if "*" in bron:
            bron, _, s = bron.partition("*")
            schaal = float(s)
        uit[int(doel, 16)] = (int(bron, 16), schaal)
    return uit


def zet_glyphs_over(font, bronpad, schaal, gewicht, vanaf=None):
    """De astrologie-glyphs uit een tweede font in het doelfont zetten.

    De contouren worden omgerekend naar de em van het doelfont en met `schaal` vermeerderd
    (Symbola is 2048, de meeste tekstfonts 1000 — zonder die omrekening zouden de glyphs
    twee keer zo groot worden). De penvoorsprong van zo'n glyph wordt de inktbreedte plus een
    marge van 1% van het em aan weerszijden, zodat er in een lopende regel niets tegen zijn
    buurman plakt; de plaatsing in het wiel gebruikt de gemeten inktbreedte.

    `vanaf` haalt een glyph van een andere plek in de bron (`lees_vanaf`); het codepunt in
    *ons* font blijft het codepunt van `GLYPHS`/`ASPECTEN`, zodat de rest van het programma
    niets merkt van de herkomst.
    """
    from fontTools.misc.transform import Transform
    from fontTools.pens.recordingPen import DecomposingRecordingPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.ttLib import TTFont

    bron = TTFont(bronpad)
    bron, glyph_gewicht = _instantieer(bron, gewicht)
    bron_upem = bron["head"].unitsPerEm
    doel_upem = font["head"].unitsPerEm
    factor = doel_upem / bron_upem * schaal
    bron_cmap = bron.getBestCmap()
    bron_gs = bron.getGlyphSet()
    glyfen, hmtx = font["glyf"], font["hmtx"]
    volgorde = font.getGlyphOrder()
    gezet, mist, vanaf_gebruikt = [], [], {}
    for sleutel, cp in list(GLYPHS.items()) + list(ASPECTEN.items()):
        bron_cp, extra = (vanaf or {}).get(cp, (cp, 1.0))
        naam_bron = bron_cmap.get(bron_cp)
        if naam_bron is None:
            mist.append((sleutel, bron_cp))
            continue
        if bron_cp != cp:
            vanaf_gebruikt[sleutel] = (cp, bron_cp, naam_bron, extra)
        rec = DecomposingRecordingPen(bron_gs)
        bron_gs[naam_bron].draw(rec)
        pen = TTGlyphPen(None)
        rec.replay(TransformPen(pen, Transform().scale(factor * extra)))
        glyph = pen.glyph()
        naam_doel = "glyf_" + naam_bron
        if naam_doel in volgorde:
            naam_doel = f"{naam_doel}_{cp:04X}"
        glyph.recalcBounds(glyfen)
        # Let op: `glyfen[naam] = glyph` zet de glyph in de tabel én in de glyphvolgorde
        # (table__g_l_y_f.__setitem__ doet dat zelf); hier dus niets extra aan de volgorde
        # toevoegen, want dan staat de naam er twee keer in en weigert fontTools het
        #        weigeren (len(glyphOrder) == len(glyphs)).
        glyfen[naam_doel] = glyph
        marge = max(1, round(doel_upem / 100))
        hmtx[naam_doel] = (max(1, glyph.xMax - glyph.xMin) + 2 * marge, glyph.xMin - marge)
        for tabel in font["cmap"].tables:
            tabel.cmap[cp] = naam_doel
        gezet.append((sleutel, cp, naam_doel))
    if len(glyfen.glyphOrder) != len(glyfen.glyphs):
        raise SystemExit(f"de glyphvolgorde loopt uit de pas: {len(glyfen.glyphOrder)} namen, "
                         f"{len(glyfen.glyphs)} glyphs")
    return gezet, mist, {"bron_upem": bron_upem, "doel_upem": doel_upem, "factor": factor,
                         "glyph_gewicht": glyph_gewicht, "vanaf": vanaf_gebruikt}


def naamtabellen(font, versie, herkomst):
    """Copyright, familienaam, versie en de licentietekst in het font zelf."""
    from fontTools.misc.timeTools import timestampNow
    naam = font["name"]
    velden = {
        0: f"Astro Sans — afgeleide van {herkomst}. Zie LICENTIE-AstroSans.txt.",
        1: FAMILIE,
        2: "Regular",
        3: f"{FAMILIE}: maak-font.py {versie}",
        4: FAMILIE,
        5: f"Version {versie}",
        6: FAMILIE.replace(" ", "") + "-Regular",
        13: f"Herkomst en licentie: {herkomst}. Het font moet zijn eigen naam houden, de "
            "licentievermelding moet meegaan en het font mag niet los verkocht worden. "
            "Zie data/fonts/LICENTIE-AstroSans.txt in de bronmap.",
    }
    for platform, encoding, taal in ((3, 1, 0x409), (1, 0, 0)):
        for nid, tekst in velden.items():
            naam.setName(tekst, nid, platform, encoding, taal)
    font["head"].modified = timestampNow()


def bouw(bronpad, glyphpad, schaal, gewicht, vanaf=None):
    from fontTools.subset import Options, Subsetter
    from fontTools.ttLib import TTFont

    font = TTFont(bronpad)
    font, bron_gewicht = _instantieer(font, gewicht)
    opties = Options()
    opties.layout_features = ["*"]
    opties.notdef_outline = True
    opties.recalc_bounds = True
    opties.name_IDs = ["*"]
    subsetter = Subsetter(options=opties)
    subsetter.populate(unicodes=tekens())
    subsetter.subset(font)

    uitkomst = {"bron": bronpad, "glyphbron": None, "schaal": None, "gewicht": bron_gewicht}
    if os.path.abspath(glyphpad) != os.path.abspath(bronpad):
        gezet, mist, maten = zet_glyphs_over(font, glyphpad, schaal, gewicht, vanaf)
        uitkomst.update(glyphbron=glyphpad, schaal=schaal, gezet=len(gezet), mist=len(mist),
                        **maten)
        if mist:
            print("LET OP: deze glyphs zitten niet in het glyph-font en komen er dus niet in: "
                  + ", ".join(f"{n} (U+{c:04X})" for n, c in mist))
    return font, uitkomst


def licentietekst(uitkomst, bijlage, opdracht=None):
    from datetime import date
    herkomst = os.path.basename(uitkomst["bron"])
    glyphbron = os.path.basename(uitkomst["glyphbron"]) if uitkomst["glyphbron"] else None
    namen = " ".join(n.lower() for n in (herkomst, glyphbron or ""))
    regels = [LICENTIE_KOP, f"Gebouwd: {date.today().isoformat()}\n",
              f"Letters en cijfers: {herkomst} (sha256 {_sha256(uitkomst['bron'])[:16]}…)"
              + (f", op gewicht {uitkomst['gewicht']}" if uitkomst.get("gewicht") else "") + "\n"]
    if uitkomst["glyphbron"]:
        regels.append(f"Astrologie-glyphs: {glyphbron} "
                      f"(sha256 {_sha256(uitkomst['glyphbron'])[:16]}…), geschaald met factor "
                      f"{uitkomst['factor']:.4f} naar de em van het doelfont "
                      f"({uitkomst['bron_upem']} -> {uitkomst['doel_upem']} eenheden)\n")
    if uitkomst.get("vanaf"):
        regels.append("Glyphs die van een andere plek in de bron komen:\n")
        for sleutel, (doel, bron_cp, naam, extra) in uitkomst["vanaf"].items():
            regels.append(f"  {sleutel}: {naam} U+{bron_cp:04X} -> ons U+{doel:04X}"
                          + (f", extra schaal {extra:.3f}\n" if extra != 1.0 else "\n"))
    if opdracht:
        regels.append(f"\nGebouwd met:\n  {opdracht}\n")
    if herkomst.lower().startswith("dejavu"):
        regels.append(BITSTREAM)
    if "source_sans" in namen or "sourcesans" in namen:
        regels.append(SOURCE_SANS)
    if "symbola" in namen:
        regels.append(SYMBOLA)
    if "starfisher" in namen:
        regels.append(STARFISHER)
    if bijlage:
        with open(bijlage, encoding="utf-8", errors="replace") as f:
            regels.append(f"\nBrontekst van de licentie ({os.path.basename(bijlage)})\n"
                          + "-" * 60 + "\n" + f.read())
    return "".join(regels)


def meet_tekens(font):
    """De penvoorsprong per teken, in em — de maat die de browser gebruikt als hij tekst zet.

    Voor de glyphs hierboven is de *inktbreedte* de maat (die conventie komt uit B4 en blijft),
    maar voor een stukje als `07°` telt de voorsprong van elk teken: daar komt de cursor na
    het teken. Vandaar twee soorten maten in één bestand.
    """
    upem = font["head"].unitsPerEm
    hmtx = font["hmtx"]
    uit = {}
    for cp, gname in font.getBestCmap().items():
        if cp < 0x20:
            continue
        try:
            uit[chr(cp)] = round(hmtx[gname][0] / upem, 4)
        except KeyError:
            continue
    return uit


def meet(font, fontpad):
    """De maten per glyph, precies zoals het oude bestand ze had: rasteren op 200 px en de
    inkt opvragen. De oude waarden (breedte 0,800 bij Ram tegen een contour van 0,791) laten
    zien dat de meting de antialiasing meenam; die conventie houden we aan."""
    from PIL import Image, ImageDraw, ImageFont

    upem = font["head"].unitsPerEm
    cmap = font.getBestCmap()
    uit = {}
    for sleutel, cp in GLYPHS.items():
        if cp not in cmap:
            raise SystemExit(f"glyph {sleutel} (U+{cp:04X}) komt niet in het font terecht")
        letter = ImageFont.truetype(fontpad, SCHUUR)
        beeld = Image.new("L", (SCHUUR * 3, SCHUUR * 3), 0)
        teken = ImageDraw.Draw(beeld)
        teken.text((SCHUUR, SCHUUR), chr(cp), font=letter, fill=255)
        doos = beeld.getbbox()
        if doos is None:
            raise SystemExit(f"glyph {sleutel} (U+{cp:04X}) is leeg in het font")
        x0, y0, x1, y1 = doos
        # De pen staat op (SCHUUR, SCHUUR); de inktdoos daar ten opzichte van bepaalt de maten
        # hieronder.
        uit[sleutel] = {
            "code": cp,
            "chr": chr(cp),
            "breedte": round((x1 - x0) / SCHUUR, 3),
            "hoogte": round((y1 - y0) / SCHUUR, 3),
            "pen_x": round((x0 - SCHUUR) / SCHUUR, 3),
            "pen_y": round((y0 - SCHUUR) / SCHUUR, 3),
        }
    maten = {
        "font": f"{FAMILIE} (schil/static/astro-sans.ttf, gebouwd met data/maak-font.py)",
        "eenheid": "em",
        "gemeten_op_px": SCHUUR,
        "eenheden_per_em": upem,
        "let_op": "pen_x en pen_y zijn de inktdoos ten opzichte van de pen; de plaatsing in "
                  "teken/wiel.py gebruikt alleen 'breedte'.",
        "glyphs": uit,
        "tekens": meet_tekens(font),
        "let_op_tekens": "de penvoorsprong per teken (wat de browser doet als hij '07°' zet), "
                         "zodat de cijfers, het graadteken en de minuutstreep gemeten worden in "
                         "plaats van geschat met tekenbreedte_gewoon/_smal",
    }
    return maten


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--bron", default=BRON_STANDAARD, help="het font voor de letters en de cijfers")
    p.add_argument("--glyphs", help="het font voor de astrologie-glyphs (leeg: hetzelfde als --bron)")
    p.add_argument("--glyph-vanaf", action="append", default=[], metavar="DOEL=BRON[*SCHAAL]",
                   help="een glyph van een andere plek in het glyphfont halen, bijvoorbeeld "
                        "2651=E021 (Steenbok uit capricornalt) of 2609=263C (de Zon staat in "
                        "StarfisherUni op U+263C); met *SCHAAL erachter per teken bijschalen")
    p.add_argument("--glyph-schaal", type=float, default=1.0,
                   help="de glyphs nog eens extra schalen (1.0 = de maat van het bronfont)")
    p.add_argument("--gewicht", type=int, default=400,
                   help="het gewicht waarop een variabel font gezet wordt (400 = Regular)")
    p.add_argument("--uit-map", help="waar de drie uitvoerbestanden komen (leeg: de echte plekken)")
    p.add_argument("--licentie-bijlage", help="een licentiebestand dat voluit mee moet")
    p.add_argument("--versie", default="1.0")
    args = p.parse_args()

    glyphpad = args.glyphs or args.bron
    for pad in (args.bron, glyphpad):
        if not os.path.exists(pad):
            raise SystemExit(f"bronfont niet gevonden: {pad}")
    vanaf = lees_vanaf(args.glyph_vanaf)
    if glyphpad != args.bron and not args.licentie_bijlage \
            and not any(w in os.path.basename(glyphpad).lower()
                        for w in ("symbola", "dejavu", "starfisher", "source_sans", "sourcesans")):
        print("LET OP: de licentie van het glyphfont gaat niet mee — geef --licentie-bijlage mee "
              "(of zet het licentieblok in dit script, zoals bij Symbola en StarfisherUni).")

    font, uitkomst = bouw(args.bron, glyphpad, args.glyph_schaal, args.gewicht, vanaf)

    if args.uit_map:
        os.makedirs(args.uit_map, exist_ok=True)
        font_uit = os.path.join(args.uit_map, "astro-sans.ttf")
        maten_uit = os.path.join(args.uit_map, "glyph-maten.json")
        licentie_uit = os.path.join(args.uit_map, "LICENTIE-AstroSans.txt")
    else:
        font_uit, maten_uit, licentie_uit = FONT_STANDAARD, MATEN_STANDAARD, LICENTIE_STANDAARD

    herkomst = os.path.basename(args.bron) + (
        f" + {os.path.basename(glyphpad)}" if uitkomst["glyphbron"] else "")
    naamtabellen(font, args.versie, herkomst)
    os.makedirs(os.path.dirname(font_uit), exist_ok=True)
    font.save(font_uit)
    print(f"bron: {args.bron}")
    if uitkomst["glyphbron"]:
        print(f"glyphs: {os.path.basename(glyphpad)} (geschaald {uitkomst['factor']:.4f}, "
              f"{uitkomst['gezet']} glyphs overgezet"
              + (f", {uitkomst['mist']} ontbreken" if uitkomst.get("mist") else "") + ")")
        for sleutel, (doel, bron_cp, naam, extra) in (uitkomst.get("vanaf") or {}).items():
            print(f"  {sleutel}: {naam} U+{bron_cp:04X} -> ons U+{doel:04X}"
                  + (f", extra schaal {extra:.3f}" if extra != 1.0 else ""))
    print(f"font: {font_uit} ({os.path.getsize(font_uit)/1024:.1f} kB, {len(tekens())} tekens)")

    maten = meet(font, font_uit)
    with open(maten_uit, "w", encoding="utf-8") as f:
        json.dump(maten, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"maten: {maten_uit}")

    os.makedirs(os.path.dirname(licentie_uit), exist_ok=True)
    with open(licentie_uit, "w", encoding="utf-8") as f:
        f.write(licentietekst(uitkomst, args.licentie_bijlage, " ".join(sys.argv)))
    print(f"licentie: {licentie_uit}")

    # De dekking zoals de rest van het programma hem ziet, plus de maat van een label
    cmap = font.getBestCmap()
    alles = list(GLYPHS.items()) + list(ASPECTEN.items())
    ontbreekt = [f"{k} U+{cp:04X}" for k, cp in alles if cp not in cmap]
    print(f"dekking: {len(alles) - len(ontbreekt)}/{len(alles)} glyphs"
          + (f", ontbreekt: {', '.join(ontbreekt)}" if ontbreekt else ""))
    tm = maten["tekens"]
    print(f"labels: '02°' = {sum(tm.get(c, 0) for c in '02°'):.3f} em, "
          f"'51\\'' = {sum(tm.get(c, 0) for c in chr(53) + chr(49) + chr(39)):.3f} em")
    for sleutel in ("Ram", "Zon", "Noordknoop", "retrograde"):
        r = maten["glyphs"][sleutel]
        print(f"  {sleutel:14s} U+{r['code']:04X} {r['chr']}  breedte {r['breedte']:.3f} "
              f"hoogte {r['hoogte']:.3f} pen {r['pen_x']:+.3f}/{r['pen_y']:+.3f}")


if __name__ == "__main__":
    main()
