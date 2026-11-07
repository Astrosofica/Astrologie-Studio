"""Het venster van het programma besturen via de Windows-API.

Waarom dit bestaat: met de vlaggen van de browser kwamen we er niet. Drie metingen op Windows 11
met Edge 156 (scherm 1920x1080, werkgebied 1920x1032, 96 dpi):

  * `--start-maximized` maximaliseert wel, maar zet als **herstelmaat** Chromium's eigen standaard
    (gemeten 945x1012 - de halve breedte op bijna de volle hoogte). Dat is precies het halve scherm
    dat je ziet als je vanuit gemaximaliseerd op "kleiner" klikt.
  * `--window-size` erbij: **die wint**, en dan opent het venster gewoon op die maat in plaats van
    gemaximaliseerd.
  * Een browser die al draait negeert de venstervlaggen van een tweede `--app=`-start helemaal.

`SetWindowPlacement` zet de stand **en** de herstelmaat in één aanroep, ook op een venster dat al
bestaat. Gemeten op dezelfde machine: start 700x500 -> `SetWindowPlacement(max, herstel
800x600@40,40)` -> gemaximaliseerd, en na herstellen precies 800x600 op 40,40. Ook toen de browser al
draaide. Voor volledig scherm werkt F11 insturen; na nog een F11 komt het venster terug op de gezette
herstelmaat.

Alleen op Windows: elders doet deze module niets en zegt ze dat ook. `ctypes` zit standaard in Python,
dus er komt geen pakket bij in de bundel. De Windows-onderdelen worden pas bij gebruik opgezocht
(`_koppel`), zodat dit bestand ook op Linux gewoon te importeren is - de ijkproeven draaien daar.

Over de eenheden: de maten komen van de pagina in **CSS-pixels**, en deze API rekent in de eenheid van
het proces. Die twee zijn niet altijd gelijk: bij weergave boven 100 % werkt een schaalbewust proces in
beeldpunten, en dan wordt `1440 x 900` een venster van `1200 x 751` (1440 / 1,2). Daarom rekent
`_schaal()` de
verhouding uit twee getallen die we allebei hebben - de monitor die de API ziet gedeeld door de
schermbreedte die de pagina meldt - in plaats van hem aan te nemen. Het maakt daarbij niet uit of het
proces schaalbewust is: de verhouding klopt in beide gevallen, want de teller komt uit dezelfde
eenheid als de aanroep.
"""

import ctypes
import os
import time

# Hoe lang we op het venster wachten, en hoe vaak we kijken. De browser heeft een seconde of twee
# nodig voor het venster er staat; langer wachten betekent alleen dat een mislukking later opvalt.
WACHT = 15.0
STAP = 0.25

# De standen van WINDOWPLACEMENT.showCmd en de twee boodschappen die we zelf sturen.
SW_SHOWNORMAL = 1
SW_SHOWMAXIMIZED = 3
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
VK_F11 = 0x7A
MONITOR_DEFAULTTONEAREST = 2
SM_CXSCREEN = 0

STAND_GEWOON = "gewoon"
STAND_GEMAXIMALISEERD = "gemaximaliseerd"
STAND_VOLLEDIG = "volledig"

# De sleutel waarin de schil haar kenmerk in het adres zet. De pagina zet dat kenmerk in de
# venstertitel, zodat we bij twee vensters het juiste pakken (zie `schil/static/index.html`).
TOKEN_SLEUTEL = "vt"


