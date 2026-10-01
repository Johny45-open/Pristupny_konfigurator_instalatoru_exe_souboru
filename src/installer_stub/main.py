import sys
import os
import shutil
import json
import subprocess
import time
from enum import Enum
from datetime import datetime, timezone
from PyQt6.QtWidgets import (QApplication, QWizard, QWizardPage, QVBoxLayout,
                             QLabel, QLineEdit, QPushButton, QHBoxLayout,
                             QProgressBar, QMessageBox, QCheckBox, QTextBrowser)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
try:
    from PyQt6.QtGui import QAccessible
except Exception:
    QAccessible = None  # type: ignore

MANIFEST_FILENAME = "install_manifest.json"
CONFIG_FILENAME = "install_config.json"

PROTECTED_DIRS = [
    os.path.abspath(os.environ.get("SystemRoot", r"C:\Windows")),
    os.path.abspath(os.environ.get("SystemRoot", r"C:\Windows") + r"\System32"),
    os.path.abspath("C:\\"),
    os.path.abspath("C:/"),
]

class InstallStatus(Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"

def is_protected_dir(path: str) -> bool:
    """Vrátí True pokud je cesta chráněná (kořen, Windows)."""
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

def write_manifest(manifest_data: dict, dest_dir: str) -> str:
    """Zapíše manifest do dest_dir/MANIFEST_FILENAME."""
    os.makedirs(dest_dir, exist_ok=True)
    path = os.path.join(dest_dir, MANIFEST_FILENAME)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, ensure_ascii=False, indent=2)
    return path

