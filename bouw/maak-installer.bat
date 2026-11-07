@echo off
rem ===========================================================================================
rem  Astrologie Studio - de installer bouwen (Inno Setup 6)
rem
rem  Starten: dubbelklikken, of vanaf de opdrachtregel:  bouw\maak-installer.bat
rem
rem  Wat het doet, in deze volgorde:
rem    1. kijken of Inno Setup 6 er is (het compileerprogramma ISCC.exe);
rem    2. kijken of de bundel die meegeleverd wordt in dist\ staat - dat is sinds 27 okt 2026 de
rem       versie MET consolevenster (de cursist ziet de server draaien). Ontbreekt hij, dan eerst
rem       bouw\bouw-windows.bat draaien; dat bouwt beide smaken;
rem    3. kijken of de bronzip in uitgave\ staat (de AGPL-3.0 vraagt dat de bron meegaat);
rem    4. het versienummer uit kern\versie.py in bouw\versie.iss schrijven;
rem    5. compileren met ISCC. De setup komt in uitgave\.
rem
rem  Waarom hier geen versie- of ziptaken in dit script zelf: cmd is slecht in logica. Elk stuk dat
rem  kan mislukken, stopt met een melding die zegt wat je moet doen.
rem
rem  De tekst is met opzet zonder accenten (codepage van de machine).
rem ===========================================================================================

setlocal
chcp 65001 >nul
cd /d "%~dp0.."

echo === Astrologie Studio - installer bouwen ===
echo projectmap: %CD%
echo.

rem --- 1. Inno Setup vinden ---------------------------------------------------------------
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC (
    echo FOUT: Inno Setup 6 staat niet op deze pc.
    echo Haal het gratis op: https://jrsoftware.org/isdl.php  ^(Inno Setup 6^)
    echo Daarna dit script opnieuw starten.
    goto :einde
)
echo Inno Setup: %ISCC%

rem --- 2. de bundel die meegaat -------------------------------------------------------------
rem Sinds 27 okt 2026 is dat de versie MET consolevenster: de cursist ziet dat er een server draait.
rem De naam moet gelijk zijn aan AppExe in astrologie-studio.iss - daar verwijst de installer naar.
set "BUNDEL=dist\Astrologie Studio - console.exe"
if not exist "%BUNDEL%" (
    echo FOUT: %BUNDEL% ontbreekt ^(de versie met consolevenster^).
    echo Draai eerst:  bouw\bouw-windows.bat
    echo Dat bouwt beide smaken; met "console" erachter alleen deze.
    goto :einde
)
for %%f in ("%BUNDEL%") do echo bundel: %%~zf bytes, %%~tf

rem --- 3. de bronzip ----------------------------------------------------------------------
dir /b "uitgave\astrologie-studio-bron-*.zip" >nul 2>nul
if errorlevel 1 (
    echo FOUT: er staat geen bronzip in uitgave\.
    echo Maak hem eerst op de server:  bash bouw/maak-bronzip.sh
    echo Zonder bronzip geen installer: de AGPL-3.0 vraagt dat de bron meegaat.
    goto :einde
)

rem --- 4. versie.iss schrijven ------------------------------------------------------------
where python >nul 2>nul
if errorlevel 1 (
    echo FOUT: Python staat niet in het PATH; nodig om versie.iss te maken.
    goto :einde
)
python bouw\maak-versie-iss.py
if errorlevel 1 (
    echo FOUT: versie.iss kon niet gemaakt worden. Zie de melding hierboven.
    goto :einde
)

rem --- 5. compileren ----------------------------------------------------------------------
echo.
echo --- compileren ---
"%ISCC%" /Qp bouw\astrologie-studio.iss
if errorlevel 1 (
    echo.
    echo FOUT: het compileren is mislukt. De meldingen staan hierboven.
    goto :einde
)

echo.
echo --- klaar ---
for %%f in ("uitgave\astrologie-studio-*-setup.exe") do (
    echo bestand: %%~ff  ^(%%~zf bytes^)
    certutil -hashfile "%%~ff" SHA256 | findstr /v ":"
)
echo.
echo De setup staat in uitgave\. Test hem voor je hem weggeeft:
echo   installeren, programma starten, weer verwijderen ^(met en zonder "gegevens verwijderen"^).

:einde
echo.
pause
endlocal
