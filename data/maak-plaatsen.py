#!/usr/bin/env python3
"""Bouwt `data/plaatsen.json`: de plaatsenlijst van het invulscherm.

Bron: **GeoNames** (<https://download.geonames.org/export/dump/>), licentie CC BY 4.0 — de
bronvermelding hoort in het scherm te staan (zie `schil/static/index.html`, de regel onderaan).

Wat erin gaat:
  - NL.zip en BE.zip  : **elke** bewoonde plaats van Nederland en Belgie (feature class P), dus ook
                        een dorp als Achthuizen of Doesburg;
  - cities15000.zip   : de plaatsen elders in de wereld vanaf 15.000 inwoners;
  - admin1CodesASCII.txt : de namen van de provincies en deelstaten buiten Nederland en Belgie.

Van elke plaats gaan **alle** schone naamsvarianten mee (GeoNames kolom 4: alternatieve namen). Dat
is nodig omdat juist de Nederlandse naam vaak niet de hoofdnaam is: van Antwerpen staat er
"Antwerp", en "Antwerpen" is de 21e van 64 varianten; "Luik" is de 27e variant van "Liege". Voor
steden buiten Nederland en Belgie gaan de varianten mee vanaf `DREMPEL_INWONERS` inwoners, zodat de
lijst niet uitdijt met varianten van elk gehucht (Keulen, Londen en Wenen werken zo wel, een klein
dorp in Spanje houdt zijn eigen naam).

**Streek en gemeente.** Gelijknamige plaatsen zijn anders alleen
aan hun coordinaten te onderscheiden, en die zeggen een gebruiker niets. Elke plaats krijgt daarom
twee etiketten mee, en per land komen die uit het veld waar de bron ze heeft:

  - **Nederland**: streek = de **provincie** (het ADM1-object: "Provincie Zuid-Holland" -> Zuid-
    Holland), gemeente = de **gemeente** (het ADM2-object: "Gemeente Hengelo" -> Hengelo);
  - **Belgie**: streek = de **provincie** uit adm2 ("Provincie Oost-Vlaanderen"), gemeente = de
    **gemeente** uit adm4 (de 565 ADM4-objecten in BE.txt). Het gewest uit adm1 (Vlaanderen,
    Wallonie) zegt te weinig om uit te kiezen en wordt niet gebruikt;
  - **elders**: streek = adm1 uit `admin1CodesASCII.txt` (VS-staten, Duitse deelstaten); de gemeente
    blijft leeg, want dat is per land te verschillend.

De twee etiketten staan **als nummer** in een tabel `streken`, niet letterlijk bij elk van de ruim
54.000 plaatsen: dat scheelt de helft van de groei van het bestand (gemeten: +0,5 MB tegen +1,1 MB).

De uitkomst heeft de plaatsen **een keer** en de namen als verwijzingen daarnaar, zodat dezelfde
plaats niet telkens opnieuw in het bestand staat:

    {"bron": ..., "licentie": ..., "gebouwd": ..., "aantal": N,
     "plaatsen": [[naam, breedte, lengte, land, zone, inwoners, streeknr, gemeentenr], ...],
     "streken": ["Overijssel", "Gelderland", ...],
     "namen": {"dieren": [123], "dier": [123], "antwerpen": [456], ...}}

Draaien:  /usr/bin/python3 data/maak-plaatsen.py [--bron <map met de zipbestanden>]
Zonder `--bron` worden de bestanden in de scratchmap gezocht en anders gedownload.
"""

import argparse
import datetime
import json
import os
import re
import sys
import urllib.request
import zipfile

HIER = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HIER)
UIT = os.path.join(HIER, "plaatsen.json")

BASIS = "https://download.geonames.org/export/dump/"
NODIG = ("NL.zip", "BE.zip", "cities15000.zip")
# De namen van de adm1-gebieden: losse tekstbestanden, geen zip.
NODIG_TEKST = ("admin1CodesASCII.txt",)
STANDAARD_BRON = os.path.expanduser("~/.hermes/cache/scratch/plaatsen")
LANDEN = ("NL", "BE")
DREMPEL_INWONERS = 100000        # buitenland: naamsvarianten vanaf deze grootte

# Een naamsvariant moet een gewone naam zijn: letters, spatie, punt, streepje of apostrof.
SCHOON = re.compile(r"^[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ' .\-]{1,29}$")

