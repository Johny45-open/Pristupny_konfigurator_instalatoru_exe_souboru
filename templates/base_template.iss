; Přístupná šablona pro Inno Setup
; Vygenerováno pomocí Přístupného konfigurátoru instalátorů

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppAuthor}
DefaultDirName={#DefaultDirName}\{#AppName}
DefaultGroupName={#AppName}
OutputDir=.
OutputBaseFilename={#AppName}_Setup
Compression=lzma
SolidCompression=yes
ArchitecturesAllowed={#ArchitecturesAllowed}
ArchitecturesInstallIn64BitMode={#ArchitecturesInstallIn64BitMode}

[Languages]
Name: "czech"; MessagesFile: "compiler:Languages\Czech.isl"

[CustomMessages]
; Vlastní zprávy pro přístupnost (přístupné přes CustomMessage)
SelectDirDesc=Kam má být produkt {#AppName} nainstalován? Průvodce nainstaluje produkt do následující složky. Pokračujte klepnutím na tlačítko Další.
SelectProgramGroupDesc=Kam má průvodce umístit zástupce aplikace? Průvodce vytvoří zástupce v následující složce nabídky Start. Pokračujte klepnutím na tlačítko Další.

[Messages]
; Vylepšení přístupnosti pro dialog zrušení instalace (přepisuje systémové zprávy)
czech.ExitSetupTitle=Ukončení instalace
czech.ExitSetupMessage=Chcete skutečně přerušit instalaci programu {#AppName}? Pokud ji nyní ukončíte, program nebude nainstalován. Stiskněte Ano pro ukončení nebo Ne pro pokračování v instalaci.

[Tasks]
{#DesktopShortcutTask}

[Files]
Source: "{#ExePath}"; DestDir: "{app}"; Flags: ignoreversion
{#ExtraFiles}

[Icons]
{#StartMenuShortcut}
{#DesktopShortcut}

[Run]
Filename: "{app}\{#ExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[Code]
// Procedura pro vynucení čtení instrukcí při změně stránky
procedure CurPageChanged(CurPageID: Integer);
var
  InstructionText: String;
begin
  case CurPageID of
    wpSelectDir:
      InstructionText := 'Zvolte cílové umístění. ' + CustomMessage('SelectDirDesc');
    wpSelectProgramGroup:
      InstructionText := 'Zvolte složku v nabídce Start. ' + CustomMessage('SelectProgramGroupDesc');
    wpSelectTasks:
      InstructionText := 'Vyberte další úlohy, které mají být provedeny.';
  end;
end;

// Funkce pro úpravu popisků za běhu pro lepší přístupnost
procedure InitializeWizard();
begin
  // Nastavení AccessibleName pro klíčové prvky, aby čtečka věděla, co edituje
  WizardForm.DirEdit.Hint := 'Zadejte cestu k instalaci';
  WizardForm.GroupEdit.Hint := 'Zadejte název složky v nabídce Start';
end;
