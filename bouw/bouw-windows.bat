@echo off
rem ===========================================================================================
rem  Astrologie Studio - de Windows-bundel bouwen
rem
rem  Starten: dubbelklikken, of vanaf de opdrachtregel:
rem      bouw\bouw-windows.bat            -> BEIDE smaken: eerst met consolevenster (die gaat de
rem                                          installer in), daarna zonder consolevenster
rem      bouw\bouw-windows.bat console    -> alleen met consolevenster (wat de cursist krijgt)
rem      bouw\bouw-windows.bat stil       -> alleen zonder consolevenster
rem  Werkt vanaf elke map: het script gaat zelf naar de projectmap (een map boven deze).
rem
rem  Sinds 27 okt 2026 bouwt dubbelklikken allebei de smaken; daarvoor moest er na de bouw nog iets
rem  aangepast worden voor de installer gemaakt kon worden. Na een run staan nu beide .exe's in
rem  dist\, uit dezelfde bron, elk met zijn eigen zelfcontrole. Een smaak kiezen kan nog steeds.
rem
rem  Welke smaak is voor de cursist: die MET consolevenster (besluit 27 okt 2026). Hij ziet dan dat
rem  er een lokale server draait, in plaats van een programma dat iets doet zonder dat je het ziet.
rem  De stille bundel blijft bestaan voor wie geen venster wil, maar gaat niet de installer in.
rem
rem  Wat het doet: kijken of Python en de drie pakketten er zijn (en ze anders installeren), het
rem  versienummer schrijven, bouwen met PyInstaller volgens bouw\astrologie-studio.spec, en daarna de
rem  zelfcontrole van de bundel laten draaien. Faalt de zelfcontrole, dan stopt het script met een fout
rem  - een bundel die zichzelf niet kan narekenen is geen bundel om weg te geven.
rem
rem  De tekst is met opzet zonder accenten: een .bat wordt in de codepage van de machine gelezen en
rem  dan worden letters met een accent soms onleesbaar. Om dezelfde reden staan er geen haakjes in
rem  de bestandsnaam van de consoleversie: haakjes in een pad botsen met de blokken van cmd.
rem ===========================================================================================

setlocal
chcp 65001 >nul
cd /d "%~dp0.."

rem ===========================================================================================
rem  1. Eenmalige voorbereiding: Python, de pakketten, de efemeriden en het versienummer.
rem ===========================================================================================
echo === Astrologie Studio - bouw voor Windows ===
echo projectmap: %CD%

where python >nul 2>nul
if errorlevel 1 (
    echo FOUT: Python staat niet in het PATH.
    echo Installeer Python 3.11 of 3.12 van python.org en vink "Add python.exe to PATH" aan.
    goto :einde
)

for /f "tokens=2" %%v in ('python -V 2^>^&1') do echo Python: %%v

python -c "import PyInstaller, swisseph, tzdata" >nul 2>nul
if errorlevel 1 (
    echo Een van de drie pakketten ontbreekt ^(pyinstaller, pyswisseph, tzdata^); ik installeer ze.
    python -m pip install --upgrade pyinstaller pyswisseph tzdata
    if errorlevel 1 (
        echo FOUT: het installeren van de pakketten is mislukt.
        goto :einde
    )
)

if not exist "efemeriden\sepl_18.se1" (
    echo FOUT: de efemeriden ontbreken in efemeriden\ - zonder die bestanden rekent het programma
    echo met de Moshier-benadering in plaats van met de echte standen.
    goto :einde
)

echo.
echo --- versienummer ---
python bouw\maak-versie-iss.py --alleen-versie
if errorlevel 1 (
    echo FOUT: het versienummer kon niet geschreven worden ^(zie de melding hierboven^).
    goto :einde
)

rem ===========================================================================================
rem  2. Welke smaak(en)?
rem ===========================================================================================
set "SMAAK=%~1"
if /i "%SMAAK%"=="stil" goto :een
if /i "%SMAAK%"=="console" goto :een
if "%SMAAK%"=="" goto :beide
echo.
echo FOUT: onbekende keuze "%SMAAK%".
echo Gebruik:  bouw\bouw-windows.bat            ^(beide smaken^)
echo           bouw\bouw-windows.bat stil       ^(alleen zonder venster^)
echo           bouw\bouw-windows.bat console    ^(alleen met venster^)
goto :einde

