"""Tijd en tijdzones voor de rekenkern.

Overgebracht uit `public_html`/`src/Time/AstroTime.php` van Astrosofica/Horoscoopberekening
(AGPL-3.0, eigen werk, besluit T17/T19). De Nederlandse en Belgische tabellen zijn
letterlijk overgenomen; IANA komt hier uit `zoneinfo` in plaats van uit PHP's DateTimeZone.

Werkwijze (gelijk aan zijn programma): de ingevoerde tijd is kloktijd ter plaatse. Die wordt
eerst als UTC behandeld (`local_ts`), daarmee wordt de offset opgezocht, en de echte UTC is
`local_ts - offset`. Bij een server op UTC is dat precies wat `calculate-horoscope.php` doet.
"""

from __future__ import annotations

import datetime as _dt
import zoneinfo

SECONDS_PER_DEGREE = 240
MIN_TIMESTAMP = -5364662400   # ~1800 CE
MAX_TIMESTAMP = 13569465599   # ~2399 CE

TZ_AMSTERDAM = "Europe/Amsterdam"
TZ_BRUSSELS = "Europe/Brussels"

# Het nulpunt van de epoch, als bewuste UTC-datetime.
EPOCH = _dt.datetime(1970, 1, 1, tzinfo=_dt.timezone.utc)


def van_epoch(ts):
    """Epoch-seconden -> een bewuste UTC-datetime, **zonder** de C-bibliotheek.

    `datetime.fromtimestamp()` gaat op Windows door de C-functie `gmtime`, en die weigert
    negatieve waarden met `OSError: [Errno 22] Invalid argument`. Gevolg: elke horoscoop vóór
    1 januari 1970 valt op Windows om, terwijl dezelfde kaart op Linux gewoon rekent - en de
    zelfcontrole merkt er niets van, want die gebruikt een ijkpunt uit 1985 (positief).

    Rekenen met de epoch is gewone datumaritmetiek: dezelfde uitkomst op elk systeem, geen
    platformafhankelijke C-functie ertussen. Gemeten met dertien datums van
    1800 tot 2399: alle standen bleven tot op de laatste decimaal gelijk.
    """
    return EPOCH + _dt.timedelta(seconds=ts)

# --- Nederlandse tabel (UTC-sleutel -> offset in seconden) -----------------------------------
NL_TABLE = {
    "1909-04-30 23:40:28": 1172,
    "1916-04-30 23:40:28": 4772, "1916-09-30 22:40:28": 1172,
    "1917-04-16 01:40:28": 4772, "1917-09-16 01:40:28": 1172,
    "1918-04-01 01:40:28": 4772, "1918-09-29 01:40:28": 1172,
    "1919-04-07 01:40:28": 4772, "1919-09-28 01:40:28": 1172,
    "1920-04-05 01:40:28": 4772, "1920-09-26 01:40:28": 1172,
    "1921-04-04 01:40:28": 4772, "1921-10-02 01:40:28": 1172,
    "1922-03-26 01:40:28": 4772, "1922-10-08 01:40:28": 1172,
    "1923-04-22 01:40:28": 4772, "1923-10-07 01:40:28": 1172,
    "1924-03-30 01:40:28": 4772, "1924-10-05 01:40:28": 1172,
    "1925-04-19 01:40:28": 4772, "1925-10-04 01:40:28": 1172,
    "1926-05-15 01:40:28": 4772, "1926-10-03 01:40:28": 1172,
    "1927-05-15 01:40:28": 4772, "1927-10-02 01:40:28": 1172,
    "1928-05-15 01:40:28": 4772, "1928-10-07 01:40:28": 1172,
    "1929-05-15 01:40:28": 4772, "1929-10-06 01:40:28": 1172,
    "1930-05-15 01:40:28": 4772, "1930-10-05 01:40:28": 1172,
    "1931-05-15 01:40:28": 4772, "1931-10-04 01:40:28": 1172,
    "1932-05-22 01:40:28": 4772, "1932-10-02 01:40:28": 1172,
    "1933-05-15 01:40:28": 4772, "1933-10-08 01:40:28": 1172,
    "1934-05-15 01:40:28": 4772, "1934-10-07 01:40:28": 1172,
    "1935-05-15 01:40:28": 4772, "1935-10-06 01:40:28": 1172,
    "1936-05-15 01:40:28": 4772, "1936-10-04 01:40:28": 1172,
    "1937-05-22 01:40:28": 4772,
    "1937-06-30 22:40:28": 4800,
    "1937-10-03 01:40:00": 1200,
    "1938-05-15 01:40:00": 4800,
    "1938-10-02 01:40:00": 1200,
    "1939-05-15 01:40:00": 4800,
    "1939-10-08 01:40:00": 1200,
    "1940-05-15 23:40:00": 7200,
    "1941-10-05 01:00:00": 3600,
    "1942-03-09 01:00:00": 7200, "1942-11-02 01:00:00": 3600,
    "1943-03-29 01:00:00": 7200, "1943-10-04 01:00:00": 3600,
    "1944-04-03 01:00:00": 7200, "1944-10-02 01:00:00": 3600,
    "1945-04-02 01:00:00": 7200, "1945-09-16 01:00:00": 3600,
}