class _Punt(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class _Rechthoek(ctypes.Structure):
    _fields_ = [("links", ctypes.c_long), ("boven", ctypes.c_long),
                ("rechts", ctypes.c_long), ("onder", ctypes.c_long)]


class _Plaatsing(ctypes.Structure):
    """WINDOWPLACEMENT: de stand plus de maat waar "kleiner" naar terugvalt."""

    _fields_ = [("lengte", ctypes.c_uint), ("vlaggen", ctypes.c_uint), ("stand", ctypes.c_uint),
                ("min_punt", _Punt), ("max_punt", _Punt), ("herstel", _Rechthoek)]


class _Monitorinfo(ctypes.Structure):
    _fields_ = [("omvang", ctypes.c_ulong), ("monitor", _Rechthoek), ("werkblad", _Rechthoek),
                ("vlaggen", ctypes.c_ulong)]


_API = None
_TERUG = None
_GEPROBEERD = False


def beschikbaar() -> bool:
    """Kan deze module hier iets doen?"""
    return os.name == "nt"


def token() -> str:
    """Een kenmerk dat dit venster van alle andere onderscheidt."""
    return "as%d" % os.getpid()


def _koppel():
    """De Windows-functies klaarzetten. None als dat hier niet kan."""
    global _API, _TERUG, _GEPROBEERD
    if _GEPROBEERD:
        return _API
    _GEPROBEERD = True
    if not beschikbaar():
        return None
    try:
        from ctypes import wintypes
        gebruiker = ctypes.WinDLL("user32", use_last_error=True)
        _TERUG = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    except (ImportError, OSError, AttributeError, ValueError):
        return None

    gebruiker.EnumWindows.argtypes = [_TERUG, wintypes.LPARAM]
    gebruiker.EnumWindows.restype = wintypes.BOOL
    gebruiker.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    gebruiker.GetWindowTextW.restype = ctypes.c_int
    gebruiker.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    gebruiker.GetWindowTextLengthW.restype = ctypes.c_int
    gebruiker.IsWindowVisible.argtypes = [wintypes.HWND]
    gebruiker.IsWindowVisible.restype = wintypes.BOOL
    gebruiker.GetWindowPlacement.argtypes = [wintypes.HWND, ctypes.POINTER(_Plaatsing)]
    gebruiker.GetWindowPlacement.restype = wintypes.BOOL
    gebruiker.SetWindowPlacement.argtypes = [wintypes.HWND, ctypes.POINTER(_Plaatsing)]
    gebruiker.SetWindowPlacement.restype = wintypes.BOOL
    gebruiker.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(_Rechthoek)]
    gebruiker.GetWindowRect.restype = wintypes.BOOL
    gebruiker.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
                                       wintypes.LPARAM]
    gebruiker.PostMessageW.restype = wintypes.BOOL
    gebruiker.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    gebruiker.MonitorFromWindow.restype = wintypes.HANDLE
    gebruiker.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_Monitorinfo)]
    gebruiker.GetMonitorInfoW.restype = wintypes.BOOL
    # Sinds Windows 10 1607: de dpi van de monitor waar het venster staat. Zonder argtypes zou ctypes
    # het vensterhandvat als c_int doorgeven, en dat gaat op een 64-bits venster mis.
    gebruiker.GetDpiForWindow.argtypes = [wintypes.HWND]
    gebruiker.GetDpiForWindow.restype = wintypes.UINT
    gebruiker.GetSystemMetrics.argtypes = [ctypes.c_int]
    gebruiker.GetSystemMetrics.restype = ctypes.c_int
    _API = gebruiker
    return _API


def _titel(api, hwnd) -> str:
    lengte = api.GetWindowTextLengthW(hwnd)
    if lengte <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(lengte + 1)
    api.GetWindowTextW(hwnd, buf, lengte + 1)
    return buf.value


def zoek(titel_deel, wacht=WACHT):
    """Het venster waarvan de titel dit stuk tekst bevat, of None."""
    api = _koppel()
    if api is None or not titel_deel:
        return None
    gezocht = titel_deel.lower()
    eind = time.monotonic() + wacht
    while time.monotonic() < eind:
        gevonden = []

        def kijk(hwnd, _):
            if not api.IsWindowVisible(hwnd):
                return True
            if gezocht in _titel(api, hwnd).lower():
                gevonden.append(hwnd)
                return False
            return True

        api.EnumWindows(_TERUG(kijk), 0)
        if gevonden:
            return gevonden[0]
        time.sleep(STAP)
    return None


def _plaatsing(api, hwnd):
    p = _Plaatsing()
    p.lengte = ctypes.sizeof(_Plaatsing)
    if not api.GetWindowPlacement(hwnd, ctypes.byref(p)):
        return None
    return p


