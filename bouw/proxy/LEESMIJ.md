# De OSM-proxy, als kopie van wat er draait

`osm-index.php` is de **kopie** van `public_html/osm/index.php` in de docroot van studio.astrosofica.nl
op t640. Het echte bestand staat daar; deze kopie staat hier zodat een wijziging aan een script dat op een
publieke server draait te lezen en te vergelijken is voordat hij uitgaat.

Wat hier **niet** staat en ook niet hoort te staan:

- `etc/osm-proxy.php` — de sleutel, de dienst-URL en de werkmap. Dat bestand staat buiten de docroot op
  t640 en wordt nooit meegebundeld.
- de cache, de tellers en `versies.log` in `tmp/osm/`.

Uitrollen: eerst als `index-nieuw.php` ernaast leggen, `php8.3 -l` erop, met `curl` beproeven, en pas
daarna met `mv` over `index.php` heen. De oude versie gaat naar `~/backups/osm/` — **niet** in de docroot
laten staan (een `.php`-bestand met een andere naam geeft daar een 500).

Achtergrond, proeven en de afspraken: `~/wiki/projects/astrologie-studio/OSM-PROXY.md`.