# --- Belgische tabel -------------------------------------------------------------------------
BE_TABLE = {
    "1892-05-01 00:00:00": 0,    "1914-08-04 00:00:00": 3600, "1916-04-30 23:00:00": 7200,
    "1916-09-30 23:00:00": 3600, "1917-04-16 01:00:00": 7200, "1917-09-17 01:00:00": 3600,
    "1918-04-15 01:00:00": 7200, "1918-09-16 01:00:00": 3600, "1918-11-11 00:00:00": 0,
    "1919-03-01 23:00:00": 3600,
    "1919-10-04 23:00:00": 0,    "1920-02-14 23:00:00": 3600, "1920-10-23 23:00:00": 0,
    "1921-03-14 23:00:00": 3600, "1921-10-25 23:00:00": 0,    "1922-03-25 23:00:00": 3600,
    "1922-10-07 23:00:00": 0,    "1923-04-21 23:00:00": 3600, "1923-10-06 23:00:00": 0,
    "1924-03-29 23:00:00": 3600, "1924-10-04 23:00:00": 0,    "1925-04-04 23:00:00": 3600,
    "1925-10-03 23:00:00": 0,    "1926-04-17 23:00:00": 3600, "1926-10-02 23:00:00": 0,
    "1927-04-09 23:00:00": 3600, "1927-10-01 23:00:00": 0,    "1928-04-14 23:00:00": 3600,
    "1928-10-07 02:00:00": 0,    "1929-04-21 02:00:00": 3600, "1929-10-06 02:00:00": 0,
    "1930-04-13 02:00:00": 3600, "1930-10-05 02:00:00": 0,    "1931-04-19 02:00:00": 3600,
    "1931-10-04 02:00:00": 0,    "1932-04-03 02:00:00": 3600, "1932-10-02 02:00:00": 0,
    "1933-03-26 02:00:00": 3600, "1933-10-08 02:00:00": 0,    "1934-04-08 02:00:00": 3600,
    "1934-10-07 02:00:00": 0,    "1935-03-31 02:00:00": 3600, "1935-10-06 02:00:00": 0,
    "1936-04-19 02:00:00": 3600, "1936-10-04 02:00:00": 0,    "1937-04-04 02:00:00": 3600,
    "1937-10-03 02:00:00": 0,    "1938-03-27 02:00:00": 3600, "1938-10-02 02:00:00": 0,
    "1939-04-16 02:00:00": 3600, "1939-11-19 02:00:00": 0,    "1940-02-25 02:00:00": 3600,
    "1940-05-20 02:00:00": 7200, "1942-11-02 01:00:00": 3600, "1943-03-29 01:00:00": 7200,
    "1943-10-04 01:00:00": 3600, "1944-04-03 01:00:00": 7200, "1944-09-17 01:00:00": 3600,
    "1945-04-02 01:00:00": 7200, "1945-09-16 01:00:00": 3600, "1946-05-19 01:00:00": 7200,
    "1946-10-07 01:00:00": 3600,
}

_NL_KEYS = sorted(NL_TABLE, reverse=True)
_BE_KEYS = sorted(BE_TABLE, reverse=True)


def _table_offset(table_keys, table, utc_str):
    for key in table_keys:
        if utc_str >= key:
            return table[key]
    return None


def _str_from_ts(ts):
    return van_epoch(ts).strftime("%Y-%m-%d %H:%M:%S")


# --- De afkorting die de gebruiker leest ------------------------------------------------------
# De IANA-database levert de Engelse vormen (CET/CEST); de eigen tabel hierboven gebruikt voor
# 1940-1945 en voor Belgie al MEST/MET. Twee systemen naast elkaar betekent dat dezelfde plaats in
# het ene jaar "CET" leest en in het andere "MET" - en dat verschil zie je terug. Een tabel
# met de Nederlandse vormen, toegepast op elke plek waar een label vandaan komt, zodat er niet
# opnieuw drie systemen ontstaan. Historische namen (AMT, AMST, NT, NST, BMT) blijven staan: dat zijn
# de namen die in de literatuur bij die tijdperken horen. "UTC" wordt "UT": het formulier zegt ook UT.
# "LMT" wordt "WPT": de cursus noemt de tijd die bij de lengtegraad hoort de **ware plaatselijke
# tijd**. Het rekenwerk blijft gelijk - lengtegraad x 4 minuten - en dat is precies
# wat de handmatige berekening ook doet.
NL_AFKORTING = {"CET": "MET", "CEST": "MEZT", "MEST": "MEZT", "UTC": "UT", "LMT": "WPT"}


def _label(afkorting):
    """De afkorting zoals de gebruiker hem leest (Nederlands)."""
    return NL_AFKORTING.get(afkorting, afkorting)