def _buiten(api, hwnd):
    r = _Rechthoek()
    if not api.GetWindowRect(hwnd, ctypes.byref(r)):
        return None
    return r


def _monitor(api, hwnd):
    """Het werkblad (scherm min taakbalk) van de monitor waar het venster staat."""
    monitor = api.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
    info = _Monitorinfo()
    info.omvang = ctypes.sizeof(_Monitorinfo)
    if not monitor or not api.GetMonitorInfoW(monitor, ctypes.byref(info)):
        return None
    return info


def _vult_scherm(api, hwnd) -> bool:
    """Vult het venster de hele monitor? Dan staat het in volledig scherm."""
    info = _monitor(api, hwnd)
    buiten = _buiten(api, hwnd)
    if info is None or buiten is None:
        return False
    m = info.monitor
    return (buiten.links == m.links and buiten.boven == m.boven
            and buiten.rechts == m.rechts and buiten.onder == m.onder)


def _zet(api, hwnd, stand, links, boven, breed, hoog) -> bool:
    p = _Plaatsing()
    p.lengte = ctypes.sizeof(_Plaatsing)
    p.vlaggen = 0
    p.stand = stand
    p.herstel.links = links
    p.herstel.boven = boven
    p.herstel.rechts = links + breed
    p.herstel.onder = boven + hoog
    return bool(api.SetWindowPlacement(hwnd, ctypes.byref(p)))


def _f11(api, hwnd) -> None:
    api.PostMessageW(hwnd, WM_KEYDOWN, VK_F11, 0x00010001)
    time.sleep(0.12)
    api.PostMessageW(hwnd, WM_KEYUP, VK_F11, 0xC0010001)


def _klem(api, hwnd, links, boven, breed, hoog):
    """De maat en de plaats binnen het werkblad brengen.

    Twee dingen tegelijk. Het venster mag niet buiten het scherm openen (de plaats) en het mag niet
    **groter** zijn dan het werkblad (de maat) - anders valt de onderkant, met de groene statusbalk,
    achter de taakbalk. Op een scherm met 150 % weergave past de beginmaat 1440 x 900 niet op een
    werkblad van ±1280 x 700, en dan verdwijnt die onderkant achter de taakbalk; maximaliseren
    verhelpt dat omdat de browser zich dan zelf binnen het werkblad houdt.

    Dit is de plek waar het werkblad **gemeten** wordt (via de monitor van het venster), dus hier klopt
    het ook op de eerste start, als er nog geen `venster.json` is met een werkblad erin. Alle vier de
    maten zijn in de eenheid van de API.

    `WINDOWPLACEMENT.herstel` werkt in werkbladcoördinaten: het nulpunt ligt bij de taakbalk, niet bij
    de schermrand. Staat de taakbalk onderaan (het gewone geval), dan vallen die twee samen.
    """
    info = _monitor(api, hwnd)
    if info is None:
        return links, boven, breed, hoog
    w = info.werkblad
    werkblad_breed = max(1, w.rechts - w.links)
    werkblad_hoog = max(1, w.onder - w.boven)
    breed = min(breed, werkblad_breed)
    hoog = min(hoog, werkblad_hoog)
    links = max(w.links, min(links, max(w.links, w.rechts - breed)))
    boven = max(w.boven, min(boven, max(w.boven, w.onder - hoog)))
    return links, boven, breed, hoog


def _bewust():
    """Is dit proces schaalbewust, en zo ja hoe? 0 = nee, 1 = systeem, 2 = per monitor.

    Waarom dit uitmaakt: de maten uit de pagina zijn **CSS-pixels**. Een proces dat níet schaalbewust
    is, ziet het scherm in dezelfde eenheden en kan ze zo doorgeven. Een proces dat het wél is, werkt
    in **beeldpunten**, en dan is 1440 doorgeven op een scherm met 120 % weergave een venster van 1200
    CSS-pixels (1440 / 1,2). Daarom vraagt deze module het op in plaats van het aan te nemen.
    """
    try:
        shcore = ctypes.WinDLL("shcore")
        shcore.GetProcessDpiAwareness.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
        waarde = ctypes.c_int(-1)
        if shcore.GetProcessDpiAwareness(None, ctypes.byref(waarde)) == 0:
            return waarde.value if waarde.value >= 0 else 0
    except (OSError, AttributeError, ValueError):
        pass
    # Ouder dan Windows 8.1: alleen "wel of niet".
    try:
        return 1 if ctypes.WinDLL("user32").IsProcessDPIAware() else 0
    except (OSError, AttributeError, ValueError):
        return 0


