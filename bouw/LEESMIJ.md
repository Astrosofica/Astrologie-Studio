# De Windows-bundel bouwen

Deze map bevat alles wat de build nodig heeft. Er is niets meer te verzinnen op de avond zelf: het
script doet de stappen en de zelfcontrole zegt of de bundel deugt.

| Bestand | Wat het is |
|---|---|
| `astrologie-studio.spec` | De PyInstaller-spec: welke gegevens mee de bundel in, wat er buiten blijft, en waarom |
| `bouw-windows.bat` | Het bouwscript voor de Windows-pc: controleert de omgeving, bouwt, en laat de zelfcontrole draaien |
| `controle-verwacht.json` | Het ijkpunt voor die zelfcontrole: vier standen van de ijkkaart (1963-07-19 16:51:26 Controleplaats — bewust vóór 1970) |
| `astrologie-studio.ico` | Het pictogram van de .exe (hetzelfde wiel als de favicon van de landingspagina) |
| `maak-bronzip.sh` | Maakt de bronzip die naast de .exe hoort (AGPL-3.0). Draait op de server, niet op Windows |
| `astrologie-studio.iss` | Het Inno Setup 6-script voor de installer: per gebruiker, met verwijderaar |
| `maak-installer.bat` | Bouwt de installer op de Windows-pc (vraagt Inno Setup 6) |
| `maak-versie-iss.py` | Schrijft `versie.iss` met het versienummer uit `kern/versie.py` en de nieuwste bronzip |
| `installatie-tekst.rtf` | Wat de gebruiker vóór de installatie te lezen krijgt: RTF, dus met koppen en vet (Inno toont hem in een rich-edit-venster) |

## 1. Bouwen

Op de Windows-pc, vanuit de projectmap:

```
bouw\bouw-windows.bat            BEIDE smaken: eerst zonder venster, dan met consolevenster
bouw\bouw-windows.bat stil       alleen de versie ZONDER venster (voor de cursist)
bouw\bouw-windows.bat console    alleen de versie MET consolevenster (wat de cursist krijgt)
```

Dubbelklikken bouwt sinds 27 okt 2026 **allebei**, elk met zijn eigen zelfcontrole, zodat je voor
`maak-installer.bat` niets meer hoeft aan te passen. Het script:

