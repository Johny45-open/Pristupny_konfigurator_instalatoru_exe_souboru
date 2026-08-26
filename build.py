import subprocess
import sys
import os

def build():
    # Definice cest ke zdrojům, které PyInstaller potřebuje
    # Formát je "zdroj;cíl", kde cíl je relativní cesta uvnitř balíčku
    datas = [
        ("uninstaller_stub;uninstaller_stub"),
        ("installer_stub;installer_stub"),
        ("templates;templates")
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

    # Hlavní skript
    cmd.append("src/main.py")

    print("Spouštím sestavení pomocí PyInstalleru...")
    try:
        subprocess.run(cmd, check=True)
        print("Sestavení proběhlo úspěšně.")
    except subprocess.CalledProcessError as e:
        print(f"Sestavení selhalo: {e}")
        sys.exit(1)

if __name__ == "__main__":
    build()
