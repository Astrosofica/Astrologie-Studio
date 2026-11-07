"""Het versienummer van Astrologie Studio - één waarheid voor programma, installer en bestandsnaam.

Waarom dit bestand bestaat: hetzelfde nummer staat op drie plekken nodig, en die mogen het niet oneens
kunnen worden. In het programma (Over-venster en `/api/leeft`), in de installer (Windows toont het bij
"Apps en onderdelen" en het hoort in de bestandsnaam van de setup), en in de documentatie.

`bouw/maak-versie-iss.py` leest deze waarde en schrijft hem in `bouw/versie.iss`, dat de Inno
Setup-spec inleest. Wie het nummer verhoogt, verhoogt het hier - en nergens anders.

De opbouw is `<major>.<minor>.<patch>`, en de betekenis die we eraan geven:

- **0.x** — pre-alpha/beta: het programma werkt, maar de vorm kan nog veranderen en er kunnen dingen
  ontbreken. Er is geen belofte dat een bewaarde horoscoop uit een vorige 0.x-versie blijft werken.
- **1.0** — de eerste versie die naar cursisten gaat en waarvan we vinden dat hij af is.
- **patch** — een reparatie zonder nieuwe functies.

Het nummer gaat mee in de bestandsnaam van de setup (`astrologie-studio-0.1.0-setup.exe`), zodat twee
versies naast elkaar op een schijf te herkennen zijn zonder ze te openen.
"""

VERSIE = "0.6.0"

# Het jaar waar de versie bij hoort, voor de leesbaarheid in het Over-venster en het verslag.
VERSIE_JAAR = "2026"
