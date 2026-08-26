import os
import subprocess
import json
import shutil
import tempfile
import unicodedata
import re
import sys

def get_resource_path(relative_path):
    """ Získá absolutní cestu ke zdroji, funguje pro vývoj i pro PyInstaller. """
    try:
        # PyInstaller vytvoří dočasnou složku a uloží cestu do _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Pokud neběžíme v PyInstalleru, použijeme cestu vzhledem k tomuto souboru
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)

def slugify(value):
    # ... (zachovám původní funkci slugify)
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value).strip().replace(' ', '_')
    return re.sub(r'[-\s]+', '-', value)

def build_installer(data, output_exe_path):
    """
    Sestaví samostatný EXE instalátor i odinstalátor pomocí PyInstalleru.
    """
    safe_name = slugify(data['appName'])
    data['safeName'] = safe_name

    with tempfile.TemporaryDirectory() as tmpdir:
        # --- KROK 1: Sestavení odinstalátoru (Uninstaller) ---
        uninst_tmp = os.path.join(tmpdir, "uninst_build")

        # Oprava cesty: použijeme absolutní cestu ke složce pomocí get_resource_path
        uninst_stub = get_resource_path("uninstaller_stub")

        shutil.copytree(uninst_stub, uninst_tmp)

        # Pro odinstalátor nepotřebujeme payload, config si najde v cílové složce
        uninst_cmd = [
            "pyinstaller", "--onefile", "--windowed", "--uac-admin",
            f"--name=uninstall", "--clean", "main.py"
        ]
        subprocess.run(uninst_cmd, cwd=uninst_tmp, check=True, capture_output=True)
        uninstall_exe_path = os.path.join(uninst_tmp, "dist", "uninstall.exe")

        # --- KROK 2: Příprava hlavního instalátoru (Setup) ---
        stub_dir = get_resource_path("installer_stub")
        shutil.copytree(stub_dir, tmpdir, dirs_exist_ok=True)
        # ... (zbytek zůstává)**
        # Vytvoření config.json
        config_path = os.path.join(tmpdir, "config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        
        # Příprava payload
        payload_dir = os.path.join(tmpdir, "payload")
        if os.path.exists(payload_dir):
            shutil.rmtree(payload_dir)
        os.makedirs(payload_dir)
        
        # Přidáme uninstall.exe do payloadu
        shutil.copy2(uninstall_exe_path, payload_dir)
        
        # Přidáme soubory uživatele
        shutil.copy2(data['exePath'], payload_dir)
        
        # Pokud je vybrána složka aplikace (obsahující _internal, lib, atd.)
        if data.get('dirPath') and os.path.exists(data['dirPath']):
            dir_path = os.path.abspath(data['dirPath'])
            for item in os.listdir(dir_path):
                # Nekopírujeme znovu samotný EXE, pokud už tam je
                if item == os.path.basename(data['exePath']):
                    continue
                    
                s = os.path.join(dir_path, item)
                d = os.path.join(payload_dir, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)
        else:
            # Pokud složka vybrána nebyla, zkusíme najít _internal/lib vedle EXE automaticky
            exe_dir = os.path.dirname(os.path.abspath(data['exePath']))
            for extra in ["_internal", "lib", "tcl", "tk"]:
                extra_path = os.path.join(exe_dir, extra)
                if os.path.exists(extra_path) and os.path.isdir(extra_path):
                    shutil.copytree(extra_path, os.path.join(payload_dir, extra), dirs_exist_ok=True)

        # --- KROK 3: Sestavení finálního Setup.exe ---
        setup_cmd = [
            "pyinstaller", "--onefile", "--windowed", "--uac-admin",
            f"--name={safe_name}_Setup",
            f"--add-data=config.json;.",
            f"--add-data=payload;payload",
            "--clean", "main.py"
        ]
        
        try:
            subprocess.run(setup_cmd, cwd=tmpdir, check=True, capture_output=True)
            
            dist_exe = os.path.join(tmpdir, "dist", f"{safe_name}_Setup.exe")
            if os.path.exists(dist_exe):
                if os.path.exists(output_exe_path):
                    os.remove(output_exe_path)
                shutil.move(dist_exe, output_exe_path)
                return True
            return False
        except subprocess.CalledProcessError as e:
            raise Exception(f"PyInstaller selhal: {e.stderr.decode('utf-8', errors='ignore')}")