def _schaal(api, hwnd, scherm_css=None) -> float:
    """Hoeveel eenheden van de venster-API er in één CSS-pixel gaan.

    De maat waarmee alles staat of valt, en daarom met een **meting** en niet met een aanname: de
    monitor die de API ziet (`GetMonitorInfo`, in de eenheid van `SetWindowPlacement`) gedeeld door de
    schermbreedte die de **pagina** meldt (`screen.width`, in CSS-pixels). Zijn die twee gelijk, dan
    werkt de API in CSS-pixels; is de monitor breder, dan werkt hij in beeldpunten en moet elke maat
    vermenigvuldigd worden.

    Zo wordt `1440 x 900` bij 120 % weergave `1200 x 751`: 1440 / 1,2 = 1200, want de API rekent daar
    in beeldpunten. Een proces dat de schil zelf start weet dat niet zeker (`GetProcessDpiAwareness`
    zegt het, maar de DPI van de monitor is wat telt), dus de verhouding komt uit twee getallen die we
    allebei al hebben.
    """
    info = _monitor(api, hwnd)
    if info is not None and scherm_css and scherm_css[0] >= 200:
        verhouding = (info.monitor.rechts - info.monitor.links) / float(scherm_css[0])
        if 0.5 <= verhouding <= 4.0:
            return verhouding
    # Geen schermmaat van de pagina (eerste start ooit): dan de dpi van dit venster.
    if not _bewust():
        return 1.0
    try:
        return (api.GetDpiForWindow(hwnd) or 96) / 96.0
    except (AttributeError, OSError, ValueError):
        return 1.0


def beginschaal(scherm_css=None) -> float:
    """De schaal voor de **beginmaat** van de browser, vóór er een venster is.

    Waarom dit nodig is: een schone start geeft netjes 1440 x 900, maar na maximaliseren en
    herstarten staat er `herstelmaat 1200 x 750` in de console - die factor 1,2, nu in de
    *opgeslagen* maat. Chromium leest `--window-size` op zijn pc in
    beeldpunten: het venster opent dus 1200 CSS breed, de pagina meet dat als eerste en bewaart het,
    en zolang het venster daarna schermvullend is kan de pagina de herstelmaat niet meer meten. Dan
    blijft die eerste, te kleine meting staan.

    Dus geeft de schil de beginmaat in dezelfde eenheid als Chromium hem leest: de schermbreedte die
    de API ziet gedeeld door de schermbreedte die de pagina meldt. Zonder die maat (allereerste start)
    blijft het 1,0 - dan is er nog niets opgeslagen om te bederven.
    """
    if not beschikbaar():
        return 1.0
    api = _koppel()
    if api is None or not scherm_css or scherm_css[0] < 200:
        return 1.0
    try:
        breed = api.GetSystemMetrics(SM_CXSCREEN)
    except (AttributeError, OSError, ValueError):
        return 1.0
    if breed < 200:
        return 1.0
    verhouding = breed / float(scherm_css[0])
    return verhouding if 0.5 <= verhouding <= 4.0 else 1.0


def _fysiek(maat, schaal):
    """Een maat uit de pagina (CSS-pixels) naar de eenheid van de venster-API."""
    return (int(round(maat[0] * schaal)), int(round(maat[1] * schaal)))


def _css(maat, schaal):
    """Terug naar CSS-pixels, voor wat er in de console komt (dat is wat de gebruiker ziet)."""
    return (int(round(maat[0] / schaal)), int(round(maat[1] / schaal)))


