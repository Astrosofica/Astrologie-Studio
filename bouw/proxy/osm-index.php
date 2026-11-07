<?php
declare(strict_types=1);

/*
 * OSM-proxy voor Astrologie Studio
 * Zie wiki: ~/wiki/projects/astrologie-studio/OSM-PROXY.md
 *
 * GET /osm/?q=<plaats>&limit=5[&taal=nl]
 *
 * **Sinds 5 november 2026 (T66) is er geen sleutel meer nodig.** De sleutel zat in elke installer en
 * zei niets over wie er zocht, dus hij beschermde niets; de app vanaf 0.6.0 stuurt zijn versienummer
 * mee in de header X-Astro-Versie en verder niets. Wat de dienst beschermt is nu:
 *
 *   - een grens van 20 vragen per uur per IP (`grens_per_uur`), alleen voor vragen die echt naar
 *     Nominatim gaan - een treffer uit de cache kost niets en telt niet mee;
 *   - het tempo van één verzoek per seconde over alle gebruikers heen (de policy van Nominatim);
 *   - de lengtegrenzen op de vraag.
 *
 * De **oude sleutel wordt nog steeds geaccepteerd**, en aan de sleutel herkennen we wie er nog op 0.5.0
 * zit - dat is de enige meetbare kant van "wie is er nog niet bij". Een verouderde versie krijgt een
 * kopje `X-Astro-Verouderd: 1` in het antwoord, maar nooit een weigering: niemand wordt buitengesloten
 * (besluit 5 nov 2026). In 0.7.0 vervalt de oude sleutel.
 *
 * Deze proxy doet niets anders dan één vraag doorgeven aan Nominatim:
 * alleen q, limit en taal gaan door, het antwoord gaat ongewijzigd terug.
 * De vraag zelf wordt nergens bewaard behalve in de cache, en het access_log
 * slaat dit pad over (zie .htaccess + CustomLog ... env=!dontlog in de vhost).
 */

const MIN_LENGTE = 3;
const MAX_LENGTE = 200;
const MAX_LIMIT = 10;
const STANDAARD_LIMIT = 5;
const CACHE_DAGEN = 30;
const CACHE_MAX = 2000;
const TEMPO_SECONDEN = 1.0;   // policy Nominatim: hoogstens 1 verzoek per seconde
const WACHT_OP_SLOT = 5.0;    // seconden wachten op het temposlot voor we 429 geven
const VERBIND_TIMEOUT = 5;
const TOTAAL_TIMEOUT = 12;
const GRENS_PER_UUR = 20;     // per IP, alleen voor vragen die naar buiten gaan
const STANDAARD_MIN_VERSIE = '0.6.0';
const VERSIE_LOG_MAX = 1048576;   // 1 MB, daarna rollen naar versies.log.1

const CONFIG = __DIR__ . '/../../etc/osm-proxy.php';

