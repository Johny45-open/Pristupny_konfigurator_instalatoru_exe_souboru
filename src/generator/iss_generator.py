import os

def generate_iss(data, output_path, template_path):
    """
    Generuje .iss soubor na základě dat z wizardu a šablony.
    """
    with open(template_path, 'r', encoding='utf-8') as f:
        template = f.read()

    exe_path = data.get('exePath')
    exe_name = os.path.basename(exe_path)
    app_name = data.get('appName')
    app_version = data.get('appVersion')
    app_author = data.get('appAuthor')
    
    install_dir_index = data.get('installDir')
    if install_dir_index == 0:  # 64-bit
        default_dir = "{autopf64}"
        arch_allowed = "x64"
        arch_mode = "x64"
    else:  # 32-bit
        default_dir = "{autopf32}"
        arch_allowed = "x86 x64"
        arch_mode = ""

    extra_files = ""
    dir_path = data.get('dirPath')
    if dir_path and os.path.exists(dir_path):
        # Pokud je vybrána složka (onedir), přidáme její obsah
        extra_files = f'Source: "{dir_path}\\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs'

    replacements = {
        "{#AppName}": app_name,
        "{#AppVersion}": app_version,
        "{#AppAuthor}": app_author,
        "{#DefaultDirName}": default_dir,
        "{#ArchitecturesAllowed}": arch_allowed,
        "{#ArchitecturesInstallIn64BitMode}": arch_mode,
        "{#ExePath}": exe_path,
        "{#ExeName}": exe_name,
        "{#ExtraFiles}": extra_files
    }

    iss_content = template
    for placeholder, value in replacements.items():
        iss_content = iss_content.replace(placeholder, str(value))

    with open(output_path, 'w', encoding='utf-8-sig') as f: # BOM pro Inno Setup
        f.write(iss_content)

    return output_path