# Een werkblad dat kleiner is dan dit is geen werkblad maar een kapotte melding; dan laten we de maat
# staan in plaats van het venster tot niets te krimpen.
MIN_WERKBLAD = (400, 300)


def klem_maat(rust, werkblad):
    """De maat binnen het werkblad brengen, zodat er niets achter de taakbalk valt.

    Zonder klemmen opent het venster op de bewaarde maat 1440 x 900, terwijl een werkblad bij 150 %
    weergave maar ±1280 x 700 is: de onderkant - met de groene statusbalk - verdwijnt achter de
    taakbalk. Maximaliseren helpt, want dan houdt de browser zichzelf binnen het werkblad; gewoon
    openen doet dat niet, want de schil geeft de bewaarde maat ongeklemd door.

    `rust` en `werkblad` zijn allebei in **CSS-pixels**: de pagina meldt `screen.availWidth` en
    `screen.availHeight` in dezelfde eenheid als de maat die ze van het venster ziet. Dit is dus een
    gewone vergelijking en geen schaalrekening - die komt pas bij het doorgeven aan de API.

    Zonder werkblad (een oude `venster.json`, of een pagina die het niet meldt) blijft de maat zoals
    hij is. Dat is geen gok: de eerste start op een kleiner scherm meldt het werkblad, en vanaf die
    start wordt er geklemd.
    """
    if not rust or not werkblad:
        return rust
    try:
        breed, hoog = int(rust[0]), int(rust[1])
        wb, wh = int(werkblad[0]), int(werkblad[1])
    except (TypeError, ValueError, IndexError):
        return rust
    if wb < MIN_WERKBLAD[0] or wh < MIN_WERKBLAD[1]:
        return rust
    return (min(breed, wb), min(hoog, wh))


def _herstel_maat(api, hwnd):
    p = _plaatsing(api, hwnd)
    if p is None:
        return None
    return (p.herstel.rechts - p.herstel.links, p.herstel.onder - p.herstel.boven)


def _past(gelezen, doel, marge=2) -> bool:
    return (gelezen is not None and abs(gelezen[0] - doel[0]) <= marge
            and abs(gelezen[1] - doel[1]) <= marge)