def get_offset(timezone_id, longitude, timestamp):
    """Levert {offset, source, label} voor een UTC-tijdstip (`timestamp` als epoch).

    Let op: de NL/BE-tabellen worden - net als in het PHP-programma - opgezocht met de
    kloktijd die als UTC is behandeld, niet met de echte UTC. Dat is de bestaande praktijk
    en het scheelt hoogstens nabij een overgang.
    """
    # Buiten 1800-2399 zeggen de tabellen niets, maar de zones wel. Zonder deze tak geeft het een kale
    # fout met offset 0 - en dus een kaart die stil met de verkeerde UT rekent ("12:00:00
    # OUT_OF_RANGE" op de A4). Daarom rekent het door: vóór 1909 geeft de Nederlandse tak de zonnetijd
    # van de plaats (LMT), en anders neemt zoneinfo het over, die voor oude data zijn eigen LMT-regel
    # heeft. Dat hoort bij het doorrekenen met de Moshier-benadering.

    if timezone_id == TZ_AMSTERDAM:
        res = _netherlands(timezone_id, longitude, timestamp)
        if res is not None:
            return res
    if timezone_id == TZ_BRUSSELS:
        res = _belgium(timezone_id, longitude, timestamp)
        if res is not None:
            return res
    return _iana(timezone_id, longitude, timestamp)


def _netherlands(_tz, longitude, timestamp):
    utc_str = _str_from_ts(timestamp)
    year = int(utc_str[:4])
    if utc_str < "1909-04-30 23:40:28":
        return {"offset": int(round(longitude * SECONDS_PER_DEGREE)),
                "source": "Manual NL: LMT (Plaatselijke tijd)", "label": _label("LMT")}
    if year <= 1945:
        offset = _table_offset(_NL_KEYS, NL_TABLE, utc_str)
        if offset is None:
            offset = 1172
        if year < 1937 or (year == 1937 and utc_str < "1937-06-30 22:40:28"):
            label = "AMST" if offset > 1200 else "AMT"
        elif year < 1940 or (year == 1940 and utc_str < "1940-05-15 23:40:00"):
            label = "NST" if offset > 1200 else "NT"
        else:
            label = "MEST" if offset >= 7200 else "MET"
        return {"offset": offset, "source": "Manual NL: High-Precision UTC Table",
                "label": _label(label)}
    return None


def _belgium(_tz, longitude, timestamp):
    utc_str = _str_from_ts(timestamp)
    year = int(utc_str[:4])
    if utc_str < "1880-05-01 00:00:00":
        return {"offset": int(round(longitude * SECONDS_PER_DEGREE)),
                "source": "Manual BE: LMT", "label": _label("LMT")}
    if utc_str < "1892-05-01 00:00:00":
        return {"offset": 1049, "source": "Manual BE: Brussels Meridian", "label": "BMT"}
    if utc_str < "1947-01-01 00:00:00":
        offset = _table_offset(_BE_KEYS, BE_TABLE, utc_str)
        if offset is None:
            offset = 0
        if year < 1940:
            label = "GMT+DST" if offset > 0 else "GMT"
        else:
            label = "MEST" if offset >= 7200 else "MET"
        return {"offset": offset, "source": "Manual BE: Official Table (KSB)", "label": _label(label)}
    return None


def _iana(timezone_id, longitude, timestamp):
    try:
        tz = zoneinfo.ZoneInfo(timezone_id)
    except Exception:
        return {"offset": int(round(longitude * SECONDS_PER_DEGREE)),
                "source": "Fallback LMT (onbekende zone)", "label": _label("LMT")}
    dt = van_epoch(timestamp)
    local = dt.astimezone(tz)
    offset = int(local.utcoffset().total_seconds())
    abbr = local.tzname() or "UNKNOWN"
    if abbr == "LMT":
        return {"offset": int(round(longitude * SECONDS_PER_DEGREE)),
                "source": "Auto LMT (location-based)", "label": _label("LMT")}
    return {"offset": offset, "source": "IANA Database", "label": _label(abbr)}


def lmt_offset(longitude):
    return int(round(longitude * SECONDS_PER_DEGREE))


def local_to_utc(year, month, day, hour, minute, second, timezone_id, longitude,
                 time_correction=None):
    """Kloktijd ter plaatse -> UTC. `time_correction`: None, 'utc' of 'lmt'."""
    local_ts = int(_dt.datetime(year, month, day, hour, minute, second,
                               tzinfo=_dt.timezone.utc).timestamp())
    if time_correction == "utc":
        return local_ts, {"offset": 0, "source": "manual", "label": "UT"}
    if time_correction == "lmt":
        off = lmt_offset(longitude)
        return local_ts - off, {"offset": off, "source": "manual", "label": _label("LMT")}
    res = get_offset(timezone_id, longitude, local_ts)
    return local_ts - res["offset"], res


def fmt_offset(seconds):
    sign = "+" if seconds >= 0 else "-"
    s = abs(int(seconds))
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    parts = []
    if h:
        parts.append(f"{h} u")
    if m:
        parts.append(f"{m} min")
    if s:
        parts.append(f"{s} sec")
    if not parts:
        parts.append("0 sec")
    return sign + " ".join(parts)