function fout(int $code, string $tekst, int $retry = 0): void
{
    http_response_code($code);
    header('Content-Type: application/json; charset=utf-8');
    if ($retry > 0) {
        header('Retry-After: ' . $retry);
    }
    echo json_encode(['fout' => $tekst], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

/** Het IP van de aanvrager, gehasht - genoeg om te tellen, en er staat geen adres in de bestanden. */
function ip_sleutel(): string
{
    return substr(sha1('osm|' . (string) ($_SERVER['REMOTE_ADDR'] ?? '')), 0, 16);
}

/**
 * Telt deze vraag bij de IP-grens en stopt met 429 als het uur vol is.
 *
 * De teller staat per IP in een eigen bestand met een slot erom, want twee gelijktijdige vragen van
 * dezelfde computer zouden anders allebei "nog één" lezen. Kan de teller niet worden bijgehouden, dan
 * gaat de vraag gewoon door: een kapotte teller mag niemand buitensluiten.
 */
function tel_op(string $map, int $grens): void
{
    if ($grens < 1) {
        return;
    }
    if (!is_dir($map) && !@mkdir($map, 0750, true) && !is_dir($map)) {
        return;
    }
    $handvat = @fopen($map . '/' . ip_sleutel() . '.json', 'c+');
    if ($handvat === false) {
        return;
    }
    if (!flock($handvat, LOCK_EX)) {
        fclose($handvat);
        return;
    }
    $nu = time();
    $tijden = [];
    $ruw = json_decode((string) stream_get_contents($handvat), true);
    if (is_array($ruw)) {
        foreach ($ruw as $tijd) {
            if (is_int($tijd) && $tijd > $nu - 3600) {
                $tijden[] = $tijd;
            }
        }
    }
    if (count($tijden) >= $grens) {
        $vrij = max(60, 3600 - ($nu - (int) min($tijden)));
        flock($handvat, LOCK_UN);
        fclose($handvat);
        fout(429, 'Deze computer heeft het maximum van ' . $grens . ' zoekopdrachten per uur bereikt. '
            . 'Probeer het over ' . (int) round($vrij / 60) . ' minuten opnieuw.', $vrij);
    }
    $tijden[] = $nu;
    ftruncate($handvat, 0);
    rewind($handvat);
    fwrite($handvat, (string) json_encode($tijden));
    fflush($handvat);
    flock($handvat, LOCK_UN);
    fclose($handvat);
}

/**
 * Eén regel per vraag: wanneer, welke versie, hoe we dat weten en of het antwoord uit de cache kwam.
 *
 * De **vraag zelf komt hier niet in** - die staat alleen in de cache, zoals de afspraak is.
 */
function schrijf_versie(string $werkmap, string $versie, string $herkomst, string $bron): void
{
    $regel = implode("\t", [gmdate('Y-m-d\TH:i:s\Z'), $versie, $herkomst, $bron, ip_sleutel()]) . "\n";
    @file_put_contents($werkmap . '/versies.log', $regel, FILE_APPEND | LOCK_EX);
}

// ---- 0. configuratie -------------------------------------------------------
if (!is_file(CONFIG)) {
    fout(500, 'De proxy is niet ingesteld.');
}
$cfg = require CONFIG;
foreach (['sleutel', 'dienst', 'ua', 'werkmap'] as $sleutel) {
    if (empty($cfg[$sleutel])) {
        fout(500, 'De proxy is niet ingesteld.');
    }
}
$werkmap = rtrim($cfg['werkmap'], '/');
$cachemap = $werkmap . '/cache';
if (!is_dir($cachemap) && !@mkdir($cachemap, 0750, true) && !is_dir($cachemap)) {
    fout(500, 'De proxy heeft geen schrijfmap.');
}

// ---- 1. methode, versie en sleutel ----------------------------------------
$methode = $_SERVER['REQUEST_METHOD'] ?? 'GET';
if ($methode !== 'GET' && $methode !== 'HEAD') {
    fout(405, 'Alleen GET.');
}

// De versie komt uit de header; een oude app (0.5.0) stuurt die niet maar wel de sleutel, en dan weten
// we genoeg. Geen van beide: onbekend. **De sleutel wordt niet meer gecontroleerd** - wie hem heeft
// meegestuurd krijgt gewoon antwoord, ook als hij niet klopt; er valt niets meer te beschermen dat de
// IP-grens niet al doet.
$versie = (string) ($_SERVER['HTTP_X_ASTRO_VERSIE'] ?? '');
if (preg_match('/^\d{1,3}\.\d{1,3}(\.\d{1,3})?$/', $versie) !== 1) {
    $versie = '';
}
$sleutel = (string) ($_SERVER['HTTP_X_ASTRO_SLEUTEL'] ?? '');
if ($versie !== '') {
    $herkomst = 'header';
} elseif ($sleutel !== '' && hash_equals((string) $cfg['sleutel'], $sleutel)) {
    $versie = '0.5.0';
    $herkomst = 'sleutel';
} elseif ($sleutel !== '') {
    $versie = 'onbekend';
    $herkomst = 'vreemde-sleutel';
} else {
    $versie = 'onbekend';
    $herkomst = 'geen';
}
$minVersie = (string) ($cfg['min_versie'] ?? STANDAARD_MIN_VERSIE);
$verouderd = preg_match('/^\d/', $versie) === 1 && version_compare($versie, $minVersie, '<');
header('X-Astro-Versie: ' . $versie);
if ($verouderd) {
    // Een vlag, geen weigering: de app mag zeggen dat er een nieuwere versie is, maar blijft werken.
    header('X-Astro-Verouderd: 1');
    header('X-Astro-Min-Versie: ' . $minVersie);
}

// ---- 2. de vraag ----------------------------------------------------------
$q = (string) ($_GET['q'] ?? '');
$q = preg_replace('/\s+/u', ' ', trim($q)) ?? '';
if (preg_match('/[\x00-\x1F\x7F]/u', $q) === 1) {
    fout(400, 'De zoektekst bevat ongeldige tekens.');
}
if (mb_strlen($q) < MIN_LENGTE) {
    fout(400, 'De zoektekst is te kort.');
}
if (mb_strlen($q) > MAX_LENGTE) {
    fout(400, 'De zoektekst is te lang.');
}

$limit = filter_var($_GET['limit'] ?? STANDAARD_LIMIT, FILTER_VALIDATE_INT);
if ($limit === false || $limit < 1) {
    $limit = STANDAARD_LIMIT;
}
$limit = min($limit, MAX_LIMIT);

$taal = (string) ($_GET['taal'] ?? 'nl');
if (preg_match('/^[A-Za-z]{2,8}([-_][A-Za-z0-9]{1,8})?$/', $taal) !== 1) {
    $taal = 'nl';
}

// ---- 3. cache ------------------------------------------------------------
$sleutelCache = sha1('v1|' . mb_strtolower($q) . '|' . $limit . '|' . $taal);
$cachebestand = $cachemap . '/' . substr($sleutelCache, 0, 2) . '/' . $sleutelCache . '.json';

if (is_file($cachebestand) && (time() - (int) @filemtime($cachebestand)) < CACHE_DAGEN * 86400) {
    $bewaard = @file_get_contents($cachebestand);
    if ($bewaard !== false) {
        $rij = json_decode($bewaard, true);
        if (is_array($rij) && isset($rij['antwoord']) && is_string($rij['antwoord'])) {
            schrijf_versie($werkmap, $versie, $herkomst, 'cache');
            header('Content-Type: application/json; charset=utf-8');
            header('X-Astro-Cache: hit');
            echo $rij['antwoord'];
            exit;
        }
    }
}

// ---- 4. IP-grens: twintig vragen per uur ----------------------------------
// Pas hier, na de cache: een herhaalde vraag kost Nominatim niets en mag dus niets kosten.
tel_op($werkmap . '/teller', (int) ($cfg['grens_per_uur'] ?? GRENS_PER_UUR));

// ---- 5. tempo: één verzoek per seconde over alle gebruikers --------------
$slot = @fopen($werkmap . '/tempo.lock', 'c');
if ($slot === false) {
    fout(500, 'De proxy heeft geen temposlot.');
}
$deadline = microtime(true) + WACHT_OP_SLOT;
while (!flock($slot, LOCK_EX | LOCK_NB)) {
    if (microtime(true) > $deadline) {
        fout(429, 'Te veel zoekopdrachten kort na elkaar. Probeer het over een paar seconden opnieuw.', 3);
    }
    usleep(50000);
}

$stempel = $werkmap . '/tempo.stamp';
$vorig = is_file($stempel) ? (float) @file_get_contents($stempel) : 0.0;
$wacht = TEMPO_SECONDEN - (microtime(true) - $vorig);
if ($wacht > 0) {
    usleep((int) round($wacht * 1e6));
}
@file_put_contents($stempel, (string) microtime(true));

// ---- 6. Nominatim --------------------------------------------------------
$url = $cfg['dienst'] . '?' . http_build_query([
    'q' => $q,
    'format' => 'jsonv2',
    'addressdetails' => 1,
    'limit' => $limit,
    'accept-language' => $taal,
], '', '&', PHP_QUERY_RFC3986);

$antwoord = false;
$status = 0;
$fouttekst = '';
for ($poging = 1; $poging <= 2; $poging++) {
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_USERAGENT => (string) $cfg['ua'],
        CURLOPT_CONNECTTIMEOUT => VERBIND_TIMEOUT,
        CURLOPT_TIMEOUT => TOTAAL_TIMEOUT,
        CURLOPT_FOLLOWLOCATION => false,
        CURLOPT_ENCODING => '',
        CURLOPT_HTTPHEADER => ['Accept: application/json'],
    ]);
    $antwoord = curl_exec($ch);
    $status = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $fouttekst = curl_error($ch);
    curl_close($ch);

    if ($status >= 200 && $status < 300) {
        break;
    }
    // 403/429 van Nominatim: één keer opnieuw, langzamer. Verder niets herhalen.
    if (($status === 403 || $status === 429) && $poging === 1) {
        sleep(2);
        continue;
    }
    break;
}