1. kijkt of Python in het PATH staat (3.11 of 3.12);
2. kijkt of `pyinstaller`, `pyswisseph` en `tzdata` er zijn, en installeert ze anders;
3. kijkt of de efemeriden in `efemeriden\` liggen — zonder die bestanden rekent het programma met de
   Moshier-benadering in plaats van de echte standen, en dat mag geen stille terugval zijn;
4. bouwt met `pyinstaller --clean --noconfirm bouw\astrologie-studio.spec`;
5. laat de zelfcontrole draaien en **stopt met een fout** als die faalt;
6. noemt de grootte en de sha256 van de .exe.

Uitkomst, afhankelijk van de smaak:

| Smaak | Bestand | Voor wie |
|---|---|---|
| met console | `dist\Astrologie Studio - console.exe` | **de cursist** (besluit 27 okt 2026): hij ziet de URL, de meldingen en dat er een lokale server draait — niets verborgen. Deze gaat de installer in |
| zonder console (`stil`) | `dist\Astrologie Studio.exe` | optioneel, voor wie geen venster wil: stoppen met Bestand > Afsluiten |

Ongeveer 16 MB per stuk (op Linux 15,6 MB gemeten; op Windows komt de Visual C++-runtime erbij).
Geen installatieprogramma: één bestand dat je kunt dubbelklikken.

**Waarom de consoleversie geen haakjes in de naam heeft:** haakjes in een pad botsen met de
`if (...)`-blokken van cmd. Een streepje is veiliger, en het leest net zo goed.

**Wat er in de stille versie anders is:** er is geen `sys.stdout`, dus alles wat het programma print
gaat naar `fouten.log` in de map met de horoscopen; het access-log staat uit; en een fout die het
starten tegenhoudt komt als Windows-melding in beeld in plaats van stil te sterven. De zelfcontrole
schrijft haar verslag naar `controle-uitkomst.txt`, want in de stille bundel valt er niets op het
scherm te lezen — daarom leest het bouwscript dat bestand.

**Eén schil per keer.** Een tweede start naast een draaiende schil zet geen tweede server op: hij
vraagt op de vaste poort of daar hijzelf draait (`/api/leeft`) en opent dan dat venster. De poort is
de grendel, geen extra bestand.

## 2. Wat de zelfcontrole narekent

`--controle` is geen vinklijstje. Het is de vraag of het programma bij zijn eigen gegevens kan
komen, en die vraag wordt met een berekening beantwoord:

- **25 bestanden aanwezig** — efemeriden, plaatsenlijst, technieken, de pagina, de drie fonts, de
  licenties, `LICENSE` en `README.md`. Ontbreekt er een, dan staat de naam erbij.
- **efemeriden in gebruik: Swiss Ephemeris** — een kaart wordt berekend en het programma zegt zelf
  welke efemeride het gebruikte. "Moshier" hier betekent: de bundel mist de `.se1`-bestanden en
  rekent stil te onnauwkeurig. Dit is de controle die er echt toe doet.
- **standen gelijk aan het ijkpunt** — zon, maan, ascendant en MC tegen `controle-verwacht.json`,
  binnen 0,001 graad (3,6 boogseconde). Zo komt een beschadigd of verkeerd efemeridebestand eruit.
- **wiel getekend met het eigen font** — het wiel wordt echt getekend en het lettertype moet als
  data-URI in de SVG zitten; anders is het font niet meegekomen.
- **plaatsenlijst leesbaar** — een zoekopdracht op "Dieren" levert een treffer.
- **dienst voor OpenStreetMap ingesteld** — `data/osm-dienst.json` zit in de bundel.
- **schrijfmap beschrijfbaar** — er wordt een proefbestand in `~/astrologie-horoscopen` gezet en weer
  weggehaald.

Exit 0 = in orde, exit 1 = niet in orde. Het bouwscript stopt op die 1.

## 3. Weggeven: twee bestanden, niet één

Op de server (bot640), van dezelfde commit als waarmee je bouwde:

```
bash bouw/maak-bronzip.sh
```

Dat maakt `uitgave/astrologie-studio-bron-<datum>-<commit>.zip` en print de sha256. **Die zip hoort
erbij.** Het programma staat onder de AGPL-3.0 en de Over-tab zegt letterlijk: "de broncode wordt
meegeleverd bij iedere verspreiding". Eén .exe sturen en de bron vergeten is de licentie niet
nakomen — en het is meteen het punt waar een cursist die het na wil zoeken niets vindt.

Dus per uitgave: de .exe, de bronzip, en een regel met de sha256 van allebei. Zet ze in één map.

## 4. Wat hierdoor in het programma veranderd is (20 oktober 2026)

Een bundel maakt twee dingen stuk die in ontwikkeling onzichtbaar zijn, en die zijn allebei
gerepareerd voordat deze spec er was:

- **De programmamap is in een bundel tijdelijk.** PyInstaller pakt alles uit in een map die na het
  afsluiten verdwijnt. Het programma schreef de OSM-cache en de eigen plaatsen in die map — dus
  weg bij de volgende start. Sinds `kern/paden.py` is er een hard onderscheid: `bron()` voor wat
  meegeleverd wordt (alleen lezen), `gebruikersmap()` voor wat de gebruiker maakt. De eigen
  plaatsen en de OSM-cache staan nu naast de horoscopen in `~/astrologie-horoscopen`, zodat één map
  kopiëren alles dekt. Het meegeleverde `data/eigen-plaatsen.tsv` is nu een leeg voorbeeld met de
  uitleg in de kop; bij het eerste gebruik wordt het naar de gebruikersmap gekopieerd.
- **De efemeriden stonden op een vast pad van de ontwikkelmachine**
  (`~/.local/share/swisseph`). Ze liggen nu in `efemeriden/` in de projectmap, en
  `ASTRO_EPHE_PATH` wint nog steeds als je ze ergens anders wilt hebben.

En twee dingen die met de eerste cursist te maken hebben:

- **De schil luistert alleen nog op `127.0.0.1`.** Op `0.0.0.0` stonden de horoscopen van de hele
  les op het netwerk van de cursist, en Windows vroeg bij de eerste start om toestemming van de
  firewall. Ontwikkelen op bot640 zet `ASTRO_HOST=0.0.0.0` in het startcommando.
- **De schil zoekt zelf een vrije poort** (8086 en dan negen verder) en **opent in een bundel zelf
  de browser**. Anders moet een cursist een adres intypen, en dat is precies het soort stap waar
  het misgaat.

## 5. Wat er nog niet is

- **Geen ondertekening.** Windows toont bij een onbekende .exe "Windows heeft uw pc beschermd"
  (SmartScreen) met "Meer informatie" en dan "Toch uitvoeren". Bij de eerste kennismaking is dat
  een drempel, en er is niets aan te doen zonder een code-signing-certificaat (honderd euro per
  jaar of meer). Zet het in de begeleidende tekst bij de eerste uitgave.
- **Geen macOS.** Daar is geen machine voor; dat blijft de enige echte drempel (zie `DISTRIBUTIE.md`).
- **Geen tray-pictogram.** De versie die de cursist krijgt is sinds 27 okt 2026 die **met**
  consolevenster, dus er staat altijd een venster in de taakbalk waar hij het programma terugvindt -
  dat lost het probleem op waar een tray-pictogram voor bedoeld was. De stille bundel heeft geen
  venster (20 oktober 2026); daar gaat stoppen met Bestand > Afsluiten, en wie dat vergeet ziet het
  programma in Taakbeheer staan. Die smaak gaat niet de installer in.

## 6. De installer (sinds 20 oktober 2026)

```
bouw\maak-installer.bat
```

Eerst moet de bundel die meegaat er zijn — dat is sinds 27 okt 2026 de **consoleversie**
(`bouw\bouw-windows.bat` bouwt hem, samen met de stille) — en moet de bronzip in `uitgave\` liggen
(gemaakt op de server). Daarna:

1. zoekt het script Inno Setup 6 (gratis, https://jrsoftware.org/isdl.php) en stopt met een melding
   als het er niet is;
2. schrijft `python bouw\maak-versie-iss.py` het versienummer en de naam van de bronzip in
   `bouw\versie.iss` — het nummer komt uit `kern/versie.py`, en er is geen tweede plek waar het staat;
3. compileert ISCC het script tot `uitgave\astrologie-studio-<versie>-setup.exe`.

**Open je het .iss in de Inno Setup-IDE (dubbelklikken) in plaats van het .bat?** Dat mag, maar het
.bat doet stap 2 en de IDE niet: zonder `python bouw\maak-versie-iss.py` compileert de IDE met **het
nummer van de vorige keer** — geen fout, geen waarschuwing, een installer die liegt over zijn versie.
Bestaat `versie.iss` helemaal niet (een verse kopie van de repo), dan stopt hij nu met de melding dat
je dat script moet draaien; ontbreekt alleen de *juiste* inhoud, dan zegt niets iets. Het .bat is dus
de route: dat doet de drie stappen in de juiste orde. Wil je toch de IDE gebruiken, draai dan eerst
`python bouw\maak-versie-iss.py`.

Wat de installer doet:

- **Per gebruiker** (`PrivilegesRequired=lowest`): geen beheerderswachtwoord, geen UAC-vraag. De app
  komt in `%LOCALAPPDATA%\Programs\Astrologie Studio`, de snelkoppelingen in het eigen profiel.
  Voor een lescomputer waar iedereen hem moet hebben is een aparte variant per machine nodig.
- **De gegevens blijven buiten de installatiemap**: `%USERPROFILE%\astrologie-horoscopen`. De
  installer raakt die map nooit aan, ook niet bij een upgrade.
- **De verwijderaar vraagt** of die map ook weg moet, met het pad erbij en "nee" als antwoord als je
  gewoon doorgaat. Programma weg, horoscopen laten staan — dat is wat je bij een upgrade wilt.
- **De bronzip gaat mee** de installatiemap in (`{app}\bron`), plus `LICENSE`, `README.md` en de
  licentieteksten van de lettertypen. De AGPL-3.0 en de Over-tab beloven dat.
- **De consoleversie gaat niet mee.** Die is gereedschap voor onszelf.

Wat de installer **niet** oplost: de SmartScreen-waarschuwing. Die gaat pas weg met een
code-signing-certificaat. De tekst vóór de installatie zegt dat ook, met wat de gebruiker moet doen.

**Nakijken zonder Windows:** `/usr/bin/python3 ../astrologie-studio-ijking/ijk-installer.py` (buiten de
repo) controleert op de server of elk bestand dat het script noemt bestaat, of `versie.iss` klopt met `kern/versie.py`, of de AppId een
vaste GUID is, of de bronzip meegaat, of er geen accolade-paar in het commentaar van `[Code]` staat
(dat sloopt de compilatie), en of een ontbrekend `versie.iss` een leesbare melding geeft. Wat het niet
kan: de Pascal-code compileren — dat gebeurt op de Windows-pc.
