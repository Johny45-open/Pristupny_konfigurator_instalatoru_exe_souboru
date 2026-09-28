"""Offline aktualizační program (Update.exe).

Bundluje novou verzi aplikace (payload/ + config.json) a na cílovém PC:
1. najde existující instalaci (install_manifest.json),
2. porovná verze (starý manifest vs. nový config),
3. překopíruje nové soubory, smaže jen soubory zmizelé dle diffu manifestu,
4. přepíše manifest + config, obnoví zástupce.

Přístupnost: QWizard + QTextBrowser souhrn (čtení šipkami/virtuálním kurzorem),
live region s throttlingem, všechna pole s AccessibleName/Description.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from enum import Enum

from PyQt6.QtCore import Qt, QThread, pyqtSignal
try:
    from PyQt6.QtGui import QAccessible
except Exception:
    QAccessible = None  # type: ignore
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)

MANIFEST_FILENAME = "install_manifest.json"
CONFIG_FILENAME = "install_config.json"

PROTECTED_DIRS = [
    os.path.abspath(os.environ.get("SystemRoot", r"C:\Windows")),
    os.path.abspath(os.environ.get("SystemRoot", r"C:\Windows") + r"\System32"),
    os.path.abspath("C:\\"),
    os.path.abspath("C:/"),
]


class UpdateStatus(Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


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


def _parse_version_tuple(version: str) -> tuple:
    s = str(version or "").strip()
    m = re.match(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?", s)
    if not m:
        return (0, 0, 0)
    try:
        return (int(m.group(1) or 0), int(m.group(2) or 0), int(m.group(3) or 0))
    except Exception:
        return (0, 0, 0)


def compare_versions(old: str, new: str) -> int:
    """-1 nová < stará, 0 shodné, 1 nová > stará."""
    o = _parse_version_tuple(old)
    n = _parse_version_tuple(new)
    if n < o:
        return -1
    if n > o:
        return 1
    return 0


def collect_payload_files(payload_dir: str) -> tuple[list, list]:
    files: list = []
    dirs: list = []
    if not os.path.isdir(payload_dir):
        return files, dirs
    for root, dirnames, filenames in os.walk(payload_dir):
        rel_root = os.path.relpath(root, payload_dir)
        if rel_root == ".":
            rel_root = ""
        for dn in dirnames:
            rel = os.path.join(rel_root, dn) if rel_root else dn
            dirs.append(rel)
        for fn in filenames:
            rel = os.path.join(rel_root, fn) if rel_root else fn
            if rel in (MANIFEST_FILENAME, CONFIG_FILENAME):
                continue
            files.append(rel)
    dirs.sort(key=lambda p: p.count(os.sep), reverse=True)
    files.sort()
    return files, dirs


def load_manifest(install_dir: str) -> dict | None:
    path = os.path.join(install_dir, MANIFEST_FILENAME)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def write_manifest(manifest_data: dict, dest_dir: str) -> str:
    os.makedirs(dest_dir, exist_ok=True)
    path = os.path.join(dest_dir, MANIFEST_FILENAME)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, ensure_ascii=False, indent=2)
    return path


def write_config(config: dict, dest_dir: str) -> str:
    os.makedirs(dest_dir, exist_ok=True)
    path = os.path.join(dest_dir, CONFIG_FILENAME)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)
    return path


def get_powershell_path():
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    candidates = [
        os.path.join(system_root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe"),
        os.path.join(system_root, "Sysnative", "WindowsPowerShell", "v1.0", "powershell.exe"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return candidates[0]


def get_known_folder(folder_id):
    mapping = {
        "desktop": "Desktop",
        "commondesktop": "CommonDesktopDirectory",
        "programs": "Programs",
        "commonprograms": "CommonPrograms",
        "startmenu": "StartMenu",
    }
    net_name = mapping.get(folder_id.lower(), folder_id)
    try:
        ps_path = get_powershell_path()
        ps_cmd = f"[Environment]::GetFolderPath('{net_name}')"
        result = subprocess.run(
            [ps_path, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-Command", ps_cmd],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            p = result.stdout.strip()
            if p:
                return p
    except Exception:
        pass
    if folder_id.lower() == "desktop":
        return os.path.join(os.environ.get("USERPROFILE", ""), "Desktop")
    if folder_id.lower() == "commonprograms":
        base = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
        return os.path.join(base, "Microsoft", "Windows", "Start Menu", "Programs")
    if folder_id.lower() in ("programs", "startmenu"):
        return os.path.join(
            os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs")
    if folder_id.lower() == "commondesktop":
        return os.path.join(os.environ.get("PUBLIC", r"C:\Users\Public"), "Desktop")
    return ""


class UpdateThread(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    announce = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, source_dir, dest_dir, new_config, old_manifest):
        super().__init__()
        self.source_dir = source_dir
        self.dest_dir = os.path.abspath(dest_dir)
        self.new_config = dict(new_config)
        self.old_manifest = dict(old_manifest or {})

    def create_shortcut(self, target_path, shortcut_path):
        try:
            parent = os.path.dirname(shortcut_path)
            if parent and not os.path.exists(parent):
                os.makedirs(parent, exist_ok=True)

            def ps_escape(s):
                return s.replace("'", "''")

            ps_path = get_powershell_path()
            ps_script = (
                f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{ps_escape(shortcut_path)}'); "
                f"$s.TargetPath = '{ps_escape(target_path)}'; "
                f"$s.WorkingDirectory = '{ps_escape(os.path.dirname(target_path))}'; $s.Save()"
            )
            result = subprocess.run(
                [ps_path, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                 "-Command", ps_script],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode != 0:
                err = (result.stderr or result.stdout or "").strip()
                return f"PowerShell error: {err}" if err else f"PowerShell selhal (code {result.returncode})"
            if not os.path.exists(shortcut_path):
                return "Zástupce nebyl vytvořen (soubor neexistuje po Save())"
            return None
        except Exception as e:
            return str(e)

    def run(self):
        errors: list[str] = []
        try:
            if is_protected_dir(self.dest_dir):
                self.finished_signal.emit(False, f"Cílová cesta je chráněná: {self.dest_dir}")
                return
            if not os.path.isdir(self.dest_dir):
                self.finished_signal.emit(
                    False, "Cílová složka neexistuje. Nejdřív aplikaci nainstalujte instalátorem.")
                return
            if self.isInterruptionRequested():
                self.finished_signal.emit(False, "Aktualizace zrušena uživatelem.")
                return

            new_files, new_dirs = collect_payload_files(self.source_dir)
            old_files = list(self.old_manifest.get("files", []))
            old_files_n = {os.path.normpath(f).lower() for f in old_files}
            new_files_n = {os.path.normpath(f).lower() for f in new_files}
            removed = [f for f in old_files if os.path.normpath(f).lower() not in new_files_n]

            total = max(len(new_files), 1)
            announced = set()
            for i, rel in enumerate(new_files):
                if self.isInterruptionRequested():
                    self.announce.emit("Aktualizace zrušena uživatelem.")
                    self.finished_signal.emit(False, "Aktualizace zrušena uživatelem.")
                    return
                src = os.path.join(self.source_dir, rel)
                dst = os.path.join(self.dest_dir, rel)
                abs_dst = os.path.abspath(dst)
                try:
                    common = os.path.commonpath([self.dest_dir.lower(), abs_dst.lower()])
                except ValueError:
                    common = ""
                if common != self.dest_dir.lower():
                    continue
                parent = os.path.dirname(abs_dst)
                if parent and not os.path.exists(parent):
                    os.makedirs(parent, exist_ok=True)
                if os.path.isdir(src):
                    if os.path.exists(abs_dst) and not os.path.isdir(abs_dst):
                        os.remove(abs_dst)
                    os.makedirs(abs_dst, exist_ok=True)
                else:
                    shutil.copy2(src, abs_dst)
                percent = int(((i + 1) / total) * 80)
                self.progress.emit(percent)
                self.status.emit(f"Aktualizuji: {rel}")
                for milestone in (25, 50, 75):
                    if percent >= milestone and milestone not in announced:
                        announced.add(milestone)
                        self.announce.emit(f"Aktualizace {milestone} procent dokončeno")

            # Smazání odstraněných souborů — jen dle starého manifestu, jen uvnitř installDir
            for rel in removed:
                if self.isInterruptionRequested():
                    self.finished_signal.emit(False, "Aktualizace zrušena uživatelem.")
                    return
                abs_path = os.path.abspath(os.path.join(self.dest_dir, rel))
                try:
                    common = os.path.commonpath([self.dest_dir.lower(), abs_path.lower()])
                except ValueError:
                    continue
                if common != self.dest_dir.lower():
                    continue
                if is_protected_dir(abs_path) or is_protected_dir(os.path.dirname(abs_path)):
                    continue
                if "uninstall" in os.path.basename(abs_path).lower():
                    continue
                if os.path.isfile(abs_path):
                    try:
                        os.remove(abs_path)
                    except Exception as e:
                        errors.append(f"Odstranění {rel}: {e}")

            # Prázdné odstraněné adresáře
            old_dirs = sorted(self.old_manifest.get("dirs", []),
                              key=lambda p: p.count(os.sep), reverse=True)
            old_dirs_n = {os.path.normpath(d).lower() for d in old_dirs}
            new_dirs_n = {os.path.normpath(d).lower() for d in new_dirs}
            for rel in old_dirs:
                if os.path.normpath(rel).lower() in new_dirs_n:
                    continue
                abs_path = os.path.abspath(os.path.join(self.dest_dir, rel))
                try:
                    common = os.path.commonpath([self.dest_dir.lower(), abs_path.lower()])
                except ValueError:
                    continue
                if common != self.dest_dir.lower() or is_protected_dir(abs_path):
                    continue
                try:
                    if os.path.isdir(abs_path) and not os.listdir(abs_path):
                        os.rmdir(abs_path)
                except Exception:
                    pass

            # Zástupci 80–95 %
            self.progress.emit(80)
            exe_name = self.new_config.get("exeName") or os.path.basename(
                self.new_config.get("exePath", ""))
            if not exe_name:
                exe_name = (self.new_config.get("safeName") or "app") + ".exe"
            target_exe = os.path.join(self.dest_dir, exe_name)
            app_name = self.new_config.get("appName", "Aplikace")
            shortcuts_created = list(self.old_manifest.get("shortcuts", []))

            if self.new_config.get("createDesktopShortcut"):
                if self.isInterruptionRequested():
                    self.finished_signal.emit(False, "Aktualizace zrušena uživatelem.")
                    return
                self.status.emit("Obnovuji zástupce na ploše...")
                self.announce.emit("Obnovuji zástupce na ploše")
                desktop = get_known_folder("Desktop")
                shortcut_path = os.path.join(desktop, f"{app_name}.lnk")
                err = self.create_shortcut(target_exe, shortcut_path)
                self.progress.emit(88)
                if err:
                    errors.append(f"Zástupce na ploše: {err}")
                elif not any(shortcut_path == (s.get("path") if isinstance(s, dict) else s)
                             for s in shortcuts_created):
                    shortcuts_created.append({"path": shortcut_path, "scope": "desktop"})
            if self.new_config.get("createStartMenuShortcut"):
                if self.isInterruptionRequested():
                    self.finished_signal.emit(False, "Aktualizace zrušena uživatelem.")
                    return
                self.status.emit("Obnovuji zástupce v nabídce Start...")
                self.announce.emit("Obnovuji zástupce v nabídce Start")
                start_menu = get_known_folder("Programs")
                shortcut_path = os.path.join(start_menu, f"{app_name}.lnk")
                err = self.create_shortcut(target_exe, shortcut_path)
                self.progress.emit(95)
                if err:
                    errors.append(f"Zástupce v nabídce Start: {err}")
                elif not any(shortcut_path == (s.get("path") if isinstance(s, dict) else s)
                             for s in shortcuts_created):
                    shortcuts_created.append({"path": shortcut_path, "scope": "startmenu"})
            if not self.new_config.get("createDesktopShortcut") and not self.new_config.get(
                    "createStartMenuShortcut"):
                self.progress.emit(95)

            status_value = UpdateStatus.PARTIAL.value if errors else UpdateStatus.SUCCESS.value
            manifest_data = {
                "appName": self.new_config.get("appName", ""),
                "safeName": self.new_config.get("safeName", ""),
                "version": self.new_config.get("appVersion", ""),
                "installDir": self.dest_dir,
                "installedAt": datetime.now(timezone.utc).isoformat(),
                "files": sorted(new_files),
                "dirs": sorted(new_dirs, key=lambda p: p.count(os.sep), reverse=True),
                "shortcuts": shortcuts_created,
                "status": status_value,
            }
            write_manifest(manifest_data, self.dest_dir)
            write_config(self.new_config, self.dest_dir)
            self.progress.emit(100)
            self.announce.emit("Aktualizace dokončena na 100 procent")
            msg = "Aktualizace byla úspěšně dokončena."
            if removed:
                msg += f"\nOdstraněno zastaralých souborů: {len(removed)}."
            if errors:
                msg += "\n\nVarování:\n" + "\n".join(errors)
            self.finished_signal.emit(True, msg)
        except Exception as e:
            self.announce.emit("Aktualizace selhala")
            self.finished_signal.emit(False, str(e))


class IntroPage(QWizardPage):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.setTitle("Aktualizace programu")
        text = (f"Vítá vás aktualizace programu {config.get('appName', 'Aplikace')} "
                f"na verzi {config.get('appVersion', '')}. Pokračujte stisknutím tlačítka Další.")
        self.setAccessibleName("Úvodní stránka aktualizace")
        self.setAccessibleDescription(text)
        layout = QVBoxLayout()
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.label.setAccessibleName(text)
        layout.addWidget(self.label)
        hint = QLabel("Aktualizace zachová vaši cílovou složku a obnoví zástupce. "
                      "Původní soubory, které nová verze již neobsahuje, budou bezpečně odstraněny.")
        hint.setWordWrap(True)
        hint.setAccessibleName(hint.text())
        layout.addWidget(hint)
        self.setLayout(layout)

    def initializePage(self):
        self.label.setFocus()


class DirectoryPage(QWizardPage):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.setTitle("Složka stávající instalace")
        text = "Vyberte složku, ve které je program nyní nainstalován (musí obsahovat manifest instalace)."
        self.setAccessibleName("Výběr složky stávající instalace")
        self.setAccessibleDescription(text)
        layout = QVBoxLayout()
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.label.setAccessibleName(text)
        layout.addWidget(self.label)

        row = QHBoxLayout()
        self.pathEdit = QLineEdit()
        self.pathEdit.setAccessibleName("Cesta ke stávající instalaci")
        self.pathEdit.setAccessibleDescription(
            "Absolutní cesta ke složce s nainstalovaným programem. Povinné pole.")
        browse = QPushButton("Procházet...")
        browse.setAccessibleName("Procházet a vybrat složku stávající instalace")
        browse.setAccessibleDescription("Otevře dialog pro výběr složky s nainstalovaným programem")
        browse.clicked.connect(self.browse)
        row.addWidget(self.pathEdit)
        row.addWidget(browse)
        layout.addWidget(QLabel("Cesta k instalaci:"))
        layout.addLayout(row)
        self.registerField("installPath*", self.pathEdit)

        if config.get("installDir", 0) == 0:
            pf = os.environ.get("ProgramW6432") or os.environ.get("ProgramFiles", "")
        else:
            pf = os.environ.get("ProgramFiles(x86)") or os.environ.get("ProgramFiles", "")
        folder_name = config.get("safeName") or config.get("appName", "Aplikace")
        if pf:
            self.pathEdit.setText(os.path.join(pf, folder_name))

        self.infoLabel = QLabel("")
        self.infoLabel.setWordWrap(True)
        self.infoLabel.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.infoLabel.setAccessibleName("Informace o nalezené instalaci")
        layout.addWidget(self.infoLabel)

        self.errorLabel = QLabel("")
        self.errorLabel.setWordWrap(True)
        self.errorLabel.setStyleSheet("color: #a00;")
        self.errorLabel.setAccessibleName("")
        self.errorLabel.hide()
        layout.addWidget(self.errorLabel)
        self.setLayout(layout)
        self.pathEdit.textChanged.connect(self.refresh_info)

    def browse(self):
        directory = QFileDialog.getExistingDirectory(self, "Vybrat složku stávající instalace")
        if directory:
            self.pathEdit.setText(directory)

    def current_manifest(self):
        return load_manifest(self.pathEdit.text().strip())

    def refresh_info(self):
        m = self.current_manifest()
        if m is None:
            self.infoLabel.setText("Manifest zatím nenalezen — zkontrolujte cestu.")
            self.infoLabel.setAccessibleName("Manifest zatím nenalezen, zkontrolujte cestu.")
            return
        old_v = m.get("version", "—")
        new_v = self.config.get("appVersion", "—")
        cmp = compare_versions(old_v, new_v)
        if cmp == 0:
            state = "Nainstalovaná verze je stejná jako nová."
        elif cmp < 0:
            state = f"Aktualizace: {old_v} → {new_v}."
        else:
            state = f"Pozor: nainstalovaná verze {old_v} je novější než {new_v} (downgrade)."
        txt = (f"Nalezena instalace: {m.get('appName', '')} {old_v}, "
               f"{len(m.get('files', []))} souborů. {state}")
        self.infoLabel.setText(txt)
        self.infoLabel.setAccessibleName(txt)

    def initializePage(self):
        self.refresh_info()
        self.label.setFocus()

    def validatePage(self):
        path = self.pathEdit.text().strip()
        if not path:
            return self._fail("Cesta nesmí být prázdná.")
        if not os.path.isabs(path):
            return self._fail("Cesta musí být absolutní (např. C:\\Program Files\\Aplikace).")
        if ".." in path.split(os.sep):
            return self._fail("Cesta nesmí obsahovat '..'.")
        if is_protected_dir(path):
            return self._fail("Zvolená cesta je chráněná (systémový adresář nebo kořen disku).")
        if not os.path.isdir(path):
            return self._fail("Složka neexistuje. Nejdřív aplikaci nainstalujte instalátorem.")
        m = load_manifest(path)
        if m is None:
            return self._fail("Manifest instalace nenalezen nebo je poškozen. "
                              "Aktualizaci nelze bezpečně provést.")
        old_v = m.get("version", "")
        new_v = self.config.get("appVersion", "")
        if compare_versions(old_v, new_v) > 0:
            reply = QMessageBox.question(
                self, "Downgrade",
                f"Nainstalovaná verze ({old_v}) je novější než aktualizace ({new_v}). "
                "Opravdu chcete pokračovat a přejít na starší verzi?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return False
        self.wizard().old_manifest = m
        self.errorLabel.hide()
        return True

    def _fail(self, text):
        self.errorLabel.setText(text)
        self.errorLabel.setAccessibleName(f"Chyba: {text}")
        self.errorLabel.show()
        return False


class SummaryPage(QWizardPage):
    """Přístupný souhrn — jeden QTextBrowser čitelný šipkami i virtuálním kurzorem."""

    def __init__(self, config, source_dir):
        super().__init__()
        self.config = config
        self.source_dir = source_dir
        self.setTitle("Souhrn aktualizace")
        self.setAccessibleName("Souhrn aktualizace")
        self.setAccessibleDescription(
            "Přehled aktualizace před spuštěním. Čtěte šipkami v textovém poli.")
        layout = QVBoxLayout()
        intro = QLabel("Zkontrolujte nastavení před zahájením aktualizace. "
                       "Text přečtete šipkami, Tab vás posune na tlačítka.")
        intro.setWordWrap(True)
        intro.setAccessibleName(intro.text())
        layout.addWidget(intro)
        self.summaryView = QTextBrowser()
        self.summaryView.setReadOnly(True)
        self.summaryView.setOpenExternalLinks(False)
        self.summaryView.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.summaryView.setAccessibleName("Souhrn aktualizace")
        self.summaryView.setAccessibleDescription(
            "Textové shrnutí aktualizace. Pohyb šipkami nahoru a dolů, výběr klávesnicí.")
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
        install_path = self.field("installPath") or ""
        try:
            wiz = self.wizard()
        except Exception:
            wiz = None
        m = (getattr(wiz, "old_manifest", None) if wiz is not None else None) or {}
        if not m and install_path:
            try:
                m = load_manifest(install_path) or {}
            except Exception:
                m = {}
        old_v = m.get("version", "—")
        new_v = self.config.get("appVersion", "—")
        new_files, _ = collect_payload_files(self.source_dir)
        old_files = m.get("files", [])
        old_n = {os.path.normpath(f).lower() for f in old_files}
        new_n = {os.path.normpath(f).lower() for f in new_files}
        added = len(new_n - old_n)
        removed = len(old_n - new_n)
        lines = [
            f"Aplikace: {self.config.get('appName', '')}",
            f"Nainstalovaná verze: {old_v}",
            f"Nová verze: {new_v}",
            f"Cílová složka: {install_path}",
            f"Nových souborů: {added}",
            f"Odstraněných zastaralých souborů: {removed}",
            f"Celkem souborů v nové verzi: {len(new_files)}",
        ]
        return "\n".join(lines)

    def initializePage(self):
        text = self.summary_text()
        self.summaryView.setPlainText(text)
        self.summaryView.setAccessibleName(f"Souhrn aktualizace. {text}")
        self.summaryView.moveCursor(self.summaryView.textCursor().Start)
        self.summaryView.setFocus()

    def copy_summary(self):
        try:
            QApplication.clipboard().setText(self.summaryView.toPlainText())
            self.summaryView.setAccessibleDescription("Souhrn zkopírován do schránky.")
        except Exception:
            pass


class ProgressPage(QWizardPage):
    def __init__(self, config, source_dir):
        super().__init__()
        self.config = config
        self.source_dir = source_dir
        self.setTitle("Průběh aktualizace")
        text = "Probíhá aktualizace, prosím čekejte."
        self.setAccessibleName(text)
        layout = QVBoxLayout()
        self.label = QLabel(text)
        self.label.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.label.setAccessibleName(text)
        layout.addWidget(self.label)
        self.statusLabel = QLabel("Připraveno...")
        self.statusLabel.setAccessibleName("Stav: Připraveno")
        layout.addWidget(self.statusLabel)
        self.liveLabel = QLabel("")
        self.liveLabel.setAccessibleName("")
        self.liveLabel.setAccessibleDescription("Průběh aktualizace")
        layout.addWidget(self.liveLabel)
        self.progressBar = QProgressBar()
        self.progressBar.setAccessibleName("Průběh aktualizace v procentech")
        self.progressBar.setAccessibleDescription("Ukazatel průběhu 0 až 100 procent")
        layout.addWidget(self.progressBar)
        self.setLayout(layout)
        self._last_announce = 0.0

    def initializePage(self):
        self.label.setFocus()
        self.wizard().button(QWizard.WizardButton.BackButton).setEnabled(False)
        dest = self.field("installPath")
        old_manifest = getattr(self.wizard(), "old_manifest", None) or load_manifest(dest) or {}
        self.wizard()._update_thread = UpdateThread(
            self.source_dir, dest, self.config, old_manifest)
        self.wizard()._update_thread.progress.connect(self.progressBar.setValue)
        self.wizard()._update_thread.status.connect(self.on_status)
        self.wizard()._update_thread.announce.connect(self.on_announce)
        self.wizard()._update_thread.finished_signal.connect(self.on_finished)
        self.wizard()._update_thread.start()

    def on_status(self, text):
        self.statusLabel.setText(text)
        self.statusLabel.setAccessibleName(f"Stav: {text}")

    def on_announce(self, text):
        now = time.monotonic()
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

    def on_finished(self, success, message):
        if success:
            self.wizard().updateResultMessage = message
            self.wizard().next()
        else:
            QMessageBox.critical(self, "Chyba", f"Aktualizace selhala: {message}")


class FinishPage(QWizardPage):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.setTitle("Aktualizace dokončena")
        text = (f"Program {config.get('appName', 'Aplikace')} byl úspěšně aktualizován "
                f"na verzi {config.get('appVersion', '')}. Nyní můžete okno zavřít tlačítkem Dokončit.")
        self.setAccessibleName("Aktualizace dokončena")
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
        msg = getattr(self.wizard(), "updateResultMessage", "")
        if msg and "Varování" in msg:
            warning_text = msg[msg.find("Varování"):]
            self.warningLabel.setText(warning_text)
            self.warningLabel.setAccessibleName(warning_text)
            self.warningLabel.show()
            self.warningLabel.setFocus()
        else:
            self.warningLabel.hide()
            self.label.setFocus()


class AccessibleUpdater(QWizard):
    def __init__(self, config, source_dir):
        super().__init__()
        self.config = config
        self.source_dir = source_dir
        self.old_manifest: dict = {}
        self.updateResultMessage = ""
        self._update_thread = None
        self.setWindowTitle(f"Aktualizace - {config.get('appName', 'Aplikace')}")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setButtonText(QWizard.WizardButton.NextButton, "Další >")
        self.setButtonText(QWizard.WizardButton.BackButton, "< Zpět")
        self.setButtonText(QWizard.WizardButton.CancelButton, "Zrušit")
        self.setButtonText(QWizard.WizardButton.FinishButton, "Dokončit")
        self.addPage(IntroPage(config))
        self.addPage(DirectoryPage(config))
        self.addPage(SummaryPage(config, source_dir))
        self.addPage(ProgressPage(config, source_dir))
        self.addPage(FinishPage(config))

    def reject(self):
        if self._update_thread is not None and self._update_thread.isRunning():
            reply = QMessageBox.question(
                self, "Přerušit aktualizaci",
                "Aktualizace probíhá. Chcete ji přerušit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    self._update_thread.requestInterruption()
                    self._update_thread.wait(3000)
                except Exception:
                    pass
                super().reject()
            return
        msg = (f"Chcete skutečně přerušit aktualizaci programu {self.config.get('appName', '')}?\n\n"
               "Stiskněte Ano pro ukončení nebo Ne pro pokračování.")
        reply = QMessageBox.question(
            self, "Ukončení", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if self._update_thread is not None and self._update_thread.isRunning():
                try:
                    self._update_thread.requestInterruption()
                    self._update_thread.wait(2000)
                except Exception:
                    pass
            super().reject()


def main():
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_path, "config.json")
    if not os.path.exists(config_path):
        config = {"appName": "Aplikace", "appVersion": "1.0", "appAuthor": "",
                  "installDir": 0, "exePath": ""}
    else:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    if not config.get("exeName"):
        exe_path = config.get("exePath", "")
        if exe_path:
            config["exeName"] = os.path.basename(exe_path)
        else:
            config["exeName"] = (config.get("safeName") or config.get("appName") or "app") + ".exe"
    app = QApplication(sys.argv)
    source_dir = os.path.join(base_path, "payload")
    if not os.path.exists(source_dir):
        os.makedirs(source_dir, exist_ok=True)
    wizard = AccessibleUpdater(config, source_dir)
    wizard.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
