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

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#ExePath}"; DestDir: "{app}"; Flags: ignoreversion
{#ExtraFiles}

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#ExeName}"
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\{#ExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#ExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[Messages]
; Vylepšení přístupnosti pro dialog zrušení instalace
czech.ExitSetupTitle=Ukončení instalace
czech.ExitSetupMessage=Chcete skutečně přerušit instalaci programu {#AppName}? Pokud ji nyní ukončíte, program nebude nainstalován. Stiskněte Ano pro ukončení nebo Ne pro pokračování v instalaci.

; Oprava čtení instrukcí na stránkách
czech.SelectDirDesc=Kam má být produkt {#AppName} nainstalován? Průvodce nainstaluje produkt do následující složky. Pokračujte klepnutím na tlačítko Další.
czech.SelectProgramGroupDesc=Kam má průvodce umístit zástupce aplikace? Průvodce vytvoří zástupce v následující složce nabídky Start. Pokračujte klepnutím na tlačítko Další.

[Code]
// Procedura pro vynucení čtení instrukcí při změně stránky
procedure CurPageChanged(CurPageID: Integer);
var
  InstructionText: String;
begin
  // Při změně stránky se pokusíme zaměřit text, který má čtečka přečíst
  case CurPageID of
    wpSelectDir:
      InstructionText := 'Zvolte cílové umístění. ' + CustomMessage('SelectDirDesc');
    wpSelectProgramGroup:
      InstructionText := 'Zvolte složku v nabídce Start. ' + CustomMessage('SelectProgramGroupDesc');
    wpSelectTasks:
      InstructionText := 'Vyberte další úlohy, které mají být provedeny.';
  end;
  
  // Tip pro přístupnost: Inno Setup standardně dává fokus na editační pole nebo seznam.
  // Můžeme zkusit nastavit popisek jako "vyskakovací" hlášení pro čtečky, 
  // nebo zajistit, aby editační pole mělo správný AccessibleName obsahující i instrukci.
end;

// Funkce pro úpravu popisků za běhu pro lepší přístupnost
procedure InitializeWizard();
begin
  // Nastavení AccessibleName pro klíčové prvky, aby čtečka věděla, co edituje
  WizardForm.DirEdit.Hint := 'Zadejte cestu k instalaci';
  WizardForm.GroupEdit.Hint := 'Zadejte název složky v nabídce Start';
end;
