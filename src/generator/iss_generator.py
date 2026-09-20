import os

def _escape_iss(s: str) -> str:
    if s is None:
        return ""
    return str(s).replace('"', '""').replace('\r', '').replace('\n', ' ')

def generate_iss(data, output_path, template_path):
    with open(template_path, 'r', encoding='utf-8') as f:
        template = f.read()
    exe_path = data.get('exePath')
    exe_name = os.path.basename(exe_path) if exe_path else ""
    app_name = _escape_iss(data.get('appName', ''))
    app_version = _escape_iss(data.get('appVersion', '1.0.0') or "1.0.0")
    app_author = _escape_iss(data.get('appAuthor', ''))
    install_dir_index = data.get('installDir')
    if install_dir_index == 0:
        default_dir = "{autopf64}"
        arch_allowed = "x64"
        arch_mode = "x64"
    else:
        default_dir = "{autopf32}"
        arch_allowed = "x86 x64"
        arch_mode = ""
    extra_files = ""
    dir_path = data.get('dirPath')
    if dir_path and os.path.exists(dir_path):
        extra_files = f'Source: "{dir_path}\\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "*.pdb,*.log,*.tmp,*.ilk,__pycache__"'
    replacements = {"{#AppName}": app_name, "{#AppVersion}": app_version, "{#AppAuthor}": app_author, "{#DefaultDirName}": default_dir, "{#ArchitecturesAllowed}": arch_allowed, "{#ArchitecturesInstallIn64BitMode}": arch_mode, "{#ExePath}": exe_path, "{#ExeName}": exe_name, "{#ExtraFiles}": extra_files, "{#DesktopShortcutTask}": 'Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked' if data.get('createDesktopShortcut') else "", "{#StartMenuShortcut}": f'Name: "{{group}}\\{app_name}"; Filename: "{{app}}\\{exe_name}"' if data.get('createStartMenuShortcut') else "", "{#DesktopShortcut}": f'Name: "{{commondesktop}}\\{app_name}"; Filename: "{{app}}\\{exe_name}"; Tasks: desktopicon' if data.get('createDesktopShortcut') else ""}
    iss_content = template
    for placeholder, value in replacements.items():
        iss_content = iss_content.replace(placeholder, str(value))
    with open(output_path, 'w', encoding='utf-8-sig') as f:
        f.write(iss_content)
    return output_path
