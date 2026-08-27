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
        candidate = os.path.join(base_path, relative_path)
        if os.path.exists(candidate):
            return candidate
        return candidate
    except Exception:
        pass

    # Dev režim: soubor je v src/generator/exe_builder.py
    # Stuby jsou v src/uninstaller_stub a src/installer_stub
    this_dir = os.path.dirname(os.path.abspath(__file__))  # src/generator
    src_dir = os.path.dirname(this_dir)  # src
    project_root = os.path.dirname(src_dir)  # kořen projektu

    # 1) relativně vůči src/ (pro stuby)
    candidate_src = os.path.join(src_dir, relative_path)
    if os.path.exists(candidate_src):
        return candidate_src

    # 2) relativně vůči src/generator/ (zpětná kompatibilita)
    candidate_gen = os.path.join(this_dir, relative_path)
    if os.path.exists(candidate_gen):
        return candidate_gen

    # 3) relativně vůči kořeni projektu (pro templates, VERSION)
    candidate_root = os.path.join(project_root, relative_path)
    if os.path.exists(candidate_root):
        return candidate_root

    # 4) relativně vůči cwd (poslední záchrana)
    candidate_cwd = os.path.join(os.getcwd(), relative_path)
    if os.path.exists(candidate_cwd):
        return candidate_cwd

    # Vrátíme nejpravděpodobnější (src) aby chyba byla srozumitelná
    return candidate_src

def slugify(value):
    # ... (zachovám původní funkci slugify)
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value).strip().replace(' ', '_')
    return re.sub(r'[-\s]+', '-', value)

def build_installer(data, output_exe_path, progress_callback=None):
    """
    Sestaví samostatný EXE instalátor i odinstalátor pomocí PyInstalleru.
    progress_callback(status_text, percent) - volitelný callback pro hlášení průběhu (0-100 nebo None pro neurčitý).
    """
    def report(text, percent=None):
        if progress_callback:
            try:
                progress_callback(text, percent)
            except Exception:
                pass

    # Rychlá kontrola dostupnosti PyInstalleru před zdlouhavou prací
    if shutil.which("pyinstaller") is None:
        raise Exception("PyInstaller není nainstalován nebo není v PATH. Nainstalujte ho příkazem: pip install pyinstaller")

    safe_name = slugify(data['appName'])
    data['safeName'] = safe_name

    with tempfile.TemporaryDirectory() as tmpdir:
        # --- KROK 1: Sestavení odinstalátoru (Uninstaller) ---
        report("Krok 1/3: Sestavuji odinstalátor...", 10)
        uninst_tmp = os.path.join(tmpdir, "uninst_build")

        # Oprava cesty: použijeme absolutní cestu ke složce pomocí get_resource_path
        uninst_stub = get_resource_path("uninstaller_stub")
        if not os.path.isdir(uninst_stub):
            raise Exception(f"Nenalezena složka odinstalátoru: {uninst_stub}")

        shutil.copytree(uninst_stub, uninst_tmp)

        # Pro odinstalátor nepotřebujeme payload, config si najde v cílové složce
        uninst_cmd = [
            "pyinstaller", "--onefile", "--windowed", "--uac-admin",
            f"--name=uninstall", "--clean", "main.py"
        ]
        try:
            subprocess.run(uninst_cmd, cwd=uninst_tmp, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            raise Exception(f"PyInstaller selhal při sestavování odinstalátoru: {e.stderr.decode('utf-8', errors='ignore')}")
        uninstall_exe_path = os.path.join(uninst_tmp, "dist", "uninstall.exe")
        if not os.path.exists(uninstall_exe_path):
            raise Exception("Odinstalátor nebyl vytvořen (uninstall.exe nenalezen).")

        # --- KROK 2: Příprava hlavního instalátoru (Setup) ---
        report("Krok 2/3: Připravuji soubory instalátoru...", 45)
        stub_dir = get_resource_path("installer_stub")
        if not os.path.isdir(stub_dir):
            raise Exception(f"Nenalezena složka instalátoru: {stub_dir}")
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
        report("Krok 3/3: Sestavuji finální instalátor (může trvat několik minut)...", 70)
        setup_cmd = [
            "pyinstaller", "--onefile", "--windowed", "--uac-admin",
            f"--name={safe_name}_Setup",
            f"--add-data=config.json;.",
            f"--add-data=payload;payload",
            "--clean", "main.py"
        ]
        
        try:
            subprocess.run(setup_cmd, cwd=tmpdir, check=True, capture_output=True)
            report("Dokončuji...", 95)
            
            dist_exe = os.path.join(tmpdir, "dist", f"{safe_name}_Setup.exe")
            if os.path.exists(dist_exe):
                # Zajisti cílový adresář
                out_dir = os.path.dirname(os.path.abspath(output_exe_path))
                if out_dir and not os.path.exists(out_dir):
                    os.makedirs(out_dir, exist_ok=True)
                if os.path.exists(output_exe_path):
                    os.remove(output_exe_path)
                shutil.move(dist_exe, output_exe_path)
                report("Hotovo", 100)
                return True
            return False
        except subprocess.CalledProcessError as e:
            raise Exception(f"PyInstaller selhal při sestavování instalátoru: {e.stderr.decode('utf-8', errors='ignore')}")