flock($slot, LOCK_UN);
fclose($slot);

schrijf_versie($werkmap, $versie, $herkomst, 'nominatim');

if ($antwoord === false) {
    fout(502, 'Nominatim is niet bereikbaar.');
}
if ($status === 403 || $status === 429) {
    fout(429, 'Nominatim houdt ons even tegen. Probeer het later opnieuw.', 30);
}
if ($status < 200 || $status >= 300) {
    fout(502, 'Nominatim gaf een fout (' . $status . ').');
}
if (!is_string($antwoord) || json_decode($antwoord, true) === null) {
    fout(502, 'Nominatim gaf geen leesbaar antwoord.');
}

// ---- 7. bewaren en doorgeven (antwoord ongewijzigd) ----------------------
$map = dirname($cachebestand);
if (!is_dir($map)) {
    @mkdir($map, 0750, true);
}
$regel = json_encode(
    ['tijd' => time(), 'vraag' => $q, 'antwoord' => $antwoord],
    JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES
);
if (is_string($regel)) {
    $tijdelijk = $cachebestand . '.' . getmypid() . '.tmp';
    if (@file_put_contents($tijdelijk, $regel) !== false) {
        @rename($tijdelijk, $cachebestand);
    } else {
        @unlink($tijdelijk);
    }
}

