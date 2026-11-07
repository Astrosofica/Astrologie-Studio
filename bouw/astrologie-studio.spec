# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller-spec voor Astrologie Studio.

Bouwen vanaf de projectmap:

    pyinstaller --clean --noconfirm bouw/astrologie-studio.spec

Daarna:

    "dist/Astrologie Studio.exe" --controle

Twee smaken uit deze ene spec (20 oktober 2026):

- **met consolevenster** - `dist/Astrologie Studio - console.exe`. Die houd je zelf: je ziet de URL,
  je ziet elke fout, en het access-log loopt mee. Dit is de versie om mee te bouwen en te testen.
- **zonder consolevenster** - `dist/Astrologie Studio.exe`, de nette naam, voor de cursist.
  `bouw-windows.bat stil` zet `ASTRO_STIL=1` en dan bouwt deze spec die versie (`console=False`).
  Stoppen gaat daar met Bestand > Afsluiten; wat er misgaat gaat naar `fouten.log` bij de horoscopen,
  en een fout die het starten tegenhoudt komt als Windows-melding in beeld.

Eén spec, twee uitkomsten, zodat er geen tweede waarheid over de inhoud van de bundel kan ontstaan:
wat erin zit is in beide gevallen hetzelfde.

Deze spec doet drie dingen die een kale `pyinstaller schil/server.py` niet doet, en die alle drie
nodig zijn omdat het programma meer is dan code:

1. **De gegevens mee.** De efemeriden, de plaatsenlijst, de technieken, de lettertypen en de
   licentieteksten staan als losse bestanden in de projectmap. Zonder `datas` start het programma
   wel, maar zonder efemeriden rekent het met de Moshier-benadering (een stille terugval, geen
   foutmelding) en zonder `plaatsen.json` is er geen keuzelijst. `schil/server.py --controle`
   rekent daarom een kaart en kijkt welke efemeride er gebruikt is.
2. **De tijdzones mee (`tzdata`).** Op Linux leest `zoneinfo` de systeemdatabase; op Windows is
   die er niet. Zonder `tzdata` in de bundel valt elke kaart om met "No time zone found with key
   Europe/Amsterdam". Daarom `collect_data_files("tzdata")` én `tzdata` in de eisen van de bouw.
3. **De licenties mee.** De Over-tab in het programma verwijst naar `LICENSE` en naar de
   licentieteksten van de lettertypen. Als die niet in de bundel zitten, wijst de bronvermelding
   naar niets - en dan is de OFL niet nagekomen. Ze staan hieronder daarom los vermeld, niet als
   onderdeel van een map die iemand later opruimt.

De broncode meeleveren (AGPL-3.0) doet deze spec niet: dat is `bouw/maak-bronzip.sh`, en die hoort
bij elke uitgave naast de .exe te liggen. Zie `bouw/LEESMIJ.md`.
"""

import os

from PyInstaller.utils.hooks import collect_data_files

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(SPEC)))

# --- de gegevens die mee moeten ---------------------------------------------------------------
DATAS = [
    (os.path.join(PROJECT, "schil", "static"), "schil/static"),      # pagina, fonts
    (os.path.join(PROJECT, "technieken"), "technieken"),             # het techniek-register
    (os.path.join(PROJECT, "teken", "spec.json"), "teken"),          # de maten van het wiel
    (os.path.join(PROJECT, "efemeriden"), "efemeriden"),             # sepl/semo/seas_18.se1
    (os.path.join(PROJECT, "data", "plaatsen.json"), "data"),
    (os.path.join(PROJECT, "data", "glyph-maten.json"), "data"),
    (os.path.join(PROJECT, "data", "osm-dienst.json"), "data"),      # de proxy-URL en de sleutel
    (os.path.join(PROJECT, "data", "eigen-plaatsen.tsv"), "data"),   # leeg voorbeeld met uitleg
    (os.path.join(PROJECT, "bouw", "controle-verwacht.json"), "bouw"),
    # Licenties: los, zodat ze niet met een map meeverdwijnen.
    (os.path.join(PROJECT, "LICENSE"), "."),
    (os.path.join(PROJECT, "README.md"), "."),
    (os.path.join(PROJECT, "data", "fonts", "LICENTIE-AstroSans.txt"), "data/fonts"),
    (os.path.join(PROJECT, "data", "fonts", "LICENTIE-Selawik.txt"), "data/fonts"),
    (os.path.join(PROJECT, "data", "fonts", "bron", "Source_Sans_3-OFL.txt"), "data/fonts/bron"),
    (os.path.join(PROJECT, "data", "fonts", "bron", "StarfisherUni-OFL.txt"), "data/fonts/bron"),
]

# De tijdzones (nodig op Windows, zie de toelichting hierboven). `tzdata` moet in de omgeving van
# de bouw geinstalleerd zijn; staat het er niet, dan zegt de bouw dat liever meteen.
DATAS += collect_data_files("tzdata")

a = Analysis(
    [os.path.join(PROJECT, "schil", "server.py")],
    pathex=[PROJECT],
    binaries=[],
    datas=DATAS,
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    # Wat zeker niet nodig is: de GUI-toolkit, de testrommel en de documentatiegenerator.
    excludes=["tkinter", "unittest", "doctest", "pydoc", "pdb", "lib2to3", "test"],
    noarchive=False,
)

pyz = PYZ(a.pure)

# Het versienummer in de eigenschappen van de .exe (rechtsklik > Eigenschappen > Details), geschreven
# door maak-versie-iss.py uit kern/versie.py. Staat het bestand er niet (bijvoorbeeld op een verse
# kloon waar de generator nog niet liep), dan bouwt PyInstaller zonder versie-informatie: dat is
# hinderlijk maar geen reden om de bouw te laten mislukken.
VERSIE_INFO = os.path.join(PROJECT, "bouw", "versie-info.txt")

# De smaak: `bouw-windows.bat stil` zet ASTRO_STIL=1 in de omgeving voordat PyInstaller start.
STIL = os.environ.get("ASTRO_STIL") == "1"
NAAM = "Astrologie Studio" if STIL else "Astrologie Studio - console"

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=NAAM,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                 # UPX is niet nodig en maakt antivirus-scanners zenuwachtig
    runtime_tmpdir=None,
    # Met consolevenster in de testversie (je ziet elke fout), zonder in de versie voor de cursist.
    # Zonder console is er geen `sys.stdout`: `schil/server.py` schrijft dan naar fouten.log en zet
    # het access-log uit, zodat er niets op een leeg uitvoerkanaal knalt.
    console=not STIL,
    disable_windowed_traceback=False,
    version=VERSIE_INFO if os.path.isfile(VERSIE_INFO) else None,
    icon=os.path.join(PROJECT, "bouw", "astrologie-studio.ico"),
)
