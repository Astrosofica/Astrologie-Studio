; =============================================================================================
;  Astrologie Studio - Inno Setup 6-script voor de installer
;
;  Bouwen:  bouw\maak-installer.bat     (op de Windows-pc, met Inno Setup 6 geinstalleerd)
;  Of los:  eerst  python bouw\maak-versie-iss.py   (dat schrijft versie.iss, zie regel 31),
;           en dan  "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" bouw\astrologie-studio.iss
;           versie.iss staat niet in de repo (het is afgeleid van kern/versie.py), dus in een
;           verse kopie ontbreekt het tot dat script gedraaid is. Ontbreekt het toch, dan stopt
;           het compileren met de melding bij regel 31 hieronder.
;  Let op bij de Inno Setup-IDE: die draait maak-versie-iss.py niet. Bestaat versie.iss al maar is
;  het verouderd, dan compileert de IDE zonder klagen met het nummer van de vorige keer (27 okt 2026). Draai het script dus eerst, of gebruik bouw\maak-installer.bat.
;
;  Wat dit script doet en waarom:
;
;  - **Per gebruiker installeren** (PrivilegesRequired=lowest): geen beheerderswachtwoord en geen
;    UAC-vraag. De app komt in %LOCALAPPDATA%\Programs\Astrologie Studio en de snelkoppelingen in het
;    eigen profiel. Besluit (20 okt 2026): het vriendelijkst voor een cursist op een eigen
;    laptop. Voor een lescomputer voor iedereen is een tweede variant per machine nodig.
;  - **De gegevens blijven buiten de installatiemap.** Horoscopen en instellingen staan in
;    %USERPROFILE%\astrologie-horoscopen; die map raakt de installer nooit aan, ook niet bij een
;    upgrade. Bij het weghalen vraagt de verwijderaar of die map ook weg moet - met "nee" als
;    antwoord als je gewoon doorgaat, en met het pad erbij.
;  - **De bronzip gaat mee de installatiemap in.** De AGPL-3.0 vraagt dat de bron met de binary
;    meegaat; de Over-tab belooft dat ook. Vandaar {app}\bron\<zip>.
;  - **De consoleversie gaat juist mee** (besluit 27 okt 2026). De cursist krijgt de versie
;    MET consolevenster: dan ziet hij dat er een lokale server draait in plaats van een zwart gat,
;    en niets wordt verborgen. De stille bundel bestaat nog (zelfde spec, `console=False`) voor
;    wie geen venster wil, maar die gaat niet de installer in.
;
;  Het versienummer en de naam van de bronzip staan niet hier maar in versie.iss, dat
;  maak-versie-iss.py uit kern/versie.py en uitgave/ schrijft. Eén waarheid, geen tweede nummer.
; =============================================================================================

#define AppNaam "Astrologie Studio"
#define AppExe "Astrologie Studio - console.exe"
#define AppUitgever "Mercurieus"
#define AppUrl "https://studio.astrosofica.nl/"

; versie.iss wordt geschreven door maak-versie-iss.py en staat bewust niet in de repo: één nummer,
; één bron (kern/versie.py). Ontbreekt het bestand, dan is dit de melding die je krijgt - niet de
; kale "Cannot open file" van een gewone #include, want daar zoek je lang naar (27 okt 2026).
#if FileExists(AddBackslash(SourcePath) + "versie.iss")
  #include "versie.iss"
#else
  #error versie.iss ontbreekt naast dit script. Draai eerst: python bouw\maak-versie-iss.py  (of gebruik bouw\maak-installer.bat)
#endif