// Opruimen: met kleine kans oude regels weghalen (nooit blokkerend).
if (random_int(1, 20) === 1) {
    $grens = time() - CACHE_DAGEN * 86400;
    $alle = glob($cachemap . '/*/*.json') ?: [];
    if (count($alle) > CACHE_MAX) {
        usort($alle, static fn ($a, $b) => filemtime($a) <=> filemtime($b));
        foreach (array_slice($alle, 0, count($alle) - CACHE_MAX) as $oud) {
            @unlink($oud);
        }
    } else {
        foreach ($alle as $bestand) {
            if ((int) @filemtime($bestand) < $grens) {
                @unlink($bestand);
            }
        }
    }
    // Tellers van meer dan twee uur oud zeggen niets meer.
    foreach (glob($werkmap . '/teller/*.json') ?: [] as $teller) {
        if ((int) @filemtime($teller) < time() - 7200) {
            @unlink($teller);
        }
    }
    // Het versielog mag niet onbeperkt groeien.
    if (is_file($werkmap . '/versies.log') && (int) @filesize($werkmap . '/versies.log') > VERSIE_LOG_MAX) {
        @rename($werkmap . '/versies.log', $werkmap . '/versies.log.1');
    }
}

header('Content-Type: application/json; charset=utf-8');
header('X-Astro-Cache: miss');
echo $antwoord;
