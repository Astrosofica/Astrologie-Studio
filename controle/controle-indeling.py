"""De indeling van het scherm keuren: `schil/static/index.html` plus `css/` en `js/`.

De opmaak staat in `css/` en de bediening in `js/`; `index.html` is alleen nog
het skelet. Dat is alleen vol te houden als de afspraken meetbaar zijn. Dit script keurt ze, en het is
de vangrail voor elke volgende wijziging: een bestand dat niet geladen wordt, een declaratie die twee
keer bestaat, of code die op de verkeerde laag staat.

**De afspraken.**

1. Elk bestand in `css/` en `js/` wordt door `index.html` geladen, en alles wat `index.html` laadt
   bestaat. Geen wees en geen dode verwijzing.
2. De volgorde in `index.html` is de volgorde van de bestandsnaam (`00`, `10`, `20`…). De cascade van de
   CSS en de werkruimte van de JS hangen eraan.
3. In `00` tot en met `60` staat **geen enkele regel die iets doet**: alleen declaraties en Commentaar.
   Alles wat bij het laden loopt staat in `90-start.js`, dat als laatste komt. Zonder die regel kan een
   luisteraar in een vroeg bestand iets gebruiken dat pas later bestaat.
4. Elke naam op topniveau bestaat **één keer** over alle bestanden samen.
5. Elk `document.getElementById("…")` in de JS wijst een id aan dat in `index.html` staat.
6. Elk bestand is syntactisch in orde (`node --check`, als node er is).

Uitvoer: één regel per keuring, en aan het eind `klaar: n van m`. Afsluitcode 1 zodra er iets niet
klopt, zodat een bouw of een cronjob erop kan afgaan.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
STATIC = PROJECT / "schil" / "static"
INDEX = STATIC / "index.html"

MAX_REGELS = 900          # een bestand boven deze maat is een teken dat er weer te veel in zit
START = "90-start.js"     # het enige bestand dat bij het laden iets mag doen

# Een declaratie op topniveau: `function x(`, `async function x(`, `let x`, `const x`, `var x`, `class x`.
DECL = re.compile(
    r"^(?:async\s+)?(?:function\s+(?P<fn>[A-Za-z_$][\w$]*)"
    r"|(?:let|const|var)\s+(?P<var>[A-Za-z_$][\w$]*)"
    r"|class\s+(?P<cls>[A-Za-z_$][\w$]*))"
)

CONTROLES: list[tuple[str, bool, str]] = []


def keur(naam: str, goed: bool, uitleg: str = "") -> None:
    CONTROLES.append((naam, goed, uitleg))


def bestanden(soort: str) -> list[Path]:
    map_ = STATIC / soort
    return sorted(map_.glob("*." + soort)) if map_.is_dir() else []


def geladen(pagina: str, soort: str) -> list[str]:
    patroon = rf'/static/{soort}/([^"?]+)'
    return re.findall(patroon, pagina)


def topniveau(tekst: str) -> list[tuple[int, str, str]]:
    """Alle declaraties en alle uitvoerende regels op topniveau, met hun regelnummer."""
    uit = []
    for nummer, regel in enumerate(tekst.split("\n"), start=1):
        if not regel or regel[0].isspace() or regel.startswith("/"):
            continue
        m = DECL.match(regel)
        if m:
            uit.append((nummer, m.group("fn") or m.group("var") or m.group("cls"), "decl"))
        elif regel[0] not in "})]":
            uit.append((nummer, "", "doet"))
    return uit


def main() -> int:
    if not INDEX.is_file():
        print("index.html ontbreekt")
        return 1
    pagina = INDEX.read_text(encoding="utf-8")

    css_op_schijf = [p.name for p in bestanden("css")]
    js_op_schijf = [p.name for p in bestanden("js")]
    css_geladen = geladen(pagina, "css")
    js_geladen = geladen(pagina, "js")

    keur("elk css-bestand wordt geladen", sorted(css_geladen) == css_op_schijf,
         f"geladen {len(css_geladen)}, op schijf {len(css_op_schijf)}")
    keur("elk js-bestand wordt geladen", sorted(js_geladen) == js_op_schijf,
         f"geladen {len(js_geladen)}, op schijf {len(js_op_schijf)}")
    keur("niets geladen dat niet bestaat",
         all((STATIC / "css" / n).is_file() for n in css_geladen)
         and all((STATIC / "js" / n).is_file() for n in js_geladen))
    keur("de volgorde is de volgorde van de naam",
         css_geladen == sorted(css_geladen) and js_geladen == sorted(js_geladen) and START in js_geladen)
    keur("90-start.js komt achteraan", bool(js_geladen) and js_geladen[-1] == START)
    keur("index.html is het skelet", len(pagina.split("\n")) < 800,
         f"{len(pagina.split(chr(10)))} regels")

    # 3 en 4: per bestand de declaraties en de uitvoerende regels
    alle_namen: dict[str, str] = {}
    dubbel: list[str] = []
    doet: list[str] = []
    te_groot: list[str] = []
    for naam in js_geladen:
        pad = STATIC / "js" / naam
        tekst = pad.read_text(encoding="utf-8")
        regels = len(tekst.split("\n"))
        if regels > MAX_REGELS:
            te_groot.append(f"{naam} ({regels})")
        for nummer, kandidaat, soort in topniveau(tekst):
            if soort == "decl":
                if kandidaat in alle_namen:
                    dubbel.append(f"{kandidaat} in {naam} en {alle_namen[kandidaat]}")
                alle_namen[kandidaat] = naam
            elif naam != START:
                doet.append(f"{naam}:{nummer}")
    keur("geen dubbele declaraties", not dubbel, "; ".join(dubbel[:3]))
    keur("geen uitvoerende regel buiten 90-start.js", not doet, ", ".join(doet[:5]))
    keur("geen bestand boven de 900 regels", not te_groot, ", ".join(te_groot))

    # 5: elke id die de JS opvraagt bestaat - in de pagina, of door de JS zelf gemaakt
    #
    # Een deel van de bediening bouwt de JS bij het laden: de standkeuze van het wiel, de tijd- en de
    # leeftijdsstapper en de Berekenen-knop van de technieken bestaan niet in de HTML. Ze tellen mee
    # zodra de JS ergens een id van die naam zet (`veld.id = "…"`, `id="…"`, `setAttribute("id", …)`),
    # want dan is de opvraag legitiem.
    ids = set(re.findall(r'id="([^"]+)"', pagina))
    gemaakt: dict[str, str] = {}
    gevraagd: dict[str, str] = {}
    for naam in js_geladen:
        tekst = (STATIC / "js" / naam).read_text(encoding="utf-8")
        for nummer, regel in enumerate(tekst.split("\n"), start=1):
            for m in re.finditer(r'(?:\.id\s*=|id=|setAttribute\(\s*["\']id["\']\s*,)\s*'
                                 r'["\']([A-Za-z][\w-]*)["\']', regel):
                gemaakt.setdefault(m.group(1), f"{naam}:{nummer}")
            if "getElementById(" not in regel:
                continue
            for m in re.finditer(r'getElementById\(\s*"([^"]+)"\s*\)', regel):
                gevraagd.setdefault(m.group(1), f"{naam}:{nummer}")
    mis = {k: v for k, v in gevraagd.items() if k not in ids and k not in gemaakt}
    keur("elke opgevraagde id bestaat", not mis,
         f"{len(ids)} in de pagina, {len(gemaakt)} door de JS gemaakt"
         + ("; " + ", ".join(f"{k} ({v})" for k, v in list(mis.items())[:5]) if mis else ""))

    # 6: syntax
    node = shutil.which("node")
    if node:
        kapot = []
        for naam in js_geladen:
            uitkomst = subprocess.run([node, "--check", str(STATIC / "js" / naam)],
                                      capture_output=True, text=True)
            if uitkomst.returncode != 0:
                kapot.append(f"{naam}: {uitkomst.stderr.strip().splitlines()[0] if uitkomst.stderr else '?'}")
        keur("elk js-bestand is syntactisch in orde", not kapot, "; ".join(kapot))
    else:
        keur("elk js-bestand is syntactisch in orde", True, "overgeslagen: node niet gevonden")

    print("Indeling van het scherm")
    print()
    for naam, goed, uitleg in CONTROLES:
        teken = "ok  " if goed else "FOUT"
        print(f"  {teken}  {naam}" + (f"  ({uitleg})" if uitleg else ""))
    goed = sum(1 for _, g, _ in CONTROLES if g)
    print()
    print(f"klaar: {goed} van {len(CONTROLES)}")
    print()
    print("Bestanden:")
    for soort, namen in (("css", css_geladen), ("js", js_geladen)):
        for naam in namen:
            pad = STATIC / soort / naam
            print(f"  {soort}/{naam:22s} {len(pad.read_text(encoding='utf-8').split(chr(10))):5d} regels")
    print(f"  index.html{'':14s} {len(pagina.split(chr(10))):5d} regels")
    return 0 if goed == len(CONTROLES) else 1


if __name__ == "__main__":
    sys.exit(main())
