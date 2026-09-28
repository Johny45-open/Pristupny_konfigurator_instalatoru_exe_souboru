import os
import subprocess
import json
import shutil
import tempfile
import unicodedata
import re
import sys

try:
    from core.config import sanitize_runtime_config, slugify
except ImportError:
    try:
        from src.core.config import sanitize_runtime_config, slugify
    except ImportError:
        def slugify(value):
            value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
            value = re.sub(r'[^\w\s-]', '', value).strip().replace(' ', '_')
            return re.sub(r'[-\s]+', '-', value)
        sanitize_runtime_config = None  # type: ignore

def get_resource_path(relative_path):
    """ Získá absolutní cestu ke zdroji, funguje pro vývoj i pro PyInstaller. """
    try:
        base_path = sys._MEIPASS  # type: ignore
        candidate = os.path.join(base_path, relative_path)
        if os.path.exists(candidate):
            return candidate
        return candidate
    except Exception:
        pass
    this_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.dirname(this_dir)
    project_root = os.path.dirname(src_dir)
    candidate_src = os.path.join(src_dir, relative_path)
    if os.path.exists(candidate_src):
        return candidate_src
    candidate_gen = os.path.join(this_dir, relative_path)
    if os.path.exists(candidate_gen):
        return candidate_gen
    candidate_root = os.path.join(project_root, relative_path)
    if os.path.exists(candidate_root):
        return candidate_root
    candidate_cwd = os.path.join(os.getcwd(), relative_path)
    if os.path.exists(candidate_cwd):
        return candidate_cwd
    return candidate_src

def _run_pyinstaller(cmd, cwd, timeout=600):
    """Spustí PyInstaller bez deadlocku (Popen + communicate s timeoutem)."""
    proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore")
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            stdout, stderr = proc.communicate(timeout=10)
        except Exception:
            stdout, stderr = "", "timeout"
        raise Exception(f"PyInstaller timeout po {timeout}s. stdout: {stdout[:2000]} stderr: {stderr[:4000]}")
    if proc.returncode != 0:
        err = (stderr or stdout or "").strip()
        raise Exception(f"PyInstaller selhal (code {proc.returncode}): {err[:4000]}")
    return stdout, stderr

def _prepare_runtime(data):
    """Validuje vstup a vrátí (safe_name, runtime_config). Sdílené pro installer i updater."""
    if not data.get("appName") or not str(data["appName"]).strip():
        raise ValueError("Název aplikace je povinný")
    if not data.get("exePath") or not os.path.exists(str(data["exePath"])):
        raise ValueError(f"EXE soubor neexistuje: {data.get('exePath')}")
    if sanitize_runtime_config is not None:
        try:
            runtime_for_name = sanitize_runtime_config(data)
            safe_name = runtime_for_name.get("safeName") or slugify(str(data["appName"]))
        except Exception:
            safe_name = slugify(str(data["appName"]))
    else:
        safe_name = slugify(str(data["appName"]))
    data["safeName"] = safe_name
    if sanitize_runtime_config is not None:
        try:
            runtime_config = sanitize_runtime_config(data)
        except Exception as e:
            raise ValueError(f"Neplatná konfigurace: {e}")
    else:
        runtime_config = {"appName": str(data.get("appName", "")).strip(), "appVersion": str(data.get("appVersion", "")).strip() or "1.0.0", "appAuthor": str(data.get("appAuthor", "")).strip(), "safeName": safe_name, "exeName": os.path.basename(str(data.get("exePath", ""))), "installDir": int(data.get("installDir", 0)) if str(data.get("installDir", 0)).isdigit() else 0, "createDesktopShortcut": bool(data.get("createDesktopShortcut", True)), "createStartMenuShortcut": bool(data.get("createStartMenuShortcut", True))}
    return safe_name, runtime_config


def _copy_app_payload(data, payload_dir):
    """Zkopíruje EXE + vedlejší soubory do payload_dir (bez uninstall.exe)."""
    EXCLUDED_EXTS = {".pdb", ".log", ".tmp", ".ilk"}
    os.makedirs(payload_dir, exist_ok=True)
    shutil.copy2(data["exePath"], payload_dir)
    if data.get("dirPath") and os.path.exists(data["dirPath"]):
        dir_path = os.path.abspath(data["dirPath"])
        for item in os.listdir(dir_path):
            if item == os.path.basename(data["exePath"]):
                continue
            if os.path.splitext(item)[1].lower() in EXCLUDED_EXTS:
                continue
            s = os.path.join(dir_path, item)
            d = os.path.join(payload_dir, item)
            try:
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True, ignore=shutil.ignore_patterns("*.pdb", "*.log", "*.tmp", "*.ilk", "__pycache__"))
                else:
                    shutil.copy2(s, d)
            except Exception:
                pass
    else:
        exe_dir = os.path.dirname(os.path.abspath(data["exePath"]))
        for extra in ["_internal", "lib", "tcl", "tk"]:
            extra_path = os.path.join(exe_dir, extra)
            if os.path.exists(extra_path) and os.path.isdir(extra_path):
                try:
                    shutil.copytree(extra_path, os.path.join(payload_dir, extra), dirs_exist_ok=True, ignore=shutil.ignore_patterns("*.pdb", "*.log", "*.tmp", "__pycache__"))
                except Exception:
                    pass


