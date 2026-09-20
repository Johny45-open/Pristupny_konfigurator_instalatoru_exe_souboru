import sys
import os
import shutil
import json
import subprocess
import time
from PyQt6.QtWidgets import (QApplication, QWizard, QWizardPage, QVBoxLayout,
                             QLabel, QProgressBar, QMessageBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAccessible

MANIFEST_FILENAME = "install_manifest.json"
CONFIG_FILENAME = "install_config.json"

PROTECTED_DIRS = [
    os.path.abspath(os.environ.get("SystemRoot", r"C:\Windows")),
    os.path.abspath(os.environ.get("SystemRoot", r"C:\Windows") + r"\System32"),
    os.path.abspath("C:\\"),
    os.path.abspath("C:/"),
]

def is_protected_dir(path: str) -> bool:
    try:
        p = os.path.abspath(path).rstrip(os.sep).lower()
        for prot in PROTECTED_DIRS:
            pp = os.path.abspath(prot).rstrip(os.sep).lower()
            if p == pp:
                return True
        if len(p) <= 3:
            return True
    except Exception:
        return True
    return False

def get_powershell_path():
    system_root = os.environ.get('SystemRoot', r'C:\Windows')
    candidates = [
        os.path.join(system_root, 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe'),
        os.path.join(system_root, 'Sysnative', 'WindowsPowerShell', 'v1.0', 'powershell.exe'),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return candidates[0]


def get_known_folder(folder_id):
    mapping = {
        'desktop': 'Desktop',
        'commondesktop': 'CommonDesktopDirectory',
        'programs': 'Programs',
        'commonprograms': 'CommonPrograms',
        'startmenu': 'StartMenu',
    }
    net_name = mapping.get(folder_id.lower(), folder_id)
    try:
        ps_path = get_powershell_path()
        ps_cmd = f"[Environment]::GetFolderPath('{net_name}')"
        result = subprocess.run(
            [ps_path, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            p = result.stdout.strip()
            if p:
                return p
    except Exception:
        pass

    if folder_id.lower() == 'desktop':
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders') as k:
                v, _ = winreg.QueryValueEx(k, 'Desktop')
                exp = os.path.expandvars(v)
                if exp:
                    return exp
        except Exception:
            pass
        for name in ['Desktop', 'Plocha']:
            p = os.path.join(os.environ.get('USERPROFILE', ''), name)
            if os.path.isdir(p):
                return p
        return os.path.join(os.environ.get('USERPROFILE', ''), 'Desktop')

    if folder_id.lower() in ('programs', 'startmenu'):
        return os.path.join(os.environ.get('APPDATA', ''), 'Microsoft', 'Windows', 'Start Menu', 'Programs')
    if folder_id.lower() == 'commonprograms':
        return os.path.join(os.environ.get('PROGRAMDATA', r'C:\ProgramData'), 'Microsoft', 'Windows', 'Start Menu', 'Programs')
    if folder_id.lower() == 'commondesktop':
        return os.path.join(os.environ.get('PUBLIC', r'C:\Users\Public'), 'Desktop')
    return ""


def collect_shortcut_candidates(app_name):
    """Vrátí seznam možných cest k zástupcům (řeší CZ Plocha vs Desktop, uživatel vs společná)."""
    candidates = []
    desktop = get_known_folder('Desktop')
    if desktop:
        candidates.append(os.path.join(desktop, f"{app_name}.lnk"))
        for alt in ['Desktop', 'Plocha']:
            alt_path = os.path.join(os.environ.get('USERPROFILE', ''), alt, f"{app_name}.lnk")
            if alt_path not in candidates:
                candidates.append(alt_path)
    common_desktop = get_known_folder('CommonDesktopDirectory')
    if common_desktop:
        candidates.append(os.path.join(common_desktop, f"{app_name}.lnk"))

    programs = get_known_folder('Programs')
    if programs:
        candidates.append(os.path.join(programs, f"{app_name}.lnk"))
    common_programs = get_known_folder('CommonPrograms')
    if common_programs:
        candidates.append(os.path.join(common_programs, f"{app_name}.lnk"))

    seen = set()
    uniq = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    return uniq

class UninstallationThread(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    announce = pyqtSignal(str)
    finished = pyqtSignal(bool, str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, install_dir, config):
        super().__init__()
        self.install_dir = os.path.abspath(install_dir)
        self.config = config

    def run(self):
        try:
            if is_protected_dir(self.install_dir):
                self.status.emit("Chráněný adresář – odinstalace zrušena.")
                self.announce.emit("Chráněný adresář, odinstalace zrušena")
                self.finished.emit(False, f"Instalační adresář je chráněný: {self.install_dir}")
                self.finished_signal.emit(False, f"Instalační adresář je chráněný: {self.install_dir}")
                return

            # Načtení manifestu – manifest-only mazání
            manifest_path = os.path.join(self.install_dir, MANIFEST_FILENAME)
            manifest = None
            if os.path.exists(manifest_path):
                try:
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        manifest = json.load(f)
                except Exception:
                    manifest = None

            if manifest is None:
                # Fallback když manifest chybí → chyba bez blank delete
                # Nikdy nemazat naslepo celý adresář
                self.status.emit("Manifest nenalezen – nelze bezpečně odinstalovat.")
                self.announce.emit("Manifest nenalezen, odinstalace přerušena")
                msg = "Nebyly nalezeny informace o instalaci (manifest chybí nebo je poškozen). Odinstalace byla zrušena, aby nedošlo ke smazání cizích souborů."
                self.finished.emit(False, msg)
                self.finished_signal.emit(False, msg)
                return

            # Odstranění zástupců – podle manifestu + candidates
            app_name = self.config.get('appName', manifest.get('appName', 'Aplikace'))
            shortcuts = manifest.get("shortcuts", [])
            # Nejprve dle manifestu
            for sc in shortcuts:
                if self.isInterruptionRequested():
                    self.announce.emit("Odinstalace přerušena uživatelem")
                    self.finished.emit(False, "Odinstalace zrušena uživatelem.")
                    self.finished_signal.emit(False, "Odinstalace zrušena uživatelem.")
                    return
                sc_path = sc.get("path", "") if isinstance(sc, dict) else str(sc)
                if sc_path and os.path.exists(sc_path):
                    try:
                        if 'Desktop' in sc_path or 'Plocha' in sc_path:
                            self.status.emit("Odstraňuji zástupce na ploše...")
                        else:
                            self.status.emit("Odstraňuji zástupce v nabídce Start...")
                        self.announce.emit("Odstraňuji zástupce")
                        os.remove(sc_path)
                    except Exception:
                        pass
            # Dále zkus candidate cesty (pro jistotu)
            for shortcut in collect_shortcut_candidates(app_name):
                if self.isInterruptionRequested():
                    self.announce.emit("Odinstalace přerušena uživatelem")
                    self.finished.emit(False, "Odinstalace zrušena uživatelem.")
                    self.finished_signal.emit(False, "Odinstalace zrušena uživatelem.")
                    return
                if os.path.exists(shortcut):
                    # Ověř, že zástupce není mimo očekávání – pouze mažeme .lnk
                    if shortcut.lower().endswith(".lnk"):
                        try:
                            os.remove(shortcut)
                        except Exception:
                            pass

            files = manifest.get("files", [])
            dirs = manifest.get("dirs", [])

            total = len(files) + len(dirs)
            if total == 0:
                # Odstraň manifest a config nakonec
                for extra in [MANIFEST_FILENAME, CONFIG_FILENAME]:
                    try:
                        p = os.path.join(self.install_dir, extra)
                        if os.path.exists(p):
                            os.remove(p)
                    except Exception:
                        pass
                self.progress.emit(100)
                self.announce.emit("Odinstalace dokončena")
                self.finished.emit(True, "Program byl úspěšně odinstalován.")
                self.finished_signal.emit(True, "Program byl úspěšně odinstalován.")
                return

            count = 0
            # Maž jen manifest.files – kontrola is_protected_dir a path uvnitř install_dir
            for rel in files:
                if self.isInterruptionRequested():
                    self.announce.emit("Odinstalace přerušena uživatelem")
                    self.finished.emit(False, "Odinstalace zrušena uživatelem.")
                    self.finished_signal.emit(False, "Odinstalace zrušena uživatelem.")
                    return
                abs_path = os.path.abspath(os.path.join(self.install_dir, rel))
                # Kontrola, zda path je uvnitř install_dir
                try:
                    common = os.path.commonpath([self.install_dir.lower(), abs_path.lower()])
                except ValueError:
                    common = ""
                if common != self.install_dir.lower():
                    continue
                if is_protected_dir(abs_path) or is_protected_dir(os.path.dirname(abs_path)):
                    continue
                if os.path.exists(abs_path):
                    # Nepokoušíme se smazat uninstall.exe pokud běžíme (but manifest should not contain it if running?)
                    if "uninstall" in os.path.basename(abs_path).lower():
                        # přeskoč, smažeme později pokud možno
                        pass
                    else:
                        try:
                            if os.path.isdir(abs_path):
                                shutil.rmtree(abs_path)
                            else:
                                os.remove(abs_path)
                        except Exception:
                            pass
                count += 1
                percent = int((count / total) * 100)
                self.progress.emit(percent)
                self.status.emit(f"Odstraňuji: {rel}")
                if count % 5 == 0:
                    self.announce.emit(f"Odstraňování {percent} procent")

            # Maž manifest.dirs (seřazené od nejhlubších)
            for rel in dirs:
                if self.isInterruptionRequested():
                    self.announce.emit("Odinstalace přerušena uživatelem")
                    self.finished.emit(False, "Odinstalace zrušena uživatelem.")
                    self.finished_signal.emit(False, "Odinstalace zrušena uživatelem.")
                    return
                abs_path = os.path.abspath(os.path.join(self.install_dir, rel))
                try:
                    common = os.path.commonpath([self.install_dir.lower(), abs_path.lower()])
                except ValueError:
                    common = ""
                if common != self.install_dir.lower():
                    continue
                if is_protected_dir(abs_path):
                    continue
                if os.path.exists(abs_path) and os.path.isdir(abs_path):
                    try:
                        if not os.listdir(abs_path):
                            os.rmdir(abs_path)
                        else:
                            # Pokud není prázdný, zkus rmtree jen pokud je uvnitř install_dir
                            shutil.rmtree(abs_path)
                    except Exception:
                        pass
                count += 1
                percent = int((count / total) * 100)
                self.progress.emit(percent)
                self.status.emit(f"Odstraňuji složku: {rel}")

            # Nakonec odstraň manifest a config
            for extra in [MANIFEST_FILENAME, CONFIG_FILENAME]:
                try:
                    p = os.path.join(self.install_dir, extra)
                    if os.path.exists(p) and not is_protected_dir(p):
                        os.remove(p)
                except Exception:
                    pass

            # Pokud je adresář prázdný, zkus ho smazat (ale ne pokud chráněný)
            try:
                if os.path.exists(self.install_dir) and not os.listdir(self.install_dir):
                    if not is_protected_dir(self.install_dir):
                        os.rmdir(self.install_dir)
                elif os.path.exists(self.install_dir) and len(os.listdir(self.install_dir)) == 1 and "uninstall.exe" in os.listdir(self.install_dir)[0].lower():
                    # zbyl jen uninstall.exe – ponech, uživatel smaže ručně
                    pass
            except Exception:
                pass

            self.progress.emit(100)
            self.announce.emit("Odinstalace dokončena na 100 procent")
            self.finished.emit(True, "Program byl úspěšně odinstalován.")
            self.finished_signal.emit(True, "Program byl úspěšně odinstalován.")
        except Exception as e:
            self.finished.emit(False, str(e))
            self.finished_signal.emit(False, str(e))

class IntroPage(QWizardPage):
    def __init__(self, config, install_dir):
        super().__init__()
        self.config = config
        self.install_dir = install_dir
        self.setTitle("Odinstalace")
        text = f"Chcete skutečně odinstalovat program {config['appName']}?\n\nStiskněte tlačítko Další pro zahájení odinstalace."
        self.setAccessibleName("Úvodní stránka odinstalace")

        layout = QVBoxLayout()
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.label.setAccessibleName(text)
        layout.addWidget(self.label)

        # manifestInfo – zobraz info z manifestu
        manifest_path = os.path.join(install_dir, MANIFEST_FILENAME)
        manifest_info = ""
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    m = json.load(f)
                manifest_info = f"Instalováno: {m.get('version','')} do {m.get('installDir','')} ({len(m.get('files',[]))} souborů)"
            except Exception:
                manifest_info = "Manifest poškozen."
        else:
            manifest_info = "Manifest nenalezen – odinstalace bude odmítnuta."
        self.manifestInfo = QLabel(manifest_info)
        self.manifestInfo.setWordWrap(True)
        self.manifestInfo.setAccessibleName(manifest_info)
        self.manifestInfo.setStyleSheet("color: #555;")
        layout.addWidget(self.manifestInfo)

        self.setLayout(layout)

    def initializePage(self):
        self.label.setFocus()

class ProgressPage(QWizardPage):
    def __init__(self, config, install_dir):
        super().__init__()
        self.config = config
        self.install_dir = install_dir
        self.setTitle("Průběh odinstalace")
        text = "Probíhá odstraňování souborů, prosím čekejte."
        self.setAccessibleName(text)

        layout = QVBoxLayout()
        self.label = QLabel(text)
        self.label.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.label.setAccessibleName(text)
        layout.addWidget(self.label)

        self.statusLabel = QLabel("Připraveno...")
        layout.addWidget(self.statusLabel)

        self.liveLabel = QLabel("")
        self.liveLabel.setAccessibleName("")
        layout.addWidget(self.liveLabel)

        self.progressBar = QProgressBar()
        self.progressBar.setAccessibleName("Průběh v procentech")
        layout.addWidget(self.progressBar)
        self.setLayout(layout)
        self._last_announce = 0

    def initializePage(self):
        self.label.setFocus()
        self.wizard().button(QWizard.WizardButton.BackButton).setEnabled(False)
        self.wizard()._uninstall_thread = UninstallationThread(self.install_dir, self.config)
        self.wizard()._uninstall_thread.progress.connect(self.progressBar.setValue)
        self.wizard()._uninstall_thread.status.connect(self.update_status)
        self.wizard()._uninstall_thread.announce.connect(self.on_announce)
        # Podporujeme oba názvy signálu
        try:
            self.wizard()._uninstall_thread.finished.connect(self.on_finished)
        except Exception:
            pass
        try:
            self.wizard()._uninstall_thread.finished_signal.connect(self.on_finished)
        except Exception:
            pass
        self.wizard()._uninstall_thread.start()

    def update_status(self, text):
        self.statusLabel.setText(text)
        self.statusLabel.setAccessibleName(f"Stav: {text}")

    def on_announce(self, text):
        now = time.monotonic()
        # throttling 1.2s by se řešil v threadu, zde jen liveLabel
        self.liveLabel.setText(text)
        self.liveLabel.setAccessibleName(text)
        self.liveLabel.setAccessibleDescription(text)
        try:
            QAccessible.updateAccessibility(self.liveLabel, 0, QAccessible.Event.Alert)
        except Exception:
            pass
        self._last_announce = now

    def on_finished(self, success, message):
        if success:
            self.wizard().next()
        else:
            QMessageBox.critical(self, "Chyba", f"Odinstalace selhala: {message}")

class FinishPage(QWizardPage):
    def __init__(self, config):
        super().__init__()
        self.setTitle("Dokončeno")
        text = f"Program {config['appName']} byl úspěšně odstraněn. Nyní můžete okno zavřít tlačítkem Dokončit.\n\nPoznámka: Samotný soubor odinstalátoru bude možná nutné smazat ručně."
        self.setAccessibleName("Odinstalace dokončena")

        layout = QVBoxLayout()
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.label.setAccessibleName(text)
        layout.addWidget(self.label)
        self.setLayout(layout)

    def initializePage(self):
        self.label.setFocus()

class AccessibleUninstaller(QWizard):
    def __init__(self, config, install_dir):
        super().__init__()
        self.config = config
        self.install_dir = install_dir
        self._uninstall_thread = None
        self.setWindowTitle(f"Odinstalace - {config['appName']}")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)

        self.setButtonText(QWizard.WizardButton.NextButton, "Odinstalovat >")
        self.setButtonText(QWizard.WizardButton.BackButton, "< Zpět")
        self.setButtonText(QWizard.WizardButton.CancelButton, "Zrušit")
        self.setButtonText(QWizard.WizardButton.FinishButton, "Dokončit")

        self.addPage(IntroPage(config, install_dir))
        self.addPage(ProgressPage(config, install_dir))
        self.addPage(FinishPage(config))

    def reject(self):
        if self._uninstall_thread is not None and self._uninstall_thread.isRunning():
            reply = QMessageBox.question(self, "Přerušit odinstalaci", "Odinstalace probíhá. Chcete ji přerušit?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    self._uninstall_thread.requestInterruption()
                    self._uninstall_thread.wait(3000)
                except Exception:
                    pass
                super().reject()
            return
        super().reject()

def main():
    install_dir = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))

    config_path = os.path.join(install_dir, CONFIG_FILENAME)
    manifest_path = os.path.join(install_dir, MANIFEST_FILENAME)

    # main() vyžaduje manifest nebo config
    if not os.path.exists(manifest_path) and not os.path.exists(config_path):
        app = QApplication(sys.argv)
        QMessageBox.critical(None, "Chyba", "Nebyly nalezeny informace o instalaci. Odinstalaci nelze provést.")
        sys.exit(1)

    config = None
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception:
            config = None
    if config is None and os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                m = json.load(f)
            config = {"appName": m.get("appName", "Aplikace"), "appVersion": m.get("version", "")}
        except Exception:
            pass
    if config is None:
        app = QApplication(sys.argv)
        QMessageBox.critical(None, "Chyba", "Nebyly nalezeny informace o instalaci. Odinstalaci nelze provést.")
        sys.exit(1)

    app = QApplication(sys.argv)
    wizard = AccessibleUninstaller(config, install_dir)
    wizard.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
