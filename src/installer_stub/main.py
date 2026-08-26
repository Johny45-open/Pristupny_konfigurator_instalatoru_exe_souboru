import sys
import os
import shutil
import json
import subprocess
from PyQt6.QtWidgets import (QApplication, QWizard, QWizardPage, QVBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QHBoxLayout, 
                             QProgressBar, QMessageBox, QCheckBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal


def get_powershell_path():
    """Vrátí cestu k powershell.exe, řeší SysNative pro 32-bit proces na 64-bit OS."""
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
    """
    Vrátí skutečnou cestu ke známé složce pomocí PowerShell [Environment]::GetFolderPath.
    Funguje pro CZ lokalizaci (Plocha) i OneDrive přesměrování.
    folder_id: 'Desktop', 'CommonDesktopDirectory', 'Programs', 'StartMenu'
    """
    mapping = {
        'desktop': 'Desktop',
        'commondesktop': 'CommonDesktopDirectory',
        'programs': 'Programs',
        'commonprograms': 'CommonPrograms',
        'startmenu': 'StartMenu',
        'appdata_programs': 'Programs',  # alias
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
            if p and os.path.isdir(p):
                return p
            # PowerShell může vrátit cestu i když adresář neexistuje (např. čerstvý profil) – vrať i tak
            if p:
                return p
    except Exception:
        pass

    # Fallback – registry User Shell Folders pro Desktop
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
        # Poslední fallback – zkus Plocha i Desktop
        for name in ['Desktop', 'Plocha']:
            p = os.path.join(os.environ.get('USERPROFILE', ''), name)
            if os.path.isdir(p):
                return p
        return os.path.join(os.environ.get('USERPROFILE', ''), 'Desktop')

    if folder_id.lower() in ('programs', 'startmenu', 'commonprograms'):
        base = os.environ.get('APPDATA', '') if folder_id.lower() == 'programs' else os.environ.get('APPDATA', '')
        # Pro CommonPrograms je base veřejná cesta
        if folder_id.lower() == 'commonprograms':
            base = os.environ.get('PROGRAMDATA', r'C:\ProgramData')
            return os.path.join(base, 'Microsoft', 'Windows', 'Start Menu', 'Programs')
        return os.path.join(os.environ.get('APPDATA', ''), 'Microsoft', 'Windows', 'Start Menu', 'Programs')

    if folder_id.lower() == 'commondesktop':
        return os.path.join(os.environ.get('PUBLIC', r'C:\Users\Public'), 'Desktop')

    return ""


class InstallationThread(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, source_dir, dest_dir, config):
        super().__init__()
        self.source_dir = source_dir
        self.dest_dir = dest_dir
        self.config = config

    def create_shortcut(self, target_path, shortcut_path):
        """Vytvoří zástupce pomocí PowerShellu a vrátí chybu, pokud selže."""
        try:
            # Zajisti, že cílový adresář existuje
            parent = os.path.dirname(shortcut_path)
            if parent and not os.path.exists(parent):
                os.makedirs(parent, exist_ok=True)

            ps_path = get_powershell_path()
            # Escapování pro PowerShell – používáme single-quotes, uvnitř zdvojit '
            def ps_escape(s):
                return s.replace("'", "''")
            target_esc = ps_escape(target_path)
            shortcut_esc = ps_escape(shortcut_path)
            workdir = ps_escape(os.path.dirname(target_path))
            # PowerShell script s single-quotes – bezpečné pro cesty s diakritikou i mezerami
            ps_script = f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{shortcut_esc}'); $s.TargetPath = '{target_esc}'; $s.WorkingDirectory = '{workdir}'; $s.Save()"

            result = subprocess.run([ps_path, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps_script], capture_output=True, text=True, timeout=15)

            if result.returncode != 0:
                err = (result.stderr or result.stdout or "").strip()
                return f"PowerShell error: {err}" if err else f"PowerShell selhal (code {result.returncode})"
            # Ověř, že soubor opravdu vznikl
            if not os.path.exists(shortcut_path):
                return "Zástupce nebyl vytvořen (soubor neexistuje po Save())"
            return None
        except Exception as e:
            return str(e)

    def run(self):
        errors = []
        try:
            if not os.path.exists(self.dest_dir):
                os.makedirs(self.dest_dir)

            files = os.listdir(self.source_dir)
            total = len(files)

            if total == 0:
                # Uložíme konfiguraci pro odinstalátor
                config_for_uninstaller = os.path.join(self.dest_dir, "install_config.json")
                with open(config_for_uninstaller, "w", encoding="utf-8") as f:
                    json.dump(self.config, f, ensure_ascii=False, indent=4)
                self.finished_signal.emit(True, "Instalace byla úspěšně dokončena (nebyl nalezen žádný payload).")
                return

            for i, f in enumerate(files):
                src = os.path.join(self.source_dir, f)
                dst = os.path.join(self.dest_dir, f)
                if os.path.isdir(src):
                    if os.path.exists(dst):
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)

                percent = int(((i + 1) / total) * 0.8 * 100) # Kopírování je 80%
                self.progress.emit(percent)
                self.status.emit(f"Instaluji: {f}")

            # Vytvoření zástupců
            exe_name = os.path.basename(self.config.get('exePath', ''))
            target_exe = os.path.join(self.dest_dir, exe_name)
            app_name = self.config.get('appName', 'Aplikace')

            if self.config.get('createDesktopShortcut'):
                self.status.emit("Vytvářím zástupce na ploše...")
                desktop = get_known_folder('Desktop')
                if not desktop or not os.path.isdir(os.path.dirname(desktop)) and not os.path.isdir(desktop):
                    # Pokud GetFolderPath vrátil neexistující cestu, zkus fallback Plocha/Desktop
                    desktop = get_known_folder('desktop')
                shortcut_path = os.path.join(desktop, f"{app_name}.lnk")
                err = self.create_shortcut(target_exe, shortcut_path)
                if err: errors.append(f"Zástupce na ploše: {err} (cesta: {shortcut_path})")

            if self.config.get('createStartMenuShortcut'):
                self.status.emit("Vytvářím zástupce v nabídce Start...")
                start_menu = get_known_folder('Programs')
                shortcut_path = os.path.join(start_menu, f"{app_name}.lnk")
                err = self.create_shortcut(target_exe, shortcut_path)
                if err: errors.append(f"Zástupce v nabídce Start: {err} (cesta: {shortcut_path})")

            self.progress.emit(100)

            # Uložíme konfiguraci pro odinstalátor (včetně finální volby uživatele)
            config_for_uninstaller = os.path.join(self.dest_dir, "install_config.json")
            with open(config_for_uninstaller, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)

            msg = "Instalace byla úspěšně dokončena."
            if errors:
                msg += "\n\nVarování: Některé zástupce se nepodařilo vytvořit:\n" + "\n".join(errors)

            self.finished_signal.emit(True, msg)
        except Exception as e:
            self.finished_signal.emit(False, str(e))

class IntroPage(QWizardPage):
    def __init__(self, config):
        super().__init__()
        self.setTitle("Vítejte")
        text = f"Vítá vás instalace programu {config['appName']}. Pokračujte stisknutím tlačítka Další."
        self.setAccessibleName("Úvodní stránka")

        layout = QVBoxLayout()
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.label.setAccessibleName(text)
        layout.addWidget(self.label)
        self.setLayout(layout)

    def initializePage(self):
        self.label.setFocus()

class DirectoryPage(QWizardPage):
    def __init__(self, config):
        super().__init__()
        self.setTitle("Cílové umístění")
        text = f"Kam má být produkt {config['appName']} nainstalován?"
        self.setAccessibleName("Výběr složky")

        layout = QVBoxLayout()
        self.label = QLabel(text)
        self.label.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.label.setAccessibleName(text)
        layout.addWidget(self.label)

        self.pathEdit = QLineEdit()

        # Logika pro výběr Program Files na základě konfigurace
        if config.get('installDir', 0) == 0:
            pf = os.environ.get("ProgramW6432") or os.environ.get("ProgramFiles")
        else:
            pf = os.environ.get("ProgramFiles(x86)") or os.environ.get("ProgramFiles")

        # Použijeme safeName (bez diakritiky) pro název složky, aby fungovalo načítání DLL
        folder_name = config.get('safeName', config['appName'])
        default_path = os.path.join(pf, folder_name)
        self.pathEdit.setText(default_path)
        self.pathEdit.setAccessibleName("Cesta k instalaci")
        layout.addWidget(self.pathEdit)
        self.registerField("installPath", self.pathEdit)

        self.setLayout(layout)

    def initializePage(self):
        self.label.setFocus()


class ShortcutSelectionPage(QWizardPage):
    """Nová stránka – uživatel si vybere zástupce (výchozí podle konfigurátoru)."""
    def __init__(self, config):
        super().__init__()
        self.setTitle("Zástupci")
        self.setAccessibleName("Výběr zástupců")
        self.config = config

        layout = QVBoxLayout()
        info = QLabel("Vyberte, kde se mají vytvořit zástupci aplikace. Výchozí stav odpovídá nastavení z konfigurátoru.")
        info.setWordWrap(True)
        info.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        info.setAccessibleName("Vyberte zástupce. Výchozí stav odpovídá nastavení z konfigurátoru.")
        layout.addWidget(info)

        self.desktopCheck = QCheckBox("Vytvořit zástupce na ploše")
        self.desktopCheck.setAccessibleName("Vytvořit zástupce na ploše")
        self.desktopCheck.setAccessibleDescription("Zaškrtněte, pokud chcete zástupce na ploše. Výchozí stav pochází z konfigurátoru.")
        self.desktopCheck.setChecked(bool(config.get('createDesktopShortcut', True)))
        layout.addWidget(self.desktopCheck)
        self.registerField("createDesktopShortcut", self.desktopCheck)

        self.startMenuCheck = QCheckBox("Vytvořit zástupce v nabídce Start")
        self.startMenuCheck.setAccessibleName("Vytvořit zástupce v nabídce Start")
        self.startMenuCheck.setAccessibleDescription("Zaškrtněte, pokud chcete zástupce v nabídce Start. Výchozí stav pochází z konfigurátoru.")
        self.startMenuCheck.setChecked(bool(config.get('createStartMenuShortcut', True)))
        layout.addWidget(self.startMenuCheck)
        self.registerField("createStartMenuShortcut", self.startMenuCheck)

        # Nápověda pro čtečku
        hint = QLabel("Použijte Tab pro přesun mezi zaškrtávátky a Mezerník pro přepnutí.")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.setLayout(layout)

    def initializePage(self):
        # Fokus na první checkbox pro rychlou obsluhu čtečkou
        self.desktopCheck.setFocus()

class ProgressPage(QWizardPage):
    def __init__(self, config, source_dir):
        super().__init__()
        self.config = config
        self.source_dir = source_dir
        self.setTitle("Průběh instalace")
        text = "Probíhá instalace, prosím čekejte."
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
        dest = self.field("installPath")
        # Aktualizuj config podle volby uživatele na ShortcutSelectionPage
        try:
            self.config['createDesktopShortcut'] = bool(self.field("createDesktopShortcut"))
            self.config['createStartMenuShortcut'] = bool(self.field("createStartMenuShortcut"))
        except Exception:
            pass
        self.thread = InstallationThread(self.source_dir, dest, self.config)
        self.thread.progress.connect(self.progressBar.setValue)
        self.thread.status.connect(self.update_status)
        self.thread.finished_signal.connect(self.on_finished)
        self.thread.start()

    def update_status(self, text):
        self.statusLabel.setText(text)
        self.statusLabel.setAccessibleName(f"Stav: {text}")

    def on_finished(self, success, message):
        if success:
            # Ulož zprávu (včetně varování) pro FinishPage, aby ji zobrazila
            self.wizard().installResultMessage = message
            # Detekce varování – pokud zpráva obsahuje "Varování", označ
            if "Varování" in message:
                self.wizard().shortcutErrors = message
            self.wizard().next()
        else:
            QMessageBox.critical(self, "Chyba", f"Selhalo: {message}")

class FinishPage(QWizardPage):
    def __init__(self, config):
        super().__init__()
        self.setTitle("Instalace dokončena")
        text = f"Program {config['appName']} byl úspěšně nainstalován. Nyní můžete okno zavřít tlačítkem Dokončit."
        self.setAccessibleName("Dokončeno")

        layout = QVBoxLayout()
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.label.setAccessibleName(text)
        layout.addWidget(self.label)
        self.warningLabel = QLabel("")
        self.warningLabel.setWordWrap(True)
        self.warningLabel.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.warningLabel.setStyleSheet("color: #a00;")
        self.warningLabel.hide()
        layout.addWidget(self.warningLabel)
        self.setLayout(layout)

    def initializePage(self):
        # Zobraz varování pokud instalace hlásila chybu zástupců
        msg = getattr(self.wizard(), 'installResultMessage', '')
        if msg and "Varování" in msg:
            # Zobraz jen část s varováním
            warning_text = msg[msg.find("Varování"):]
            self.warningLabel.setText(warning_text)
            self.warningLabel.setAccessibleName(warning_text)
            self.warningLabel.show()
            # Pro čtečku – přesuň fokus na varování
            self.warningLabel.setFocus()
        else:
            self.warningLabel.hide()
            self.label.setFocus()

class AccessibleWizard(QWizard):
    def __init__(self, config, source_dir):
        super().__init__()
        self.config = config
        self.setWindowTitle(f"Instalace - {config['appName']}")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)

        self.setButtonText(QWizard.WizardButton.NextButton, "Další >")
        self.setButtonText(QWizard.WizardButton.BackButton, "< Zpět")
        self.setButtonText(QWizard.WizardButton.CancelButton, "Zrušit")
        self.setButtonText(QWizard.WizardButton.FinishButton, "Dokončit")

        self.addPage(IntroPage(config))
        self.addPage(DirectoryPage(config))
        self.addPage(ShortcutSelectionPage(config))
        self.addPage(ProgressPage(config, source_dir))
        self.addPage(FinishPage(config))

    def reject(self):
        msg = f"Chcete skutečně přerušit instalaci programu {self.config['appName']}?\n\n" \
              f"Stiskněte Ano pro ukončení nebo Ne pro pokračování."
        reply = QMessageBox.question(self, "Ukončení", msg, 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            super().reject()

def main():
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_path, "config.json")
    if not os.path.exists(config_path):
        config = {"appName": "Aplikace", "appVersion": "1.0", "appAuthor": "Autor", "installDir": 0}
    else:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

    app = QApplication(sys.argv)
    source_dir = os.path.join(base_path, "payload")
    if not os.path.exists(source_dir):
        os.makedirs(source_dir)

    wizard = AccessibleWizard(config, source_dir)
    wizard.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