[Setup]
; De AppId blijft voor eeuwig gelijk: Windows herkent een nieuwe versie aan dit nummer en ziet hem
; dan als upgrade in plaats van als tweede programma. Nooit wijzigen.
AppId={{7C4B2E51-9A3D-4E77-8B21-6F5D2A9C1E30}
AppName={#AppNaam}
AppVersion={#AppVersie}
AppVerName={#AppNaam} {#AppVersie}
AppPublisher={#AppUitgever}
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}
AppUpdatesURL={#AppUrl}
VersionInfoVersion={#AppVersie}
VersionInfoDescription={#AppNaam} installatie
VersionInfoProductName={#AppNaam}
DefaultDirName={autopf}\{#AppNaam}
DefaultGroupName={#AppNaam}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\uitgave
OutputBaseFilename=astrologie-studio-{#AppVersie}-setup
SetupIconFile=astrologie-studio.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppNaam} {#AppVersie}
Compression=lzma2/max
SolidCompression=yes
; De moderne wizard volgt sinds Inno 6.6 het lichte of donkere thema van Windows (`dynamic`). De
; 0.4.1-setup is met 6.7.0 gebouwd, dus dit werkt; bij een oudere Inno Setup stopt ISCC meteen met een
; duidelijke melding in plaats van stil iets anders te doen. In donkere modus vervangt Inno de kleuren
; in de RTF door de kleuren van de donkere stijl - de installatietekst blijft dus leesbaar.
WizardStyle=modern dynamic
InfoBeforeFile=installatie-tekst.rtf
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
; De app is één .exe van ±16 MB; een installer die zichzelf opruimt is dan genoeg, geen uninstall-logica.
AllowNoIcons=yes
; Eén programma tegelijk (28 okt 2026). De app maakt bij het starten een mutex met deze naam; zolang
; die bestaat weigert de installer verder te gaan in plaats van te proberen het venster te sluiten -
; dat lukte niet (het is een console met een server erachter) en daarna was het programma ook niet meer
; netjes af te sluiten. De naam moet gelijk zijn aan MUTEX_NAAM in schil/server.py; ijk-installer.py
; vergelijkt de twee, want een typefout hier valt verder nergens op.
AppMutex=AstrologieStudio
; Niet zelf proberen te sluiten: de melding vraagt de gebruiker het zelf te doen (zie [Messages]).
CloseApplications=no

[Messages]
; Onze eigen regel in plaats van Inno's standaard ("sluit alle actieve exemplaren nu af"): bij dit
; programma is het kruisje van het venster niet de sluitweg - dat is Bestand > Afsluiten, want het
; kruisje hoort bij het venster en de schil daarachter blijft draaien tot die menu-regel.
SetupAppRunningError=Astrologie Studio draait nog.%n%nSluit het programma via het menu Bestand > Afsluiten en klik daarna op OK om door te gaan, of op Annuleren om de installatie af te breken.

[Languages]
Name: "dutch"; MessagesFile: "compiler:Languages\Dutch.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; Een update schrijft een nieuwe bronzip met een nieuwe naam in {app}\bron. Inno Setup ruimt bij een
; update niets op wat uit het pakket verdwenen is: het schrijft bij in het bestaande verwijderlogboek
; in plaats van het oude pakket eerst weg te halen (AppId + append, zie de Inno-documentatie). Zonder
; deze regel laat elke versie zijn eigen zip van 6 MB staan. Alleen onze eigen bestanden, nooit iets
; van de gebruiker: die staat buiten {app}.
Type: files; Name: "{app}\bron\*.zip"

[Files]
; De stille bundel. `ignoreversion` omdat het één bestand is dat bij elke versie vervangen wordt.
Source: "..\dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion
; De papieren kant: licentie en de korte leesmij die ook in het archief zit.
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
; De licentieteksten van de lettertypen, zodat de bronvermelding in de Over-tab naar iets wijst dat
; er ook echt is (OFL vraagt dat).
Source: "..\data\fonts\LICENTIE-AstroSans.txt"; DestDir: "{app}\licenties"; Flags: ignoreversion
Source: "..\data\fonts\LICENTIE-Selawik.txt"; DestDir: "{app}\licenties"; Flags: ignoreversion
Source: "..\data\fonts\bron\*.txt"; DestDir: "{app}\licenties\bron"; Flags: ignoreversion
; De bron van precies deze versie (AGPL-3.0).
Source: "..\uitgave\{#BronZip}"; DestDir: "{app}\bron"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppNaam}"; Filename: "{app}\{#AppExe}"; Comment: "{#AppVersie}"
Name: "{group}\{cm:UninstallProgram,{#AppNaam}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppNaam}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppNaam}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Niets: alles wat hier staat wordt door de verwijderaar van Windows zelf al opgeruimd. De map met
; horoscopen staat hier bewust niet bij - die vraagt de verwijderaar eerst (zie [Code]).

[Code]
var
  GegevensVerwijderen: Boolean;

function GegevensMap(): String;
begin
  // Hetzelfde pad als kern/paden.standaardmap() op Windows: de thuis-map van de gebruiker.
  // ASTRO_HOROSCOPENMAP kan het programma ergens anders laten schrijven; die variabele is per
  // gebruiker gezet en wordt hier niet gelezen - de verwijderaar noemt daarom het pad dat hij
  // kent, en vraagt het pas als die map er echt is.
  //
  // Let op (21 okt 2026): dit is NIET de Inno-constante userprofile - die bestaat niet, en dat gaf
  // bij het weghalen "Interne fout: unknown constant userprofile". De omgevingsvariabele lees je
  // met een procentteken vóór de naam, tussen accolades, zoals in de regel hieronder.
  //
  // Schrijf die accolades hier niet uit (27 okt 2026): Pascal kent geen geneste commentaren, dus
  // een accolade-paar binnen een commentaar sluit dat commentaar voortijdig en de rest wordt als
  // code gelezen. Dat was een compileerfout in de vorige versie van deze notitie - een notitie
  // over het probleem die zelf het probleem werd. Vandaar commentaarregels met // en geen haken.
  Result := ExpandConstant('{%USERPROFILE}\astrologie-horoscopen');
end;

function InitializeUninstall(): Boolean;
var
  Map: String;
begin
  Result := True;
  Map := GegevensMap();
  if DirExists(Map) then
  begin
    if MsgBox('Ook je gegevens verwijderen?' + #13#10 + #13#10 +
              Map + #13#10 +
              'Daarin staan je horoscopen, je instellingen en je eigen plaatsen.' + #13#10 + #13#10 +
              'Kies Nee om ze te houden; dat is de bedoeling als je later een nieuwe versie ' +
              'installeert. Dan blijft de map staan en wordt alleen het programma verwijderd. ' +
              'Kies Ja, dan gaat de hele map weg en dat kan niet meer ongedaan worden gemaakt.',
              mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      GegevensVerwijderen := True;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and GegevensVerwijderen then
    DelTree(GegevensMap(), True, True, True);
end;
