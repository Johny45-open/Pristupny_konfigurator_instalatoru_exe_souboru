import sys
import os
import shutil
import json
import subprocess
from PyQt6.QtWidgets import (QApplication, QWizard, QWizardPage, QVBoxLayout, 
                             QLabel, QProgressBar, QMessageBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal


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
    # Plocha – primárně GetFolderPath, ale přidej i alternativní název pro jistotu
    desktop = get_known_folder('Desktop')
    if desktop:
        candidates.append(os.path.join(desktop, f"{app_name}.lnk"))
        # Přidej i druhou lokalizaci (Plocha/Desktop) pokud se liší
        for alt in ['Desktop', 'Plocha']:
            alt_path = os.path.join(os.environ.get('USERPROFILE', ''), alt, f"{app_name}.lnk")
            if alt_path not in candidates:
                candidates.append(alt_path)
    # Společná plocha – kdyby byl zástupce vytvořen jako commondesktop (starší verze)
    common_desktop = get_known_folder('CommonDesktopDirectory')
    if common_desktop:
        candidates.append(os.path.join(common_desktop, f"{app_name}.lnk"))

    # Start menu – uživatelské
    programs = get_known_folder('Programs')
    if programs:
        candidates.append(os.path.join(programs, f"{app_name}.lnk"))
    # Společné Start menu (kdyby instalátor běžel jako admin a použil common)
    common_programs = get_known_folder('CommonPrograms')
    if common_programs:
        candidates.append(os.path.join(common_programs, f"{app_name}.lnk"))

    # Odstraň duplicity
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
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, install_dir, config):
        super().__init__()
        self.install_dir = install_dir
        self.config = config

    def run(self):
        try:
            # Odstranění zástupců – automaticky, podle toho co existuje (řeší CZ Plocha)
            app_name = self.config.get('appName', 'Aplikace')
            for shortcut in collect_shortcut_candidates(app_name):
                if os.path.exists(shortcut):
                    try:
                        if 'Desktop' in shortcut or 'Plocha' in shortcut:
                            self.status.emit("Odstraňuji zástupce na ploše...")
                        else:
                            self.status.emit("Odstraňuji zástupce v nabídce Start...")
                        os.remove(shortcut)
                    except Exception:
                        # Ignoruj chybu mazání jednotlivého zástupce – pokračuj
                        pass

            if os.path.exists(self.install_dir):
                items = os.listdir(self.install_dir)
                total = len(items)

                for i, item in enumerate(items):
                    path = os.path.join(self.install_dir, item)
                    # Nepokoušíme se smazat sami sebe (uninstall.exe), to nejde dokud běžíme
                    if "uninstall" in item.lower():
                        continue

                    if os.path.isdir(path):
                        shutil.rmtree(path)
                    else:
                        os.remove(path)

                    percent = int(((i + 1) / total) * 100)
                    self.progress.emit(percent)
                    self.status.emit(f"Odstraňuji: {item}")

            self.finished_signal.emit(True, "Program byl úspěšně odinstalován.")
        except Exception as e:
            self.finished_signal.emit(False, str(e))

class IntroPage(QWizardPage):
    def __init__(self, config):
        super().__init__()
        self.setTitle("Odinstalace")
        text = f"Chcete skutečně odinstalovat program {config['appName']}?\n\nStiskněte tlačítko Další pro zahájení odinstalace."
        self.setAccessibleName("Úvodní stránka odinstalace")

        layout = QVBoxLayout()
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.label.setAccessibleName(text)
        layout.addWidget(self.label)
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

        self.progressBar = QProgressBar()
        self.progressBar.setAccessibleName("Průběh v procentech")
        layout.addWidget(self.progressBar)
        self.setLayout(layout)

    def initializePage(self):
        self.label.setFocus()
        self.wizard().button(QWizard.WizardButton.BackButton).setEnabled(False)
        self.thread = UninstallationThread(self.install_dir, self.config)
        self.thread.progress.connect(self.progressBar.setValue)
        self.thread.status.connect(self.update_status)
        self.thread.finished_signal.connect(self.on_finished)
        self.thread.start()

    def update_status(self, text):
        self.statusLabel.setText(text)
        self.statusLabel.setAccessibleName(f"Stav: {text}")

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
        self.setWindowTitle(f"Odinstalace - {config['appName']}")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)

        self.setButtonText(QWizard.WizardButton.NextButton, "Odinstalovat >")
        self.setButtonText(QWizard.WizardButton.BackButton, "< Zpět")
        self.setButtonText(QWizard.WizardButton.CancelButton, "Zrušit")
        self.setButtonText(QWizard.WizardButton.FinishButton, "Dokončit")

        self.addPage(IntroPage(config))
        self.addPage(ProgressPage(config, install_dir))
        self.addPage(FinishPage(config))

def main():
    # Odinstalátor běží přímo v nainstalované složce
    install_dir = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))

    # Načtení konfigurace, kterou tam nechal instalátor
    config_path = os.path.join(install_dir, "install_config.json")
    if not os.path.exists(config_path):
        # Pokud chybí log, nemůžeme bezpečně odinstalovat
        app = QApplication(sys.argv)
        QMessageBox.critical(None, "Chyba", "Nebyly nalezeny informace o instalaci. Odinstalaci nelze provést.")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    app = QApplication(sys.argv)
    wizard = AccessibleUninstaller(config, install_dir)
    wizard.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