def write_config(config: dict, dest_dir: str) -> str:
    """Zapíše config do dest_dir/CONFIG_FILENAME."""
    os.makedirs(dest_dir, exist_ok=True)
    path = os.path.join(dest_dir, CONFIG_FILENAME)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)
    return path

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
        'appdata_programs': 'Programs',
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

    if folder_id.lower() in ('programs', 'startmenu', 'commonprograms'):
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
    announce = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, source_dir, dest_dir, config):
        super().__init__()
        self.source_dir = source_dir
        self.dest_dir = dest_dir
        self.config = config
        self._copied_files = []
        self._copied_dirs = []

    def create_shortcut(self, target_path, shortcut_path):
        """Vytvoří zástupce pomocí PowerShellu a vrátí chybu, pokud selže."""
        try:
            parent = os.path.dirname(shortcut_path)
            if parent and not os.path.exists(parent):
                os.makedirs(parent, exist_ok=True)

            ps_path = get_powershell_path()
            def ps_escape(s):
                return s.replace("'", "''")
            target_esc = ps_escape(target_path)
            shortcut_esc = ps_escape(shortcut_path)
            workdir = ps_escape(os.path.dirname(target_path))
            ps_script = f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{shortcut_esc}'); $s.TargetPath = '{target_esc}'; $s.WorkingDirectory = '{workdir}'; $s.Save()"

            result = subprocess.run([ps_path, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps_script], capture_output=True, text=True, timeout=15)

            if result.returncode != 0:
                err = (result.stderr or result.stdout or "").strip()
                return f"PowerShell error: {err}" if err else f"PowerShell selhal (code {result.returncode})"
            if not os.path.exists(shortcut_path):
                return "Zástupce nebyl vytvořen (soubor neexistuje po Save())"
            return None
        except Exception as e:
            return str(e)

    def _rollback(self):
        """Rollback částečné instalace – smaže zkopírované soubory/adresáře."""
        try:
            for f in reversed(self._copied_files):
                try:
                    fp = os.path.join(self.dest_dir, f)
                    if os.path.isfile(fp) and not is_protected_dir(os.path.dirname(fp)):
                        os.remove(fp)
                except Exception:
                    pass
            for d in self._copied_dirs:
                try:
                    dp = os.path.join(self.dest_dir, d)
                    if os.path.isdir(dp) and not is_protected_dir(dp) and not os.listdir(dp):
                        os.rmdir(dp)
                except Exception:
                    pass
        except Exception:
            pass

    def run(self):
        errors = []
        status_result = InstallStatus.SUCCESS
        try:
            # Kontrola chráněného adresáře
            if is_protected_dir(self.dest_dir):
                self.finished_signal.emit(False, f"Cílová cesta je chráněná a nelze do ní instalovat: {self.dest_dir}")
                return

            if self.isInterruptionRequested():
                self.finished_signal.emit(False, "Instalace zrušena uživatelem.")
                return

            if not os.path.exists(self.dest_dir):
                os.makedirs(self.dest_dir, exist_ok=True)

            # Seznam souborů k instalaci (payload)
            if not os.path.isdir(self.source_dir):
                files = []
            else:
                files = os.listdir(self.source_dir)
            total = len(files)

            # Pro manifest evidenci
            manifest_files = []
            manifest_dirs = []
            shortcuts_created = []

            if total == 0:
                # Uložíme konfiguraci pro odinstalátor i při prázdném payloadu
                write_config(self.config, self.dest_dir)
                manifest_data = {
                    "appName": self.config.get("appName", ""),
                    "safeName": self.config.get("safeName", ""),
                    "version": self.config.get("appVersion", ""),
                    "installDir": os.path.abspath(self.dest_dir),
                    "installedAt": datetime.now(timezone.utc).isoformat(),
                    "files": [],
                    "dirs": [],
                    "shortcuts": [],
                    "status": InstallStatus.SUCCESS.value
                }
                write_manifest(manifest_data, self.dest_dir)
                self.progress.emit(100)
                self.announce.emit("Instalace dokončena, žádný payload nebyl nalezen.")
                self.finished_signal.emit(True, "Instalace byla úspěšně dokončena (nebyl nalezen žádný payload).")
                return

            # Kopírování 0-80 % s milníky 25/50/75
            announced_milestones = set()
            for i, f in enumerate(files):
                if self.isInterruptionRequested():
                    self.status.emit("Ruší se instalace...")
                    self.announce.emit("Instalace zrušena uživatelem, probíhá úklid.")
                    self._rollback()
                    self.finished_signal.emit(False, "Instalace zrušena uživatelem.")
                    return

                src = os.path.join(self.source_dir, f)
                dst = os.path.join(self.dest_dir, f)
                if os.path.isdir(src):
                    if os.path.exists(dst):
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                    manifest_dirs.append(f)
                    self._copied_dirs.append(f)
                    # Rekurzivně eviduj vnořené soubory pro manifest
                    for root, dirs, filenames in os.walk(dst):
                        rel_root = os.path.relpath(root, self.dest_dir)
                        for fn in filenames:
                            rel = os.path.join(rel_root, fn) if rel_root != "." else fn
                            if rel not in manifest_files:
                                manifest_files.append(rel)
                else:
                    shutil.copy2(src, dst)
                    manifest_files.append(f)
                    self._copied_files.append(f)

                percent = int(((i + 1) / total) * 80)
                self.progress.emit(percent)
                self.status.emit(f"Instaluji: {f}")

                # announce milníky 25/50/75
                for milestone in (25, 50, 75):
                    if percent >= milestone and milestone not in announced_milestones:
                        announced_milestones.add(milestone)
                        self.announce.emit(f"Instalace {milestone} procent dokončeno")

                # Kontrola protected během kopie (průběžně)
                if is_protected_dir(self.dest_dir):
                    self._rollback()
                    self.finished_signal.emit(False, "Instalace přerušena – cílový adresář je chráněný.")
                    return

            # Vytváření zástupců 80-95 %
            exe_name = self.config.get("exeName") or os.path.basename(self.config.get('exePath', ''))
            if not exe_name:
                exe_name = self.config.get("safeName", "app") + ".exe"
            target_exe = os.path.join(self.dest_dir, exe_name)
            app_name = self.config.get('appName', 'Aplikace')
            self.progress.emit(80)

            if self.config.get('createDesktopShortcut'):
                if self.isInterruptionRequested():
                    self._rollback()
                    self.finished_signal.emit(False, "Instalace zrušena uživatelem.")
                    return
                self.status.emit("Vytvářím zástupce na ploše...")
                self.announce.emit("Vytvářím zástupce na ploše")
                desktop = get_known_folder('Desktop')
                if not desktop or not os.path.isdir(os.path.dirname(desktop)) and not os.path.isdir(desktop):
                    desktop = get_known_folder('desktop')
                shortcut_path = os.path.join(desktop, f"{app_name}.lnk")
                err = self.create_shortcut(target_exe, shortcut_path)
                self.progress.emit(88)
                if err:
                    errors.append(f"Zástupce na ploše: {err} (cesta: {shortcut_path})")
                    status_result = InstallStatus.PARTIAL
                else:
                    shortcuts_created.append({"path": shortcut_path, "scope": "desktop"})

            if self.config.get('createStartMenuShortcut'):
                if self.isInterruptionRequested():
                    self._rollback()
                    self.finished_signal.emit(False, "Instalace zrušena uživatelem.")
                    return
                self.status.emit("Vytvářím zástupce v nabídce Start...")
                self.announce.emit("Vytvářím zástupce v nabídce Start")
                start_menu = get_known_folder('Programs')
                shortcut_path = os.path.join(start_menu, f"{app_name}.lnk")
                err = self.create_shortcut(target_exe, shortcut_path)
                self.progress.emit(95)
                if err:
                    errors.append(f"Zástupce v nabídce Start: {err} (cesta: {shortcut_path})")
                    if status_result != InstallStatus.PARTIAL:
                        status_result = InstallStatus.PARTIAL
                else:
                    shortcuts_created.append({"path": shortcut_path, "scope": "startmenu"})

            if not self.config.get('createDesktopShortcut') and not self.config.get('createStartMenuShortcut'):
                self.progress.emit(95)

            # Zápis manifestu a configu
            manifest_status = status_result.value if not errors else InstallStatus.PARTIAL.value if status_result == InstallStatus.PARTIAL else InstallStatus.SUCCESS.value
            if errors and status_result == InstallStatus.SUCCESS:
                manifest_status = InstallStatus.PARTIAL.value

            manifest_data = {
                "appName": self.config.get("appName", ""),
                "safeName": self.config.get("safeName", ""),
                "version": self.config.get("appVersion", ""),
                "installDir": os.path.abspath(self.dest_dir),
                "installedAt": datetime.now(timezone.utc).isoformat(),
                "files": sorted(manifest_files),
                "dirs": sorted(manifest_dirs, key=lambda p: p.count(os.sep), reverse=True),
                "shortcuts": shortcuts_created,
                "status": manifest_status
            }
            write_manifest(manifest_data, self.dest_dir)
            write_config(self.config, self.dest_dir)

            self.progress.emit(100)
            self.announce.emit("Instalace dokončena na 100 procent")

            msg = "Instalace byla úspěšně dokončena."
            if errors:
                msg += "\n\nVarování: Některé zástupce se nepodařilo vytvořit:\n" + "\n".join(errors)
                self.finished_signal.emit(True, msg)
            else:
                self.finished_signal.emit(True, msg)

        except Exception as e:
            try:
                # Zápis failed manifestu pokud možno
                manifest_data = {
                    "appName": self.config.get("appName", ""),
                    "safeName": self.config.get("safeName", ""),
                    "version": self.config.get("appVersion", ""),
                    "installDir": os.path.abspath(self.dest_dir),
                    "installedAt": datetime.now(timezone.utc).isoformat(),
                    "files": [],
                    "dirs": [],
                    "shortcuts": [],
                    "status": InstallStatus.FAILED.value
                }
                write_manifest(manifest_data, self.dest_dir)
                write_config(self.config, self.dest_dir)
            except Exception:
                pass
            self.announce.emit("Instalace selhala")
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
        if config.get('installDir', 0) == 0:
            pf = os.environ.get("ProgramW6432") or os.environ.get("ProgramFiles")
        else:
            pf = os.environ.get("ProgramFiles(x86)") or os.environ.get("ProgramFiles")

        folder_name = config.get('safeName', config['appName'])
        default_path = os.path.join(pf, folder_name)
        self.pathEdit.setText(default_path)
        self.pathEdit.setAccessibleName("Cesta k instalaci")
        layout.addWidget(self.pathEdit)
        self.registerField("installPath", self.pathEdit)
        self.pathEdit.textChanged.connect(self._on_path_changed)

        self.errorLabel = QLabel("")
        self.errorLabel.setWordWrap(True)
        self.errorLabel.setStyleSheet("color: #a00;")
        self.errorLabel.setAccessibleName("")
        self.errorLabel.hide()
        layout.addWidget(self.errorLabel)

        self.setLayout(layout)

    def isComplete(self):
        return bool(self.pathEdit.text().strip())

    def _on_path_changed(self, _text):
        self.completeChanged.emit()

    def validatePage(self):
        path = self.pathEdit.text().strip()
        if not path:
            self.errorLabel.setText("Cesta nesmí být prázdná.")
            self.errorLabel.setAccessibleName("Chyba: Cesta nesmí být prázdná.")
            self.errorLabel.show()
            return False
        if is_protected_dir(path):
            self.errorLabel.setText("Zvolená cesta je chráněná (systémový adresář nebo kořen disku). Zvolte jinou složku.")
            self.errorLabel.setAccessibleName("Chyba: Zvolená cesta je chráněná.")
            self.errorLabel.show()
            return False
        if not os.path.isabs(path):
            self.errorLabel.setText("Cesta musí být absolutní (např. C:\\Program Files\\Aplikace).")
            self.errorLabel.setAccessibleName("Chyba: Cesta musí být absolutní.")
            self.errorLabel.show()
            return False
        # Relativní cesta kontrola – pokud obsahuje ".." nebo je relativní
        if ".." in path.split(os.sep):
            self.errorLabel.setText("Cesta nesmí obsahovat '..'.")
            self.errorLabel.setAccessibleName("Chyba: Cesta nesmí obsahovat '..'.")
            self.errorLabel.show()
            return False
        self.errorLabel.hide()
        return True

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

        hint = QLabel("Použijte Tab pro přesun mezi zaškrtávátky a Mezerník pro přepnutí.")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.setLayout(layout)

    def initializePage(self):
        self.desktopCheck.setFocus()