# Wat er van een streek- of gemeentenaam af gaat: dat is de soort, niet de naam.
VOORVOEGSELS = ("Provincie ", "Province de ", "Province du ", "Province ", "Gemeente ", "Gemeinde ")


def haal_op(bestandsnaam, map_):
    pad = os.path.join(map_, bestandsnaam)
    if not os.path.exists(pad):
        os.makedirs(map_, exist_ok=True)
        print(f"  ophalen: {BASIS}{bestandsnaam}")
        urllib.request.urlretrieve(BASIS + bestandsnaam, pad)
    return pad


def lees(zipnaam, lid):
    with zipfile.ZipFile(zipnaam) as z, z.open(lid) as f:
        return [r.split("\t") for r in f.read().decode("utf-8").splitlines()]


def bewoond(rij):
    return len(rij) > 17 and (rij[6] == "P" or rij[7].startswith("PPL"))


def namen_van(rij, met_varianten):
    uit = {rij[1].lower(), rij[2].lower()}
    if met_varianten:
        uit |= {a.lower() for a in rij[3].split(",") if SCHOON.match(a)}
    return {n for n in uit if n}


def schoon(naam):
    """Een streek- of gemeentenaam zonder de soort ervoor ("Gemeente Ede" -> Ede)."""
    naam = naam.strip()
    for voor in VOORVOEGSELS:
        if naam.startswith(voor):
            return naam[len(voor):].strip()
    return naam


def plaatselijke_namen(bestanden):
    """De streek- en gemeentenamen die **in de bronbestanden zelf** staan.

    Nederland en Belgie hebben allebei hun eigen indeling, dus leest elk land zijn eigen objecten:

      - NL: ADM1 = de twaalf provincies (met de Nederlandse naam: "Provincie Zuid-Holland"),
            ADM2 = de 342 gemeenten;
      - BE: ADM2 = de elf provincies, ADM4 = de 565 gemeenten (adm1 is daar alleen het gewest).

    Geeft (streek, gemeente): twee woordenboeken met code -> naam.
    """
    streek, gemeente = {}, {}
    for land in LANDEN:
        for rij in lees(bestanden[f"{land}.zip"], f"{land}.txt"):
            if len(rij) <= 17 or rij[6] != "A":
                continue
            if land == "NL":
                if rij[7] == "ADM1":
                    streek[f"NL.{rij[10]}"] = schoon(rij[1])
                elif rij[7] == "ADM2":
                    gemeente[f"NL.{rij[10]}.{rij[11]}"] = schoon(rij[1])
            else:
                if rij[7] == "ADM2":
                    streek[f"BE.{rij[10]}.{rij[11]}"] = schoon(rij[1])
                elif rij[7] == "ADM4":
                    gemeente[f"BE.{rij[10]}.{rij[11]}.{rij[13]}"] = schoon(rij[1])
    return streek, gemeente


