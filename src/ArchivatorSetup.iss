; Přístupná šablona pro Inno Setup
; Vygenerováno pomocí Přístupného konfigurátoru instalátorů

[Setup]
AppName=Přístupný mluvící archivátor
AppVersion=1.0
AppPublisher=Jan Kalivoda
DefaultDirName={autopf64}\Přístupný mluvící archivátor
DefaultGroupName=Přístupný mluvící archivátor
OutputDir=.
OutputBaseFilename=Přístupný mluvící archivátor_Setup
Compression=lzma
SolidCompression=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "czech"; MessagesFile: "compiler:Languages\Czech.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "C:/Honza/Projekty/Pristupny_mluvici_archivator/dist/main/main.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "C:/Honza/Projekty/Pristupny_mluvici_archivator/dist/main\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Přístupný mluvící archivátor"; Filename: "{app}\main.exe"
Name: "{commondesktop}\Přístupný mluvící archivátor"; Filename: "{app}\main.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\main.exe"; Description: "{cm:LaunchProgram,Přístupný mluvící archivátor}"; Flags: nowait postinstall skipifsilent

[Messages]
; Vylepšení přístupnosti pro dialog zrušení instalace
czech.ExitSetupTitle=Ukončení instalace
czech.ExitSetupMessage=Chcete skutečně přerušit instalaci programu Přístupný mluvící archivátor? Pokud ji nyní ukončíte, program nebude nainstalován. Stiskněte Ano pro ukončení nebo Ne pro pokračování v instalaci.
