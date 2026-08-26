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


def build():
    parser = argparse.ArgumentParser(description="Sestavení Konfigurátoru")
    parser.add_argument("--no-bump", action="store_true", help="Neinkrementovat verzi v VERSION (respektuje ruční editaci)")
    parser.add_argument("--bump", choices=["patch", "minor", "major", "no"], default="patch",
                        help="Typ bumpu verze (default: patch). 'no' = stejné jako --no-bump")
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
    datas = [
        (os.path.join(project_root, "src", "uninstaller_stub") + ";uninstaller_stub"),
        (os.path.join(project_root, "src", "installer_stub") + ";installer_stub"),
        (os.path.join(project_root, "templates") + ";templates"),
        (os.path.join(project_root, "VERSION") + ";."),
    ]

    cmd = [
        "pyinstaller",
        "--onefile",
        "--windowed",
        "--name", "Konfigurator",
        "--clean"
    ]

    # Přidání datových souborů
    for data in datas:
        cmd.extend(["--add-data", data])

    # Hlavní skript (absolutní cesta)
    cmd.append(os.path.join(project_root, "src", "main.py"))

    print("Spouštím sestavení pomocí PyInstalleru...")
    try:
        subprocess.run(cmd, check=True, cwd=project_root)
        print("Sestavení proběhlo úspěšně.")
        print(f"Výstup: {os.path.join(project_root, 'dist', 'Konfigurator.exe')}")
    except subprocess.CalledProcessError as e:
        print(f"Sestavení selhalo: {e}")
        sys.exit(1)

if __name__ == "__main__":
    build()