:beide
call :bouw stil
if errorlevel 1 goto :einde
call :bouw console
if errorlevel 1 goto :einde
goto :klaar

:een
call :bouw %SMAAK%
if errorlevel 1 goto :einde
goto :klaar

rem ===========================================================================================
rem  3. :bouw <smaak> - een smaak bouwen en zijn zelfcontrole laten draaien.
rem     Geeft 0 terug bij succes en 1 bij een fout; de melding staat er dan al.
rem ===========================================================================================
:bouw
set "STIL="
set "EXE=dist\Astrologie Studio - console.exe"
if /i "%~1"=="stil" (
    set "STIL=1"
    set "EXE=dist\Astrologie Studio.exe"
)

echo.
if defined STIL (
    echo === smaak: ZONDER consolevenster ^(optioneel^) ===
) else (
    echo === smaak: MET consolevenster ^(deze gaat de installer in^) ===
)

echo.
echo --- bouwen ---
if defined STIL set "ASTRO_STIL=1"
python -m PyInstaller --clean --noconfirm bouw\astrologie-studio.spec
rem Eerst de uitslag lezen en pas daarna ASTRO_STIL wissen: `set` zet errorlevel op 0 en zou een
rem mislukte bouw laten doorgaan alsof er niets aan de hand is.
if errorlevel 1 (
    set "ASTRO_STIL="
    echo FOUT: de bouw is mislukt. De meldingen staan hierboven.
    exit /b 1
)
set "ASTRO_STIL="

if not exist "%EXE%" (
    echo FOUT: de bouw meldde geen fout, maar "%EXE%" staat er niet. Iets is er misgegaan.
    exit /b 1
)

echo.
echo --- zelfcontrole van de gebouwde bundel ---
rem De stille versie heeft geen console, dus daar leest het script het verslag uit het bestand in
rem plaats van van het scherm; vandaar `start /wait` (cmd wacht niet vanzelf op een vensterloos
rem programma).
del /q controle-uitkomst.txt 2>nul
if defined STIL (
    start /wait "" "%EXE%" --controle
) else (
    "%EXE%" --controle
)
if defined STIL (
    findstr /c:"In orde: alle controles geslaagd." controle-uitkomst.txt >nul 2>nul
    if errorlevel 1 (
        echo.
        echo FOUT: de zelfcontrole faalt of kwam niet op gang. Zie controle-uitkomst.txt.
        exit /b 1
    )
)
if not defined STIL (
    if errorlevel 1 (
        echo.
        echo FOUT: de zelfcontrole faalt. Deze bundel niet weggeven; eerst uitzoeken wat ontbreekt.
        exit /b 1
    )
)

echo.
echo --- klaar met deze smaak ---
for %%f in ("%EXE%") do echo bestand: %%~ff  ^(%%~zf bytes^)
certutil -hashfile "%EXE%" SHA256 | findstr /v ":"
if defined STIL (
    echo.
    echo Dit is de stille versie: geen consolevenster. Stoppen doet de gebruiker met
    echo Bestand ^> Afsluiten in het venster. Wat er misgaat staat in fouten.log bij de horoscopen.
    echo Deze versie gaat NIET de installer in ^(die neemt de consoleversie^).
) else (
    echo.
    echo Dit is de versie MET consolevenster - dezelfde die de cursist krijgt ^(besluit 27 okt 2026:
    echo de cursist ziet dat er een lokale server draait^). Hij gaat de installer in.
)
exit /b 0

rem ===========================================================================================
rem  4. Afsluiten
rem ===========================================================================================
:klaar
echo.
echo --- gereed ---
if exist "dist\Astrologie Studio - console.exe" echo voor de installer: %CD%\dist\Astrologie Studio - console.exe
if exist "dist\Astrologie Studio.exe" echo stil, optioneeel:    %CD%\dist\Astrologie Studio.exe
echo.
echo De .exe's staan in de map dist. Wil je ze weggeven, maak dan ook de bronzip:
echo op de server  bash bouw/maak-bronzip.sh  (zie bouw/LEESMIJ.md, punt 3).
echo De installer maak je daarna met:  bouw\maak-installer.bat

:einde
echo.
pause
endlocal
