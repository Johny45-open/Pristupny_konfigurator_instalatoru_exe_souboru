import os
import subprocess
import json
import shutil
import tempfile

def build_installer(data, output_exe_path):
    """
    Sestaví samostatný EXE instalátor pomocí PyInstalleru.
    data: slovník s metadaty (appName, appVersion, exePath, dirPath)
    output_exe_path: kam uložit výsledný instalátor
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. Příprava struktury v dočasné složce
        stub_dir = os.path.join(os.path.dirname(__file__), "..", "installer_stub")
        shutil.copytree(stub_dir, tmpdir, dirs_exist_ok=True)
        
        # 2. Vytvoření config.json
        config_path = os.path.join(tmpdir, "config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        
        # 3. Příprava payload (soubory k instalaci)
        payload_dir = os.path.join(tmpdir, "payload")
        if os.path.exists(payload_dir):
            shutil.rmtree(payload_dir)
        os.makedirs(payload_dir)
        
        # Kopírování hlavního EXE
        shutil.copy2(data['exePath'], payload_dir)
        
        # Kopírování složky (pokud existuje)
        if data.get('dirPath') and os.path.exists(data['dirPath']):
            for item in os.listdir(data['dirPath']):
                s = os.path.join(data['dirPath'], item)
                d = os.path.join(payload_dir, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)

        # 4. Spuštění PyInstalleru
        # --uac-admin: Vyžádá práva správce při spuštění instalátoru (nutné pro Program Files)
        cmd = [
            "pyinstaller",
            "--onefile",
            "--windowed",
            "--uac-admin",
            f"--name={data['appName']}_Setup",
            f"--add-data=config.json;.",
            f"--add-data=payload;payload",
            "--clean",
            "main.py"
        ]
        
        try:
            subprocess.run(cmd, cwd=tmpdir, check=True, capture_output=True)
            
            dist_exe = os.path.join(tmpdir, "dist", f"{data['appName']}_Setup.exe")
            if os.path.exists(dist_exe):
                if os.path.exists(output_exe_path):
                    os.remove(output_exe_path)
                shutil.move(dist_exe, output_exe_path)
                return True
            return False
        except subprocess.CalledProcessError as e:
            raise Exception(f"PyInstaller selhal: {e.stderr.decode('utf-8', errors='ignore')}")