class SummaryPage(QWizardPage):
    """Přístupná souhrnná stránka před instalací (QTextBrowser — šipky + virtuální kurzor)."""
    def __init__(self, config):
        super().__init__()
        self.setTitle("Souhrn")
        self.setAccessibleName("Souhrn instalace")
        self.setAccessibleDescription("Přehled instalace před spuštěním. Čtěte šipkami v textovém poli.")
        self.config = config
        layout = QVBoxLayout()
        intro = QLabel("Zkontrolujte nastavení před zahájením instalace. "
                       "Text přečtete šipkami, Tab vás posune na tlačítka.")
        intro.setWordWrap(True)
        intro.setAccessibleName(intro.text())
        layout.addWidget(intro)

        self.summaryView = QTextBrowser()
        self.summaryView.setReadOnly(True)
        self.summaryView.setOpenExternalLinks(False)
        self.summaryView.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.summaryView.setAccessibleName("Souhrn instalace")
        self.summaryView.setAccessibleDescription(
            "Textové shrnutí instalace. Pohyb šipkami nahoru a dolů, výběr klávesnicí.")
        self.summaryView.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard)
        layout.addWidget(self.summaryView)

        copy_btn = QPushButton("Kopírovat souhrn do schránky")
        copy_btn.setAccessibleName("Kopírovat souhrn do schránky")
        copy_btn.setAccessibleDescription("Zkopíruje text souhrnu do schránky")
        copy_btn.clicked.connect(self.copy_summary)
        layout.addWidget(copy_btn)

        self.setLayout(layout)

    def summary_text(self) -> str:
        app_name = self.config.get("appName", "")
        version = self.config.get("appVersion", "")
        author = self.config.get("appAuthor", "") or "—"
        try:
            install_path = self.field("installPath") or ""
        except Exception:
            install_path = ""
        try:
            desktop = "Ano" if self.field("createDesktopShortcut") else "Ne"
        except Exception:
            desktop = "—"
        try:
            startmenu = "Ano" if self.field("createStartMenuShortcut") else "Ne"
        except Exception:
            startmenu = "—"
        return (
            f"Aplikace: {app_name}\n"
            f"Verze: {version}\n"
            f"Autor: {author}\n"
            f"Cílová složka: {install_path}\n"
            f"Zástupce na ploše: {desktop}\n"
            f"Zástupce v nabídce Start: {startmenu}"
        )

    def copy_summary(self):
        try:
            QApplication.clipboard().setText(self.summaryView.toPlainText())
            self.summaryView.setAccessibleDescription("Souhrn zkopírován do schránky.")
        except Exception:
            pass

    def initializePage(self):
        text = self.summary_text()
        self.summaryView.setPlainText(text)
        self.summaryView.setAccessibleName(f"Souhrn instalace. {text}")
        try:
            self.summaryView.moveCursor(self.summaryView.textCursor().Start)
        except Exception:
            pass
        self.summaryView.setFocus()

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

        self.liveLabel = QLabel("")
        self.liveLabel.setAccessibleName("")
        # Live region pro čtečku – throttling 1.2s
        self.liveLabel.setAccessibleDescription("Průběh instalace")
        layout.addWidget(self.liveLabel)

        self.progressBar = QProgressBar()
        self.progressBar.setAccessibleName("Průběh v procentech")
        layout.addWidget(self.progressBar)
        self.setLayout(layout)
        self._last_announce = 0
        self._last_status_text = ""

    def initializePage(self):
        self.label.setFocus()
        self.wizard().button(QWizard.WizardButton.BackButton).setEnabled(False)
        dest = self.field("installPath")
        try:
            self.config['createDesktopShortcut'] = bool(self.field("createDesktopShortcut"))
            self.config['createStartMenuShortcut'] = bool(self.field("createStartMenuShortcut"))
        except Exception:
            pass
        self.wizard()._install_thread = InstallationThread(self.source_dir, dest, self.config)
        self.wizard()._install_thread.progress.connect(self.progressBar.setValue)
        self.wizard()._install_thread.status.connect(self.on_status)
        self.wizard()._install_thread.announce.connect(self.on_announce)
        self.wizard()._install_thread.finished_signal.connect(self.on_finished)
        self.wizard()._install_thread.start()

    def on_status(self, text):
        self.statusLabel.setText(text)
        self.statusLabel.setAccessibleName(f"Stav: {text}")

    def on_announce(self, text):
        # throttling 1.2s
        now = time.monotonic()
        if now - self._last_announce < 1.2 and text == self._last_status_text:
            return
        if now - self._last_announce < 1.2:
            # stále aktualizuj ale throttluj
            pass
        # Update liveLabel a vyvolej QAccessible.Alert
        self.liveLabel.setText(text)
        self.liveLabel.setAccessibleName(text)
        self.liveLabel.setAccessibleDescription(text)
        try:
            QAccessible.updateAccessibility(self.liveLabel, 0, QAccessible.Event.Alert)
        except Exception:
            pass
        try:
            QAccessible.updateAccessibility(self.liveLabel, 0, QAccessible.Event.ValueChanged)
        except Exception:
            pass
        self._last_announce = now
        self._last_status_text = text

    def on_finished(self, success, message):
        if success:
            self.wizard().installResultMessage = message
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
        msg = getattr(self.wizard(), 'installResultMessage', '')
        if msg and "Varování" in msg:
            warning_text = msg[msg.find("Varování"):]
            self.warningLabel.setText(warning_text)
            self.warningLabel.setAccessibleName(warning_text)
            self.warningLabel.show()
            self.warningLabel.setFocus()
        else:
            self.warningLabel.hide()
            self.label.setFocus()