def _move_dist(tmpdir, dist_name, output_exe_path, progress_callback=None):
    dist_exe = os.path.join(tmpdir, "dist", dist_name)
    if os.path.exists(dist_exe):
        out_dir = os.path.dirname(os.path.abspath(output_exe_path))
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)
        if os.path.exists(output_exe_path):
            os.remove(output_exe_path)
        shutil.move(dist_exe, output_exe_path)
        if progress_callback:
            try:
                progress_callback("Hotovo", 100)
            except Exception:
                pass
        return True
    return False


def build_installer(data, output_exe_path, progress_callback=None):
    def report(text, percent=None):
        if progress_callback:
            try:
                progress_callback(text, percent)
            except Exception:
                pass
    if shutil.which("pyinstaller") is None:
        raise Exception("PyInstaller není nainstalován nebo není v PATH. Nainstalujte ho příkazem: pip install pyinstaller")
    safe_name, runtime_config = _prepare_runtime(data)
    with tempfile.TemporaryDirectory() as tmpdir:
        report("Krok 1/3: Sestavuji odinstalátor...", 10)
        uninst_tmp = os.path.join(tmpdir, "uninst_build")
        uninst_stub = get_resource_path("uninstaller_stub")
        if not os.path.isdir(uninst_stub):
            raise Exception(f"Nenalezena složka odinstalátoru: {uninst_stub}")
        shutil.copytree(uninst_stub, uninst_tmp)
        uninst_cmd = ["pyinstaller", "--onefile", "--windowed", "--uac-admin", f"--name=uninstall", "--clean", "main.py"]
        _run_pyinstaller(uninst_cmd, cwd=uninst_tmp, timeout=600)
        uninstall_exe_path = os.path.join(uninst_tmp, "dist", "uninstall.exe")
        if not os.path.exists(uninstall_exe_path):
            raise Exception("Odinstalátor nebyl vytvořen (uninstall.exe nenalezen).")
        report("Krok 2/3: Připravuji soubory instalátoru...", 45)
        stub_dir = get_resource_path("installer_stub")
        if not os.path.isdir(stub_dir):
            raise Exception(f"Nenalezena složka instalátoru: {stub_dir}")
        shutil.copytree(stub_dir, tmpdir, dirs_exist_ok=True)
        config_path = os.path.join(tmpdir, "config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(runtime_config, f, ensure_ascii=False, indent=2)
        payload_dir = os.path.join(tmpdir, "payload")
        if os.path.exists(payload_dir):
            shutil.rmtree(payload_dir)
        os.makedirs(payload_dir)
        shutil.copy2(uninstall_exe_path, payload_dir)
        _copy_app_payload(data, payload_dir)
        report("Krok 3/3: Sestavuji finální instalátor (může trvat několik minut)...", 70)
        setup_cmd = ["pyinstaller", "--onefile", "--windowed", "--uac-admin", f"--name={safe_name}_Setup", "--add-data=config.json;.", "--add-data=payload;payload", "--clean", "main.py"]
        _run_pyinstaller(setup_cmd, cwd=tmpdir, timeout=600)
        report("Dokončuji...", 95)
        return _move_dist(tmpdir, f"{safe_name}_Setup.exe", output_exe_path, progress_callback)


def build_updater(data, output_exe_path, progress_callback=None):
    """Sestaví offline aktualizační EXE ({safeName}_Update.exe) z updater_stub.

    Payload obsahuje jen soubory aplikace (bez uninstall.exe) + config.json s novou verzí.
    Aktualizace na cílovém PC vyžaduje existující manifest z instalátoru.
    """
    def report(text, percent=None):
        if progress_callback:
            try:
                progress_callback(text, percent)
            except Exception:
                pass
    if shutil.which("pyinstaller") is None:
        raise Exception("PyInstaller není nainstalován nebo není v PATH. Nainstalujte ho příkazem: pip install pyinstaller")
    safe_name, runtime_config = _prepare_runtime(data)
    with tempfile.TemporaryDirectory() as tmpdir:
        report("Krok 1/2: Připravuji soubory aktualizace...", 20)
        stub_dir = get_resource_path("updater_stub")
        if not os.path.isdir(stub_dir):
            raise Exception(f"Nenalezena složka aktualizátoru: {stub_dir}")
        shutil.copytree(stub_dir, tmpdir, dirs_exist_ok=True)
        config_path = os.path.join(tmpdir, "config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(runtime_config, f, ensure_ascii=False, indent=2)
        payload_dir = os.path.join(tmpdir, "payload")
        if os.path.exists(payload_dir):
            shutil.rmtree(payload_dir)
        os.makedirs(payload_dir)
        _copy_app_payload(data, payload_dir)
        report("Krok 2/2: Sestavuji aktualizační program (může trvat několik minut)...", 60)
        update_cmd = ["pyinstaller", "--onefile", "--windowed", "--uac-admin", f"--name={safe_name}_Update", "--add-data=config.json;.", "--add-data=payload;payload", "--clean", "main.py"]
        _run_pyinstaller(update_cmd, cwd=tmpdir, timeout=600)
        report("Dokončuji...", 95)
        return _move_dist(tmpdir, f"{safe_name}_Update.exe", output_exe_path, progress_callback)