def wereld_namen(pad):
    """adm1-code -> naam uit `admin1CodesASCII.txt` (voor alles buiten Nederland en Belgie)."""
    uit = {}
    with open(pad, encoding="utf-8") as f:
        for regel in f:
            delen = regel.rstrip("\n").split("\t")
            if len(delen) > 1:
                uit[delen[0]] = delen[1]
    return uit


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bron", default=os.environ.get("PLAATSEN_BRON", STANDAARD_BRON),
                   help="map met NL.zip, BE.zip en cities15000.zip")
    p.add_argument("--uit", default=UIT)
    args = p.parse_args()

    print("Plaatsenlijst bouwen uit GeoNames")
    bestanden = {z: haal_op(z, args.bron) for z in NODIG}
    teksten = {t: haal_op(t, args.bron) for t in NODIG_TEKST}

    streek_namen, gemeente_namen = plaatselijke_namen(bestanden)
    wereld = wereld_namen(teksten["admin1CodesASCII.txt"])
    print(f"  streken: {len(streek_namen)} provincies van NL en BE uit de bronbestanden, "
          f"{len(wereld)} adm1-namen voor de rest van de wereld")
    print(f"  gemeenten: {len(gemeente_namen)} uit de bronbestanden (NL en BE)")

    plaatsen, nummer, namen = [], {}, {}
    aantallen, streken_nr = {}, {}
    zonder = {"streek": 0, "gemeente": 0}

    def nummer_van(naam):
        """Het nummer van een streek- of gemeentenaam in de tabel; -1 als er geen naam is."""
        if not naam:
            return -1
        if naam not in streken_nr:
            streken_nr[naam] = len(streken_nr)
        return streken_nr[naam]

    def etiketten(rij):
        """De streek en de gemeente van een rij, per land uit het veld waar de bron ze heeft."""
        land = rij[8]
        if land == "NL":
            st, ge = streek_namen.get(f"NL.{rij[10]}"), gemeente_namen.get(f"NL.{rij[10]}.{rij[11]}")
        elif land == "BE":
            st = streek_namen.get(f"BE.{rij[10]}.{rij[11]}")
            ge = gemeente_namen.get(f"BE.{rij[10]}.{rij[11]}.{rij[13]}")
        else:
            st, ge = wereld.get(f"{land}.{rij[10]}"), None
        zonder["streek"] += 0 if st else 1
        zonder["gemeente"] += 0 if ge else 1
        return nummer_van(st), nummer_van(ge)

    def doe_rij(rij, met_varianten):
        merk = (rij[1], round(float(rij[4]), 5), round(float(rij[5]), 5))
        if merk not in nummer:
            nummer[merk] = len(plaatsen)
            st, ge = etiketten(rij)
            plaatsen.append([rij[1], merk[1], merk[2], rij[8], rij[17], int(rij[14] or 0), st, ge])
        i = nummer[merk]
        for naam in namen_van(rij, met_varianten):
            lijst = namen.setdefault(naam, [])
            if i not in lijst:
                lijst.append(i)

    for land in LANDEN:
        rijen = lees(bestanden[f"{land}.zip"], f"{land}.txt")
        n = 0
        for rij in rijen:
            if bewoond(rij):
                doe_rij(rij, True)
                n += 1
        aantallen[land] = n
        print(f"  {land}: {n} bewoonde plaatsen (met alle naamsvarianten)")

    rijen = lees(bestanden["cities15000.zip"], "cities15000.txt")
    n = 0
    for rij in rijen:
        doe_rij(rij, int(rij[14] or 0) >= DREMPEL_INWONERS)
        n += 1
    aantallen["wereld"] = n
    print(f"  wereld vanaf 15.000 inwoners: {n} plaatsen "
          f"(naamsvarianten vanaf {DREMPEL_INWONERS} inwoners)")

    streken = [None] * len(streken_nr)
    for naam, plek in streken_nr.items():
        streken[plek] = naam
    print(f"  streken en gemeenten samen: {len(streken)} namen in de tabel")
    print(f"  plaatsen zonder streek: {zonder['streek']}; zonder gemeente: {zonder['gemeente']}")

    inhoud = {
        "bron": "GeoNames (download.geonames.org/export/dump): NL.zip, BE.zip, cities15000.zip, "
                "admin1CodesASCII.txt",
        "licentie": "CC BY 4.0 - bronvermelding verplicht (zie https://www.geonames.org/)",
        "gebouwd": datetime.date.today().isoformat(),
        "aantal": len(plaatsen),
        "aantallen": aantallen,
        "vorm": {"plaatsen": "[naam, breedte, lengte, land, zone, inwoners, streek, gemeente] - de "
                             "laatste twee zijn nummers in `streken`, -1 = geen",
                 "streken": "streek- en gemeentenamen; de plaats verwijst er met een nummer naar",
                 "namen": "naam in kleine letters -> plaatsnummers; het eerste nummer hoort bij de "
                          "grootste plaats"},
        "etiketten": {
            "NL": "streek = provincie (adm1), gemeente = gemeente (adm2)",
            "BE": "streek = provincie (adm2), gemeente = gemeente (adm4); het gewest uit adm1 zegt "
                  "te weinig om te kiezen",
            "elders": "streek = adm1 uit admin1CodesASCII.txt, gemeente leeg",
        },
        "eigen": "plaatsen uit data/eigen-plaatsen.tsv komen er in kern/plaatsen.py overheen",
        "plaatsen": plaatsen,
        "streken": streken,
        "namen": namen,
    }
    with open(args.uit, "w", encoding="utf-8") as f:
        json.dump(inhoud, f, ensure_ascii=False)
    print(f"  {len(plaatsen)} plaatsen in {len(namen)} namen")
    print(f"  geschreven: {args.uit} ({os.path.getsize(args.uit) / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