class AccessibleWizard(QWizard):
    def __init__(self, config, source_dir):
        super().__init__()
        self.config = config
        self._install_thread = None
        self.setWindowTitle(f"Instalace - {config['appName']}")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)

        self.setButtonText(QWizard.WizardButton.NextButton, "Další >")
        self.setButtonText(QWizard.WizardButton.BackButton, "< Zpět")
        self.setButtonText(QWizard.WizardButton.CancelButton, "Zrušit")
        self.setButtonText(QWizard.WizardButton.FinishButton, "Dokončit")

        self.addPage(IntroPage(config))
        self.addPage(DirectoryPage(config))
        self.addPage(ShortcutSelectionPage(config))
        self.addPage(SummaryPage(config))
        self.addPage(ProgressPage(config, source_dir))
        self.addPage(FinishPage(config))

    def reject(self):
        if self.currentId() == 4 and self._install_thread is not None and self._install_thread.isRunning():
            msg = f"Instalace probíhá. Chcete ji přerušit?\n\nStiskněte Ano pro přerušení nebo Ne pro pokračování."
            reply = QMessageBox.question(self, "Přerušit instalaci", msg,
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    self._install_thread.requestInterruption()
                    self._install_thread.wait(3000)
                except Exception:
                    pass
                super().reject()
            return
        msg = f"Chcete skutečně přerušit instalaci programu {self.config['appName']}?\n\nStiskněte Ano pro ukončení nebo Ne pro pokračování."
        reply = QMessageBox.question(self, "Ukončení", msg,
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if self._install_thread is not None and self._install_thread.isRunning():
                try:
                    self._install_thread.requestInterruption()
                    self._install_thread.wait(2000)
                except Exception:
                    pass
            super().reject()

def main():
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_path, "config.json")
    if not os.path.exists(config_path):
        config = {"appName": "Aplikace", "appVersion": "1.0", "appAuthor": "Autor", "installDir": 0, "exePath": ""}
    else:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

    # fallback exeName z exePath
    if not config.get("exeName"):
        exe_path = config.get("exePath", "")
        if exe_path:
            config["exeName"] = os.path.basename(exe_path)
        else:
            config["exeName"] = (config.get("safeName") or config.get("appName") or "app") + ".exe"

    app = QApplication(sys.argv)
    source_dir = os.path.join(base_path, "payload")
    if not os.path.exists(source_dir):
        os.makedirs(source_dir)

    wizard = AccessibleWizard(config, source_dir)
    wizard.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
