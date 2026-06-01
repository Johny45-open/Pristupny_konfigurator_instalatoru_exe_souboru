import os
import subprocess
import json
import shutil
import tempfile
import unicodedata
import re

def slugify(value):
    """
    Převede text na bezpečný název pro souborový systém (bez diakritiky, mezer a spec. znaků).
    Např. "Přístupná Aplikace 1.0" -> "Pristupna_Aplikace_10"
    """
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value).strip().replace(' ', '_')
    return re.sub(r'[-\s]+', '-', value)

def build_installer(data, output_exe_path):
    """
    Sestaví samostatný EXE instalátor pomocí PyInstalleru.
    """
    # Vytvoříme bezpečný název pro souborový systém
    safe_name = slugify(data['appName'])
    data['safeName'] = safe_name # Přidáme do dat pro instalátor

    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. Příprava struktury v dočasné složce
        stub_dir = os.path.join(os.path.dirname(__file__), "..", "installer_stub")
        shutil.copytree(stub_dir, tmpdir, dirs_exist_ok=True)
        
        # 2. Vytvoření config.json (obsahuje hezký i bezpečný název)
        config_path = os.path.join(tmpdir, "config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        
        # 3. Příprava payload
        payload_dir = os.path.join(tmpdir, "payload")
        if os.path.exists(payload_dir):
            shutil.rmtree(payload_dir)
        os.makedirs(payload_dir)
        
        shutil.copy2(data['exePath'], payload_dir)
        
        if data.get('dirPath') and os.path.exists(data['dirPath']):
            for item in os.listdir(data['dirPath']):
                s = os.path.join(data['dirPath'], item)
                d = os.path.join(payload_dir, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)

        # 4. Spuštění PyInstalleru s BEZPEČNÝM názvem
        cmd = [
            "pyinstaller",
            "--onefile",
            "--windowed",
            "--uac-admin",
            f"--name={safe_name}_Setup", # Používáme bezpečný název pro soubor
            f"--add-data=config.json;.",
            f"--add-data=payload;payload",
            "--clean",
            "main.py"
        ]
        
        try:
            subprocess.run(cmd, cwd=tmpdir, check=True, capture_output=True)
            
            dist_exe = os.path.join(tmpdir, "dist", f"{safe_name}_Setup.exe")
            if os.path.exists(dist_exe):
                if os.path.exists(output_exe_path):
                    os.remove(output_exe_path)
                shutil.move(dist_exe, output_exe_path)
                return True
            return False
        except subprocess.CalledProcessError as e:
            raise Exception(f"PyInstaller selhal: {e.stderr.decode('utf-8', errors='ignore')}")
