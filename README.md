# Astrologie Studio

Eén offline astrologieprogramma voor **Windows**: per cursusjaar de technieken die in dat jaar aan de
orde zijn. Deze versie is **cursusjaar 1**. Geen internet nodig, geen inlog, geen database — je
horoscopen staan als losse bestanden op je eigen computer.

- **Rekenkern:** pyswisseph (Swiss Ephemeris), Koch, tropisch, geocentrisch, True Node.
- **Tekenaar:** eigen SVG-wiel; alle maten, lijndiktes en kleuren staan in `teken/spec.json`.
- **Schil:** één klein Python-proces plus een pagina; geen framework.
- **Technieken zijn data**, geen code: één JSON per techniek in `technieken/`, met `technieken/jaar1.json`
  als schakelaar. Jaar 2 en 3 komen erbij als profiel en techniekbestand, niet als tweede programma.

Wat het programma doet: een horoscoop invullen (datum, tijd, plaats — met zoeken in 54.158 plaatsen en
hun tijdzone), berekenen, het wiel en de aspecten bekijken, de A4-afdruk maken, en de horoscoop bewaren.

## Zelf draaien (vanuit de bron)

Nodig: Python 3.12. De efemeriden staan al in `efemeriden/`.

    python -m pip install pyswisseph tzdata
    python schil/server.py 8086

Dan <http://127.0.0.1:8086/>. Op Windows opent de schil zelf een venster (Edge in app-modus); op Linux
open je die URL in een browser. Standaard luistert het programma alleen op je eigen machine; wil je het
vanaf een andere machine bereiken, start dan met `ASTRO_HOST=0.0.0.0` — dat is je eigen keuze en je eigen
verantwoordelijkheid.

Na een wijziging in `kern/`, in de code van `teken/` of in `schil/` moet het proces opnieuw. `spec.json`,
`technieken/*.json` en de plaatsenlijst worden per vraag gelezen.

## De Windows-versie bouwen

De bouwstraat staat in `bouw/` en is beschreven in `bouw/LEESMIJ.md`: `bouw-windows.bat` maakt de
uitvoerbare bestanden, `maak-installer.bat` de installer. Daarvoor zijn PyInstaller en Inno Setup nodig.

## Controleren of de kern nog klopt

    python schil/server.py --controle      # efemeriden, ijkpunt op 0,001°, font, plaatsenlijst, schrijfmap
    python controle/controle-indeling.py   # de opmaak en de bediening: css/, js/ en index.html

`--controle` is de poort: exit 0 betekent in orde; `controle-indeling.py` keurt de afspraken van de
opgesplitste pagina (elf controles). De ijkingen per onderdeel (invoer, opslag, plaatsen, venster,
installer, console, transits) staan **niet** in deze map: ze horen bij de metingen en de gesprekken
eromheen, niet bij de bron van het programma. Ze staan op de ontwikkelmachine, buiten de repo, met hun
uitkomsten per datum.

## Mappen

| Map | Wat erin staat |
|---|---|
| `kern/` | De rekenkern: posities, huizen, aspecten, tijdverschuivingen, invoer, opslag → JSON |
| `technieken/` | Het register: één JSON per techniek, plus de jaarindexen |
| `teken/` | De SVG-tekenaar en `spec.json` met alle maten en kleuren |
| `schil/` | Het programma: de pagina en het Python-proces |
| `controle/` | De keuring van de indeling van het scherm |
| `data/` | De plaatsenlijst, de eigen aanvullingen en de fontbronnen |
| `efemeriden/` | De efemeriden van Swiss Ephemeris (1800–2399) |
| `bouw/` | De bouwstraat voor Windows en de installatietekst |

Je horoscopen staan niet in deze map maar in je gebruikersmap (`~/astrologie-horoscopen` op Linux,
`C:\Users\<naam>\astrologie-horoscopen` op Windows): één JSON-bestand per horoscoop plus `index.json`,
`settings.json`, je eigen plaatsen en een submap `staat/` met wegwerpbestanden. Die ene map kopiëren is
de back-up. `ASTRO_HOROSCOPENMAP` verzet hem.

## Gegevens, bronnen en licenties

| Wat | Herkomst | Licentie |
|---|---|---|
| De plaatsenlijst `data/plaatsen.json` | [GeoNames](https://www.geonames.org/) | CC BY 4.0, met naamsvermelding |
| De efemeriden `efemeriden/*.se1` | Swiss Ephemeris (Astrodienst) | AGPL-3.0 of een commerciële licentie |
| Het font **Astro Sans** `schil/static/astro-sans.ttf` | glyphs uit StarfisherUni (© 2008/2014 Kenneth Hirst), letters en cijfers uit Source Sans 3 (© 2010-2024 Adobe) | SIL Open Font License 1.1 — zie `data/fonts/LICENTIE-AstroSans.txt` |
| Het schermfont **Selawik** | Microsoft, gemaakt als vrije vervanger van Segoe UI | SIL OFL 1.1 — zie `data/fonts/LICENTIE-Selawik.txt` |
| Een plaats opzoeken via OpenStreetMap (alleen als GeoNames niets geeft) | OpenStreetMap | ODbL |

Alle licenties en bronvermeldingen staan ook in het programma zelf, op de tab **Over**.

## Licentie

Dit programma valt onder de **GNU Affero General Public License, versie 3 (AGPL-3.0)**; de volledige,
ongewijzigde tekst staat in `LICENSE`. Die keuze volgt uit de rekenkern: Swiss Ephemeris is dubbel
gelicenseerd — AGPL of de commerciële licentie — en met de AGPL komt het hele programma eronder.

In gewone taal: gebruiken, aanpassen en doorgeven mag, mits de broncode erbij zit of aangeboden wordt en
het geheel onder dezelfde licentie blijft. Wie het programma via een netwerk gebruikt, houdt daarmee ook
recht op de bron.

Wat apart blijft en mee moet met elke verspreiding: de **plaatsgegevens** van GeoNames (CC BY 4.0, met
naamsvermelding) en het **glyph-font** met zijn eigen licentiebestand
(`data/fonts/LICENTIE-AstroSans.txt`).

## Contact

studio@astrosofica.nl
