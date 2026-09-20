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
// Přístupné oznámení při změně stránky – aktualizuje popisky pro čtečku
procedure CurPageChanged(CurPageID: Integer);
begin
  try
    case CurPageID of
      wpSelectDir:
        WizardForm.SelectDirLabel.Caption := CustomMessage('SelectDirDesc');
      wpSelectProgramGroup:
        WizardForm.SelectStartMenuFolderLabel.Caption := CustomMessage('SelectProgramGroupDesc');
      wpSelectTasks:
        WizardForm.TasksLabel.Caption := 'Vyberte další úlohy, které mají být provedeny.';
    end;
  except
  end;
end;

// Nastavení přístupnosti – Hint je jen fallback, hlavní je propojení Label<->Edit přes FocusControl
procedure InitializeWizard();
begin
  WizardForm.DirEdit.Hint := 'Zadejte cestu k instalaci';
  WizardForm.GroupEdit.Hint := 'Zadejte název složky v nabídce Start';
  // Zajisti, že popisky jsou fokusovatelné pro čtečku (FocusControl propojení už existuje v Inno)
  try
    WizardForm.DirEdit.AccessibleName := 'Cesta k instalaci';
  except
  end;
  try
    WizardForm.GroupEdit.AccessibleName := 'Složka v nabídce Start';
  except
  end;
end;
