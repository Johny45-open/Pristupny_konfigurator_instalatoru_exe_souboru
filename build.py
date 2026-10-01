import subprocess
import sys
import os
import re
import argparse


def get_current_version():
    """Načte verzi z VERSION souboru."""
    version_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "VERSION")
    if not os.path.exists(version_file):
        version_file = os.path.join(os.getcwd(), "VERSION")
    try:
        with open(version_file, "r", encoding="utf-8") as f:
            v = f.read().strip()
            if re.match(r"^\d+\.\d+\.\d+", v):
                return v, version_file
    except Exception:
        pass
    return "0.0.0-dev", version_file


def bump_version(version, bump_type):
    """Inkrementuje verzi podle bump_type."""
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)", version)
    if not m:
        print(f"Varování: Neplatný formát verze '{version}', používám 0.0.0 jako základ.")
        maj, min_, pat = 0, 0, 0
    else:
        maj, min_, pat = map(int, m.groups())
    if bump_type == "patch":
        pat += 1
    elif bump_type == "minor":
        min_ += 1
        pat = 0
    elif bump_type == "major":
        maj += 1
        min_ = 0
        pat = 0
    return f"{maj}.{min_}.{pat}"


def generate_version_info(version, output_path):
    """Vygeneruje version_info.txt (VSVersionInfo) pro PyInstaller z verze.

    Zajisti, aby mel vysledny EXE verzi i ve Vlastnostech souboru
    (Pravy klik -> Vlastnosti -> Podrobnosti). Pri neplatnem formatu
    pouzije 0.0.0. V resourcech se umyslne nepouziva diakritika,
    aby nedelala problemy se kodovanim na ruznych Windows.
    """
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)", version.strip())
    if m:
        maj, min_, pat = map(int, m.groups())
    else:
        print(f"Varování: Neplatný formát verze '{version}' pro version_info, používám 0.0.0.")
        maj, min_, pat = 0, 0, 0
    clean_version = f"{maj}.{min_}.{pat}"
    content = f"""# UTF-8
# Generovano automaticky z VERSION ({version}) - needitovat rucne.
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({maj}, {min_}, {pat}, 0),
    prodvers=({maj}, {min_}, {pat}, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'Johny45-open'),
        StringStruct(u'FileDescription', u'Pristupny konfigurator instalatoru EXE souboru'),
        StringStruct(u'FileVersion', u'{clean_version}'),
        StringStruct(u'InternalName', u'Konfigurator'),
        StringStruct(u'LegalCopyright', u'MIT'),
        StringStruct(u'OriginalFilename', u'Konfigurator.exe'),
        StringStruct(u'ProductName', u'Pristupny konfigurator instalatoru'),
        StringStruct(u'ProductVersion', u'{clean_version}')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"version_info vygenerován: {output_path} (verze {clean_version})")
        return output_path
    except Exception as e:
        print(f"Varování: Nepodařilo se zapsat version_info: {e}")
        return None


def build():
    parser = argparse.ArgumentParser(description="Sestavení Konfigurátoru")
    parser.add_argument("--no-bump", action="store_true", help="Neinkrementovat verzi v VERSION (respektuje ruční editaci)")
    parser.add_argument("--bump", choices=["patch", "minor", "major", "no"], default="no",
                        help="Typ bumpu verze (default: no). 'no' = stejné jako --no-bump")
    args = parser.parse_args()

    # Zpracování verze
    version, version_file = get_current_version()
    print(f"Aktuální verze konfigurátoru: {version}")

    should_bump = not args.no_bump and args.bump != "no"
    if should_bump:
        new_version = bump_version(version, args.bump)
        print(f"Auto-bump ({args.bump}): {version} -> {new_version}")
        try:
            with open(version_file, "w", encoding="utf-8") as f:
                f.write(new_version + "\n")
            version = new_version
            print(f"VERSION aktualizován: {version_file}")
        except Exception as e:
            print(f"Varování: Nepodařilo se zapsat VERSION: {e}")
    else:
        print(f"Verze zachována (ruční režim): {version}")

    # Definice cest ke zdrojům, které PyInstaller potřebuje
    # Formát je "zdroj;cíl", kde cíl je relativní cesta uvnitř balíčku
    # Pozor: stuby jsou v src/, templates a VERSION v kořeni
    # Použijeme absolutní cesty podle umístění build.py, aby fungovalo odkudkoli je spuštěn
    project_root = os.path.dirname(os.path.abspath(__file__))

    # Verze do metadat EXE (Vlastnosti souboru -> Podrobnosti)
    version_info_path = os.path.join(project_root, "version_info.txt")
    generated = generate_version_info(version, version_info_path)

    datas = [
        (os.path.join(project_root, "src", "uninstaller_stub") + ";uninstaller_stub"),
        (os.path.join(project_root, "src", "installer_stub") + ";installer_stub"),
        (os.path.join(project_root, "src", "updater_stub") + ";updater_stub"),
        (os.path.join(project_root, "templates") + ";templates"),
        (os.path.join(project_root, "VERSION") + ";."),
    ]

    cmd = [
        "pyinstaller",
        "--onefile",
        "--windowed",
        "--name", "Konfigurator",
        "--clean",
        "--hidden-import=core.config",
        "--hidden-import=core.manifest",
        "--hidden-import=core.live_announcer",
    ]

    # Přidání datových souborů
    for data in datas:
        cmd.extend(["--add-data", data])

    # Verze do metadat EXE (Vlastnosti -> Podrobnosti)
    if generated:
        cmd.extend(["--version-file", version_info_path])

    # Hlavní skript (absolutní cesta)
    cmd.append(os.path.join(project_root, "src", "main.py"))

    print("Spouštím sestavení pomocí PyInstalleru...")
    try:
        subprocess.run(cmd, check=True, cwd=project_root)
        print("Sestavení proběhlo úspěšně.")
        print(f"Výstup: {os.path.join(project_root, 'dist', 'Konfigurator.exe')}")
        print(f"FINAL_VERSION={version}")
    except subprocess.CalledProcessError as e:
        print(f"Sestavení selhalo: {e}")
        sys.exit(1)

if __name__ == "__main__":
    build()