def pas_toe(stand, rust, positie=None, kenmerk=None, scherm=None, wacht=WACHT):
    """Zet het venster in de gevraagde stand, met die maat als herstelmaat.

    `stand` is een van de drie STAND_-waarden, `rust` een (breedte, hoogte) in **CSS-pixels** zoals de
    pagina ze meldt, `positie` een (links, boven) of None, `kenmerk` het token uit de venstertitel en
    `scherm` de schermmaat uit de pagina (nodig om de schaal te bepalen). Geeft één regel terug voor de
    console: wat er gebeurd is, of waarom het niet lukte. Een lege regel betekent: hier valt niets te
    doen (geen Windows). Het tweede deel van de uitkomst zegt of de maat ook echt zo staat: alleen dan
    mag de schil hem als de nieuwe rustmaat bewaren.

    Na het zetten wordt de maat **teruggemeten** en met de gevraagde vergeleken. Klopt hij niet, dan
    zegt de console dat met beide getallen - een verkeerde maat mag nooit als geslaagd in het verslag
    staan (dat is de fout van de vorige ronde: het startblok meldde "gemaximaliseerd" terwijl het
    venster ergens anders stond).

    Past de gevraagde maat niet op het werkblad, dan wordt hij geklemd (zie `_klem`) en
    noemt de console de maat die er werkelijk staat. Dat is geen mislukking: een venster dat groter is
    dan het scherm bestaat niet, en de statusbalk hoort zichtbaar te blijven.
    """
    if not beschikbaar():
        return "", False
    api = _koppel()
    if api is None:
        return "de Windows-API is niet beschikbaar - de stand is niet toegepast", False
    hwnd = zoek(kenmerk, wacht)
    if not hwnd:
        return ("het venster is niet gevonden - de stand is niet toegepast "
                "(het opent zoals de browser het wil)"), False

    if stand == STAND_VOLLEDIG and _vult_scherm(api, hwnd):
        # Stond het al in volledig scherm (de vlag werkte, of het venster is net geopend), dan niets
        # doen: eerst de maat zetten zou het volledige scherm juist afbreken.
        return "volledig scherm (stond al zo)", True

    schaal = _schaal(api, hwnd, scherm)
    doel = _fysiek(rust, schaal)
    plek = _fysiek(positie, schaal) if positie else (0, 0)
    # De klem geeft ook de maat terug: past de gevraagde maat niet op het werkblad, dan is de
    # **geklemde** maat het doel waartegen we nameten. Anders meldt de console een afwijking die geen
    # fout is - en wordt een kloppend venster als mislukking gerapporteerd.
    plek_links, plek_boven, doel_breed, doel_hoog = _klem(api, hwnd, plek[0], plek[1],
                                                          doel[0], doel[1])
    plek = (plek_links, plek_boven)
    doel = (doel_breed, doel_hoog)
    # Wat er werkelijk gezet wordt, in de taal van de gebruiker. Wijken die twee af, dan is de maat op
    # het werkblad geklemd en zegt de console dat: het gevraagde getal doorgeven zou een venster
    # beschrijven dat niet bestaat.
    gezet = _css(doel, schaal)
    klem = ("" if (abs(gezet[0] - rust[0]) <= 1 and abs(gezet[1] - rust[1]) <= 1)
            else ", geklemd op het werkblad (gevraagd %d x %d)" % (rust[0], rust[1]))

    # Eerst als gewoon venster neerzetten: dat zet de herstelmaat, en dat is bij alle drie de standen
    # hetzelfde beginpunt. Daarna pas maximaliseren of F11.
    _zet(api, hwnd, SW_SHOWNORMAL, plek[0], plek[1], doel[0], doel[1])
    time.sleep(0.3)
    gelezen = _herstel_maat(api, hwnd)
    gemeten = _css(gelezen, schaal) if gelezen else None
    goed = _past(gelezen, doel)
    # Wat er in de console komt als de maat niet klopt: het gemetene, en anders wat er gezet had moeten
    # worden. Nooit `gemeten[0]` los: dat is None zodra het venster niets terugmeldt.
    lees = gemeten or gezet
    schaal_tekst = "" if abs(schaal - 1.0) <= 0.02 else ", schaal %.2f" % schaal

    if stand == STAND_GEMAXIMALISEERD:
        _zet(api, hwnd, SW_SHOWMAXIMIZED, plek[0], plek[1], doel[0], doel[1])
        time.sleep(0.35)
        p = _plaatsing(api, hwnd)
        if p is None or p.stand != SW_SHOWMAXIMIZED:
            return ("maximaliseren niet gelukt - het venster staat op %d x %d"
                    % lees), False
        if not goed:
            return ("gemaximaliseerd, maar de herstelmaat is %d x %d in plaats van %d x %d%s%s"
                    % (lees[0], lees[1], gezet[0], gezet[1], schaal_tekst, klem)), False
        return ("gemaximaliseerd (herstelmaat %d x %d%s%s)"
                % (gezet[0], gezet[1], schaal_tekst, klem)), True

    if stand == STAND_VOLLEDIG:
        _f11(api, hwnd)
        time.sleep(0.5)
        if not _vult_scherm(api, hwnd):
            return ("volledig scherm niet gelukt - het venster staat op %d x %d"
                    % lees), False
        if not goed:
            return ("volledig scherm, maar de herstelmaat is %d x %d in plaats van %d x %d%s%s"
                    % (lees[0], lees[1], gezet[0], gezet[1], schaal_tekst, klem)), False
        return ("volledig scherm (herstelmaat %d x %d%s%s)"
                % (gezet[0], gezet[1], schaal_tekst, klem)), True

    if not goed and gemeten is not None:
        return ("maat niet overgenomen: gevraagd %d x %d, gemeten %d x %d%s%s"
                % (gezet[0], gezet[1], lees[0], lees[1], schaal_tekst, klem)), False
    return "%d x %d%s%s" % (gezet[0], gezet[1], schaal_tekst, klem), True
