#!/usr/bin/env python3
"""Schrijft `bouw/versie.iss`: het versienummer en de bronzip voor de Inno Setup-spec.

Waarom een apart stapje: het nummer staat in `kern/versie.py`, en de installer mag daar niet zijn
eigen kopie van hebben. Dit script leest de ene waarheid en de nieuwste bronzip uit `uitgave/`, en
schrijft ze in een `.iss`-bestandje dat `astrologie-studio.iss` inleest. Eén nummer, en de installer
kan het niet oneens zijn met het programma.

Ontbreekt de bronzip, dan stopt dit script met een fout. Dat is met opzet: de AGPL-3.0 vraagt dat de
bron meegaat met iedere verspreiding, en een installer bouwen zonder bron erbij is de belofte in de
Over-tab breken. Liever hier stuk dan een installer die niet klopt.

Draaien:  python bouw/maak-versie-iss.py                (voor de installer: eist een bronzip)
          python bouw/maak-versie-iss.py --alleen-versie  (voor de .exe: versienummer alleen)

Twee uitkomsten:

- `versie-info.txt` — het versienummer in de eigenschappen van de .exe (rechtsklik > Eigenschappen >
  Details). Dit kan altijd geschreven worden.
- `versie.iss` — versienummer plus de naam van de bronzip, voor de installer. Dit eist een bronzip,
  want een installer zonder bron erbij is de AGPL-3.0 niet nakomen. Vandaar `--alleen-versie` voor de
  bouw van de .exe zelf, die de zip niet nodig heeft.
"""

from __future__ import annotations

import glob
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HIER)
sys.path.insert(0, PROJECT)

from kern.versie import VERSIE        # noqa: E402

DOEL = os.path.join(HIER, "versie.iss")
# Hetzelfde nummer in de eigenschappen van de .exe (rechtsklik > Eigenschappen > Details). Alleen op
# Windows gebruikt; PyInstaller leest dit bestand via `version=` in de spec.
DOEL_VERSIEINFO = os.path.join(HIER, "versie-info.txt")


def nieuwste_bronzip():
    """De bronzip die bij deze uitgave hoort: de nieuwste in uitgave/."""
    zips = glob.glob(os.path.join(PROJECT, "uitgave", "astrologie-studio-bron-*.zip"))
    if not zips:
        return None
    return max(zips, key=os.path.getmtime)


def main():
    alleen_versie = "--alleen-versie" in sys.argv[1:]

    delen = ([int(x) for x in VERSIE.split(".")] + [0, 0, 0, 0])[:4]   # altijd vier getallen
    velden = {
        "CompanyName": "Mercurieus",
        "FileDescription": "Astrologie Studio",
        "FileVersion": VERSIE,
        "InternalName": "astrologie-studio",
        "LegalCopyright": "AGPL-3.0",
        "OriginalFilename": "Astrologie Studio.exe",
        "ProductName": "Astrologie Studio",
        "ProductVersion": VERSIE,
    }
    strings = ", ".join("StringStruct('%s', '%s')" % (k, v) for k, v in velden.items())
    with open(DOEL_VERSIEINFO, "w", encoding="utf-8") as f:
        f.write(
            "VSVersionInfo(\n"
            "  ffi=FixedFileInfo(filevers=(%d,%d,%d,%d), prodvers=(%d,%d,%d,%d), mask=0x3f, "
            "flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0,0)),\n"
            "  kids=[StringFileInfo([StringTable('040904B0', [%s])]), "
            "VarFileInfo([VarStruct('Translation', [1033, 1200])])]\n"
            ")\n" % (*delen, *delen, strings))
    print("versie-info.txt: versie %s in de eigenschappen van de .exe" % VERSIE)

    zip_pad = nieuwste_bronzip()
    if not zip_pad:
        if alleen_versie:
            return 0
        sys.stderr.write(
            "FOUT: er staat geen bronzip in uitgave/.\n"
            "Maak hem eerst op de server:  bash bouw/maak-bronzip.sh\n"
            "Zonder bronzip geen installer: de AGPL-3.0 vraagt dat de bron meegaat.\n")
        return 1
    naam = os.path.basename(zip_pad)
    inhoud = (
        "; Automatisch geschreven door bouw/maak-versie-iss.py - niet met de hand aanpassen.\n"
        "; Het nummer komt uit kern/versie.py, de zip uit uitgave/ (de nieuwste).\n"
        '#define AppVersie "%s"\n'
        '#define BronZip "%s"\n' % (VERSIE, naam))
    with open(DOEL, "w", encoding="utf-8") as f:
        f.write(inhoud)
    print("versie.iss: versie %s, bronzip %s" % (VERSIE, naam))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
