from PyQt6.QtWidgets import (QWizardPage, QVBoxLayout, QLabel, QLineEdit, QFileDialog,
                             QPushButton, QHBoxLayout, QComboBox, QMessageBox, QProgressDialog, QApplication, QCheckBox,
                             QProgressBar, QGroupBox, QFormLayout, QTextBrowser)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices
import os
import re
import time
import unicodedata
from generator.iss_generator import generate_iss
from generator.exe_builder import build_installer, build_updater

try:
    from version import __version__
except ImportError:
    try:
        from src.version import __version__
    except ImportError:
        __version__ = "0.0.0-dev"

def _slugify_fallback(value: str) -> str:
    try:
        from core.config import slugify as _slugify
    except Exception:
        try:
            from src.core.config import slugify as _slugify
        except Exception:
            _slugify = None  # type: ignore
    if _slugify is not None:
        try:
            return _slugify(value)
        except Exception:
            pass
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value).strip().replace(" ", "_")
    return re.sub(r"[-\s]+", "-", value) or "app"


class BuildThread(QThread):
    finished_signal = pyqtSignal(bool, str)
    progress_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str)

    def __init__(self, data, output_path, mode="installer"):
        super().__init__()
        self.data = data
        self.output_path = output_path
        self.mode = mode  # "installer" | "updater"

    def run(self):
        try:
            def cb(text, percent):
                if text:
                    self.status_signal.emit(text)
                if percent is not None:
                    self.progress_signal.emit(int(percent))

            builder = build_updater if self.mode == "updater" else build_installer
            success = builder(self.data, self.output_path, progress_callback=cb)
            if success:
                self.finished_signal.emit(True, self.output_path)
            else:
                self.finished_signal.emit(False, "Sestavení skončilo bez chyby, ale soubor nebyl nalezen.")
        except Exception as e:
            self.finished_signal.emit(False, str(e))

class IntroPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Vítejte v konfigurátoru")
        text = "Tento průvodce vám pomůže vytvořit přístupný instalátor pro vaši aplikaci."
        self.setAccessibleName("Úvodní stránka")

        layout = QVBoxLayout()
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.label.setAccessibleName(f"Vítejte. {text}")
        layout.addWidget(self.label)

        # Verze konfigurátoru – odděleně od verze balené aplikace (AppInfoPage)
        version_text = f"Verze aplikace: v{__version__}"
        self.versionLabel = QLabel(version_text)
        self.versionLabel.setWordWrap(True)
        self.versionLabel.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.versionLabel.setAccessibleName(f"Verze konfigurátoru {__version__}")
        self.versionLabel.setAccessibleDescription("Verze tohoto konfigurátoru, nikoli verze balené aplikace")
        self.versionLabel.setStyleSheet("color: palette(mid); font-size: 9pt;")
        layout.addWidget(self.versionLabel)

        self.setLayout(layout)

    def initializePage(self):
        self.label.setFocus()

class AppInfoPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Informace o aplikaci")
        self.setAccessibleName("Informace o aplikaci")

        form = QFormLayout()

        self.appNameLabel = QLabel("Název aplikace:")
        self.appNameEdit = QLineEdit()
        self.appNameLabel.setBuddy(self.appNameEdit)
        self.appNameEdit.setAccessibleName("Název aplikace, povinné pole")
        self.appNameEdit.setAccessibleDescription("Zadejte název aplikace, jak se zobrazí v instalátoru. Povinné pole.")
        form.addRow(self.appNameLabel, self.appNameEdit)
        self.registerField("appName*", self.appNameEdit)

        self.appAuthorLabel = QLabel("Autor:")
        self.appAuthorEdit = QLineEdit()
        self.appAuthorLabel.setBuddy(self.appAuthorEdit)
        self.appAuthorEdit.setAccessibleName("Autor, nepovinné pole")
        self.appAuthorEdit.setAccessibleDescription("Jméno autora nebo firmy. Nepovinné pole, může zůstat prázdné.")
        form.addRow(self.appAuthorLabel, self.appAuthorEdit)
        self.registerField("appAuthor", self.appAuthorEdit)

        self.appVersionLabel = QLabel("Verze:")
        self.appVersionEdit = QLineEdit()
        self.appVersionEdit.setText("1.0.0")
        self.appVersionLabel.setBuddy(self.appVersionEdit)
        self.appVersionEdit.setAccessibleName("Verze, nepovinné pole")
        self.appVersionEdit.setAccessibleDescription("Verze balené aplikace ve formátu např. 1.0.0. Nepovinné pole, výchozí 1.0.0.")
        form.addRow(self.appVersionLabel, self.appVersionEdit)
        self.registerField("appVersion", self.appVersionEdit)

        layout = QVBoxLayout()
        layout.addLayout(form)
        self.setLayout(layout)

class FileSelectionPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Výběr souborů")
        self.setAccessibleName("Výběr souborů")

        layout = QVBoxLayout()

        self.exeLabel = QLabel("Cesta k hlavnímu EXE souboru:")
        self.exeLabel.setWordWrap(True)
        exeLayout = QHBoxLayout()
        self.exePathEdit = QLineEdit()
        self.exeLabel.setBuddy(self.exePathEdit)
        self.exePathEdit.setAccessibleName("Cesta k hlavnímu EXE souboru, povinné pole")
        self.exePathEdit.setAccessibleDescription("Absolutní cesta k hlavnímu EXE souboru vaší aplikace. Povinné pole.")
        self.exeBrowseBtn = QPushButton("Procházet...")
        self.exeBrowseBtn.setAccessibleName("Procházet a vybrat hlavní EXE soubor")
        self.exeBrowseBtn.setAccessibleDescription("Otevře dialog pro výběr EXE souboru")
        self.exeBrowseBtn.clicked.connect(self.browseExe)
        exeLayout.addWidget(self.exePathEdit)
        exeLayout.addWidget(self.exeBrowseBtn)
        layout.addWidget(self.exeLabel)
        layout.addLayout(exeLayout)
        self.registerField("exePath*", self.exePathEdit)

        self.dirDescLabel = QLabel("Složka se všemi soubory aplikace (DŮLEŽITÉ: U --onedir vyberte složku, kde je přímo váš EXE a složka _internal):")
        self.dirDescLabel.setWordWrap(True)
        self.dirDescLabel.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.dirDescLabel.setAccessibleName("Nápověda: složka se všemi soubory aplikace")
        self.dirDescLabel.setAccessibleDescription("Vyberte složku, kde je váš EXE a případně složka _internal se závislostmi. Nepovinné pokud není potřeba přibalit další soubory.")
        layout.addWidget(self.dirDescLabel)

        self.dirLabel = QLabel("Složka aplikace:")
        self.dirLabel.setWordWrap(True)
        dirLayout = QHBoxLayout()
        self.dirPathEdit = QLineEdit()
        self.dirPathEdit.setPlaceholderText("Např. C:\\projekty\\moje_aplikace\\dist\\hlavni_program")
        self.dirLabel.setBuddy(self.dirPathEdit)
        self.dirPathEdit.setAccessibleName("Složka se všemi soubory aplikace, nepovinné pole (pokud není potřeba přibalit další soubory)")
        self.dirPathEdit.setAccessibleDescription("Cesta ke složce obsahující všechny soubory aplikace. Nepovinné pole.")
        self.dirBrowseBtn = QPushButton("Procházet...")
        self.dirBrowseBtn.setAccessibleName("Procházet a vybrat složku aplikace")
        self.dirBrowseBtn.setAccessibleDescription("Otevře dialog pro výběr složky aplikace")
        self.dirBrowseBtn.clicked.connect(self.browseDir)
        dirLayout.addWidget(self.dirPathEdit)
        dirLayout.addWidget(self.dirBrowseBtn)
        layout.addWidget(self.dirLabel)
        layout.addLayout(dirLayout)
        self.registerField("dirPath", self.dirPathEdit)

        self.setLayout(layout)

    def browseExe(self):
        file, _ = QFileDialog.getOpenFileName(self, "Vybrat EXE soubor", "", "Spustitelné soubory (*.exe)")
        if file:
            self.exePathEdit.setText(file)
            # Auto-detekce složky aplikace (pokud je vedle EXE složka _internal nebo lib)
            exe_dir = os.path.dirname(os.path.abspath(file))
            if os.path.exists(os.path.join(exe_dir, "_internal")) or os.path.exists(os.path.join(exe_dir, "lib")):
                if not self.dirPathEdit.text():
                    self.dirPathEdit.setText(exe_dir)
                    QMessageBox.information(self, "Detekována složka aplikace",
                        "V blízkosti EXE souboru byla nalezena složka se závislostmi (_internal nebo lib). "
                        "Automaticky jsem ji nastavil jako složku aplikace.")

    def browseDir(self):
        directory = QFileDialog.getExistingDirectory(self, "Vybrat složku aplikace")
        if directory:
            self.dirPathEdit.setText(directory)

class InstallationSettingsPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Nastavení instalace")
        self.setAccessibleName("Nastavení instalace")

        layout = QVBoxLayout()
        self.installDirLabel = QLabel("Výchozí umístění instalace:")
        self.installDirCombo = QComboBox()
        self.installDirCombo.addItems(["Program Files (64-bit)", "Program Files (32-bit/x86)"])
        self.installDirLabel.setBuddy(self.installDirCombo)
        self.installDirCombo.setAccessibleName("Výchozí umístění")
        self.installDirCombo.setAccessibleDescription("Vyberte výchozí cílovou složku instalace: Program Files 64-bit nebo 32-bit.")
        layout.addWidget(self.installDirLabel)
        layout.addWidget(self.installDirCombo)
        self.registerField("installDir", self.installDirCombo)

        layout.addSpacing(20)

        group = QGroupBox("Zástupci")
        group.setAccessibleName("Zástupci")
        group.setAccessibleDescription("Nastavení vytváření zástupců na ploše a v nabídce Start")
        groupLayout = QVBoxLayout()

        self.createDesktopShortcut = QCheckBox("Vytvořit zástupce na ploše")
        self.createDesktopShortcut.setAccessibleName("Vytvořit zástupce na ploše")
        self.createDesktopShortcut.setAccessibleDescription("Zaškrtněte pro vytvoření zástupce na pracovní ploše")
        self.createDesktopShortcut.setChecked(True)
        groupLayout.addWidget(self.createDesktopShortcut)
        self.registerField("createDesktopShortcut", self.createDesktopShortcut)

        self.createStartMenuShortcut = QCheckBox("Vytvořit zástupce v nabídce Start")
        self.createStartMenuShortcut.setAccessibleName("Vytvořit zástupce v nabídce Start")
        self.createStartMenuShortcut.setAccessibleDescription("Zaškrtněte pro vytvoření zástupce v nabídce Start")
        self.createStartMenuShortcut.setChecked(True)
        groupLayout.addWidget(self.createStartMenuShortcut)
        self.registerField("createStartMenuShortcut", self.createStartMenuShortcut)

        group.setLayout(groupLayout)
        layout.addWidget(group)

        self.setLayout(layout)

class SummaryPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Shrnutí")
        self.setSubTitle("Zkontrolujte zadané hodnoty před sestavením instalátoru a aktualizace")
        self.setAccessibleName("Shrnutí nastavení")
        self.setAccessibleDescription(
            "Přehled všech zadaných hodnot před sestavením. Čtěte šipkami v textovém poli.")

        layout = QVBoxLayout()
        hint = QLabel("Zkontrolujte souhrn. Text přečtete šipkami nahoru/dolů, "
                      "Tab vás posune na tlačítko Kopírovat a navigaci průvodce.")
        hint.setWordWrap(True)
        hint.setAccessibleName(hint.text())
        layout.addWidget(hint)
        # Přístupný souhrn: QTextBrowser místo QLabel — čitelný šipkami i virtuálním
        # kurzorem NVDA/JAWS bez objektové navigace, v Tab-orderu.
        self.summaryView = QTextBrowser()
        self.summaryView.setReadOnly(True)
        self.summaryView.setOpenExternalLinks(False)
        self.summaryView.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.summaryView.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard)
        self.summaryView.setAccessibleName("Shrnutí zadaných hodnot")
        self.summaryView.setAccessibleDescription(
            "Textové shrnutí: název, verze, autor, cesty, zástupci a co se bude vytvářet. "
            "Pohyb šipkami nahoru a dolů.")
        layout.addWidget(self.summaryView)
        copy_btn = QPushButton("Kopírovat souhrn do schránky")
        copy_btn.setAccessibleName("Kopírovat souhrn do schránky")
        copy_btn.setAccessibleDescription("Zkopíruje text souhrnu do schránky")
        copy_btn.clicked.connect(self.copy_summary)
        layout.addWidget(copy_btn)
        self.setLayout(layout)

    def summary_text(self):
        appName = self.field("appName")
        appVersion = self.field("appVersion") or "1.0.0"
        appAuthor = self.field("appAuthor") or "—"
        exePath = self.field("exePath")
        dirPath = self.field("dirPath") or "— (není zadána, pouze EXE)"
        installDirIndex = self.field("installDir")
        # QComboBox registerField vrací index nebo text podle registrace; ošetříme obojí
        if isinstance(installDirIndex, int):
            installDir = "Program Files (64-bit)" if installDirIndex == 0 else "Program Files (32-bit/x86)"
        else:
            installDir = str(installDirIndex) if installDirIndex else "Program Files (64-bit)"
        createDesktop = self.field("createDesktopShortcut")
        createStart = self.field("createStartMenuShortcut")
        # bool nebo int
        desktopText = "Ano" if createDesktop else "Ne"
        startText = "Ano" if createStart else "Ne"
        safe = _slugify_fallback(str(appName or "app"))

        text = (
            f"Název aplikace: {appName}\n"
            f"Verze: {appVersion}\n"
            f"Autor: {appAuthor}\n"
            f"EXE soubor: {exePath}\n"
            f"Složka aplikace: {dirPath}\n"
            f"Cíl instalace: {installDir}\n"
            f"Zástupce na ploše: {desktopText}\n"
            f"Zástupce v nabídce Start: {startText}\n"
            f"—\n"
            f"Co se bude vytvářet:\n"
            f"1. Instalační program: {safe}_Setup.exe (plná instalace + odinstalátor uvnitř)\n"
            f"2. Aktualizační program: {safe}_Update.exe (offline aktualizace, vyžaduje manifest z instalace)\n"
            f"3. Inno Setup skript: {appName}.iss (volitelně, pro kompilaci v Inno Setup)\n"
            f"Poznámka: Aktualizační EXE funguje jen tam, kde už proběhla instalace "
            f"vytvořená instalačním EXE (kontroluje install_manifest.json)."
        )
        return text

    def copy_summary(self):
        try:
            QApplication.clipboard().setText(self.summaryView.toPlainText())
            self.summaryView.setAccessibleDescription("Souhrn zkopírován do schránky.")
        except Exception:
            pass

    def initializePage(self):
        text = self.summary_text()
        self.summaryView.setPlainText(text)
        self.summaryView.setAccessibleName(f"Shrnutí zadaných hodnot. {text}")
        try:
            self.summaryView.moveCursor(self.summaryView.textCursor().Start)
        except Exception:
            pass
        self.summaryView.setFocus()

class FinishPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Dokončení")
        desc = "Nyní si můžete vybrat: vygenerovat Inno Setup skript, vytvořit EXE instalátor, nebo vytvořit aktualizační EXE."
        self.setAccessibleName("Dokončení")
        self.setAccessibleDescription(desc)
        self.is_building = False
        self.is_finished = False
        self._output_path = ""
        self._build_mode = "installer"  # "installer" | "updater"
        self.progress_dialog = None
        self.build_thread = None
        self._last_announce_time = 0.0

        layout = QVBoxLayout()
        self.label = QLabel(desc)
        self.label.setWordWrap(True)
        self.label.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.label.setAccessibleName(desc)
        self.label.setAccessibleDescription("Volby pro generování skriptu, instalátoru nebo aktualizace")
        layout.addWidget(self.label)

        # live region pro throttled oznámení (1.2s)
        self.liveLabel = QLabel("")
        self.liveLabel.setAccessibleName("Živá oznámení průběhu")
        self.liveLabel.setAccessibleDescription("Průběžná oznámení pro čtečku obrazovky, throttling 1.2s")
        self.liveLabel.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # skrytý vizuálně ale přístupný pro QAccessible
        self.liveLabel.hide()
        layout.addWidget(self.liveLabel)

        self.btnIss = QPushButton("Generovat .iss skript")
        self.btnIss.setAccessibleName("Generovat ISS skript Inno Setup")
        self.btnIss.setAccessibleDescription("Vygeneruje Inno Setup skript .iss pro pozdější kompilaci")
        self.btnIss.clicked.connect(self.handle_iss)
        layout.addWidget(self.btnIss)

        self.btnExe = QPushButton("Vytvořit přímo EXE instalátor")
        self.btnExe.setAccessibleName("Vytvořit EXE instalátor přímo")
        self.btnExe.setAccessibleDescription("Přímo sestaví hotový EXE instalátor, může trvat několik minut")
        self.btnExe.clicked.connect(self.handle_exe)
        layout.addWidget(self.btnExe)

        self.btnUpdate = QPushButton("Vytvořit aktualizační EXE")
        self.btnUpdate.setAccessibleName("Vytvořit aktualizační EXE přímo")
        self.btnUpdate.setAccessibleDescription(
            "Sestaví offline aktualizační program Update.exe pro novou verzi. "
            "Vyžaduje předchozí instalaci vytvořenou instalátorem, může trvat několik minut")
        self.btnUpdate.clicked.connect(self.handle_update)
        layout.addWidget(self.btnUpdate)

        # Inline stav sestavování (viditelný i pro čtečku, přežije GC)
        self.statusLabel = QLabel("")
        self.statusLabel.setWordWrap(True)
        self.statusLabel.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.statusLabel.setAccessibleName("Stav sestavování")
        self.statusLabel.setAccessibleDescription("Aktuální stav sestavování instalátoru")
        self.statusLabel.hide()
        layout.addWidget(self.statusLabel)

        self.progressBar = QProgressBar()
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(0)
        self.progressBar.setAccessibleName("Průběh sestavování v procentech")
        self.progressBar.setAccessibleDescription("Ukazatel průběhu sestavování 0 až 100 procent")
        self.progressBar.setTextVisible(True)
        self.progressBar.hide()
        layout.addWidget(self.progressBar)

        self.resultLabel = QLabel("")
        self.resultLabel.setWordWrap(True)
        self.resultLabel.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard)
        self.resultLabel.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.resultLabel.setAccessibleName("Výsledek sestavování")
        self.resultLabel.setAccessibleDescription("Cesta k úspěšně vytvořenému souboru")
        self.resultLabel.hide()
        layout.addWidget(self.resultLabel)

        self.btnOpenFolder = QPushButton("Otevřít složku s instalátorem")
        self.btnOpenFolder.setAccessibleName("Otevřít složku s vytvořeným souborem")
        self.btnOpenFolder.setAccessibleDescription("Otevře složku obsahující vygenerovaný instalátor nebo aktualizaci ve správci souborů")
        self.btnOpenFolder.clicked.connect(self.open_output_folder)
        self.btnOpenFolder.hide()
        layout.addWidget(self.btnOpenFolder)

        self.setLayout(layout)

    def initializePage(self):
        self.label.setFocus()

    def _announce(self, text):
        # throttling 1.2s aby NVDA nebyl zahlcen
        now = time.monotonic()
        if now - self._last_announce_time < 1.2:
            return
        self._last_announce_time = now
        try:
            self.liveLabel.setText(text)
            self.liveLabel.setAccessibleName(text)
            self.liveLabel.setAccessibleDescription(text)
            from PyQt6.QtGui import QAccessible
            QAccessible.updateAccessibility(self.liveLabel, 0, QAccessible.Event.Alert)
            QAccessible.updateAccessibility(self.liveLabel, 0, QAccessible.Event.ValueChanged)
        except Exception:
            pass

    def get_data(self):
        return {
            "appName": self.field("appName"),
            "appVersion": self.field("appVersion"),
            "appAuthor": self.field("appAuthor"),
            "exePath": self.field("exePath"),
            "dirPath": self.field("dirPath"),
            "installDir": self.field("installDir"),
            "createDesktopShortcut": self.field("createDesktopShortcut"),
            "createStartMenuShortcut": self.field("createStartMenuShortcut")
        }

    def validate_paths(self, data):
        # Najdeme stránku s výběrem souborů, abychom mohli případně opravit UI
        file_page = None
        for i in self.wizard().pageIds():
            page = self.wizard().page(i)
            if isinstance(page, FileSelectionPage):
                file_page = page
                break

        # Kontrola, zda je EXE uvnitř vybrané složky (pokud je složka vybrána)
        if data['dirPath'] and os.path.exists(data['dirPath']):
            exe_path = os.path.abspath(data['exePath'])
            dir_path = os.path.abspath(data['dirPath'])
            
            if not exe_path.startswith(dir_path):
                # Speciální případ: uživatel vybral přímo _internal místo kořene aplikace
                if os.path.basename(dir_path).lower() in ["_internal", "lib"]:
                    parent_dir = os.path.dirname(dir_path)
                    if exe_path.startswith(parent_dir):
                        msg = QMessageBox(self)
                        msg.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
                        msg.setWindowTitle("Nesprávná složka")
                        msg.setText(f"Vybrali jste přímo složku '{os.path.basename(dir_path)}'. "
                            "Pro správnou funkci instalátoru je nutné vybrat celou složku aplikace "
                            "(tu, ve které je váš EXE i složka se závislostmi).\n\n"
                            "Chcete automaticky nastavit nadřazenou složku?")
                        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                        msg.button(QMessageBox.StandardButton.Yes).setText("Ano")
                        msg.button(QMessageBox.StandardButton.No).setText("Ne")
                        
                        if msg.exec() == QMessageBox.StandardButton.Yes and file_page:
                            file_page.dirPathEdit.setText(parent_dir)
                            return False # Necháme uživatele zkontrolovat
                
                QMessageBox.warning(self, "Chyba cesty", 
                    "Vybraný EXE soubor se nenachází ve vybrané složce aplikace. "
                    "Ujistěte se, že vybíráte složku, která váš EXE soubor obsahuje.")
                return False
            
            # Kontrola, zda je EXE přímo v té složce, ne o úroveň hlouběji
            rel_path = os.path.relpath(exe_path, dir_path)
            if os.path.dirname(rel_path) != "":
                msg = QMessageBox(self)
                msg.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
                msg.setWindowTitle("Varování")
                msg.setText("EXE soubor není přímo ve vybrané složce, ale v její podsložce. "
                    "To obvykle vede k chybám při spouštění (nenalezení DLL). "
                    "Chcete automaticky změnit složku aplikace na tu, kde je EXE?")
                msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                msg.button(QMessageBox.StandardButton.Yes).setText("Ano")
                msg.button(QMessageBox.StandardButton.No).setText("Ne")

                if msg.exec() == QMessageBox.StandardButton.Yes and file_page:
                    file_page.dirPathEdit.setText(os.path.dirname(exe_path))
                    return False # Necháme uživatele zkontrolovat změnu
        
        # Pokud je to onedir build (existuje _internal u EXE) a uživatel nevybral dirPath
        exe_dir = os.path.dirname(os.path.abspath(data['exePath']))
        if os.path.exists(os.path.join(exe_dir, "_internal")) and not data['dirPath']:
             msg = QMessageBox(self)
             msg.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
             msg.setWindowTitle("Chybějící složka závislostí")
             msg.setText("U vašeho EXE souboru byla nalezena složka '_internal', ale nevybrali jste 'Složku aplikace'. "
                "Bez ní program po instalaci nebude fungovat. Chcete ji doplnit automaticky?")
             msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
             msg.button(QMessageBox.StandardButton.Yes).setText("Ano")
             msg.button(QMessageBox.StandardButton.No).setText("Ne")
             
             if msg.exec() == QMessageBox.StandardButton.Yes and file_page:
                 file_page.dirPathEdit.setText(exe_dir)
                 return False

        return True

    def handle_iss(self):
        data = self.get_data()
        if not self.validate_paths(data): return
        
        file_path, _ = QFileDialog.getSaveFileName(self, "Uložit Inno Setup skript", f"{data['appName']}.iss", "Inno Setup Script (*.iss)")
        if file_path:
            # Zajisti příponu .iss
            if not file_path.lower().endswith(".iss"):
                file_path += ".iss"
            template_path = os.path.join(os.path.dirname(__file__), "..", "..", "templates", "base_template.iss")
            # Fallback pro dev i build
            if not os.path.exists(template_path):
                alt = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "templates", "base_template.iss")
                alt = os.path.abspath(alt)
                if os.path.exists(alt):
                    template_path = alt
            try:
                generate_iss(data, file_path, template_path)
                QApplication.processEvents()
                self.show_iss_success(file_path)
            except Exception as e:
                QApplication.processEvents()
                QMessageBox.critical(self, "Chyba", str(e))

    def show_iss_success(self, file_path):
        self._output_path = file_path
        self.resultLabel.setText(f"Skript byl úspěšně vygenerován:\n{file_path}")
        self.resultLabel.setAccessibleName(f"Skript byl úspěšně vygenerován: {file_path}")
        self.resultLabel.setAccessibleDescription(f"Cesta ke skriptu: {file_path}")
        self.resultLabel.show()
        self.btnOpenFolder.show()
        self.resultLabel.setFocus()
        QMessageBox.information(self, "Úspěch", f"Skript byl úspěšně vygenerován:\n{file_path}")

    def handle_exe(self):
        self._start_build("installer")

    def handle_update(self):
        self._start_build("updater")

    def _start_build(self, mode):
        data = self.get_data()
        if not self.validate_paths(data):
            return
        is_updater = (mode == "updater")
        default_name = f"{data['appName']}_Update.exe" if is_updater else f"{data['appName']}_Setup.exe"
        title = "Uložit aktualizační EXE" if is_updater else "Uložit EXE instalátor"
        file_path, _ = QFileDialog.getSaveFileName(
            self, title, default_name, "Spustitelný soubor (*.exe)")
        if file_path:
            if not file_path.lower().endswith(".exe"):
                file_path += ".exe"
            self._output_path = file_path
            self._build_mode = mode
            self.is_building = True
            self.is_finished = False
            self.btnIss.setEnabled(False)
            self.btnExe.setEnabled(False)
            self.btnUpdate.setEnabled(False)
            self.resultLabel.hide()
            self.btnOpenFolder.hide()

            if is_updater:
                start_text = "Sestavuji aktualizaci, prosím čekejte... Krok 1/2: Připravuji soubory..."
                start_acc = "Sestavuji aktualizaci, prosím čekejte. Krok 1 ze 2: Připravuji soubory"
                start_desc = "Probíhá krok 1 ze 2: příprava souborů aktualizace"
            else:
                start_text = "Sestavuji instalátor, prosím čekejte... Krok 1/3: Sestavuji odinstalátor..."
                start_acc = "Sestavuji instalátor, prosím čekejte. Krok 1 ze 3: Sestavuji odinstalátor"
                start_desc = "Probíhá krok 1 ze 3: sestavování odinstalátoru"
            # Inline progress - přežije GC, viditelný i pro čtečku
            self.statusLabel.setText(start_text)
            self.statusLabel.setAccessibleName(start_acc)
            self.statusLabel.setAccessibleDescription(start_desc)
            self.statusLabel.show()
            self.statusLabel.setFocus()
            self.progressBar.setRange(0, 100)
            self.progressBar.setValue(5)
            self.progressBar.show()

            # Modální dialog - držen jako self.* aby nebyl GC
            dlg_text = "Sestavuji aktualizaci, prosím čekejte..." if is_updater else "Sestavuji instalátor, prosím čekejte..."
            self.progress_dialog = QProgressDialog(dlg_text, None, 0, 0, self.window())
            self.progress_dialog.setWindowTitle("Pracuji...")
            self.progress_dialog.setLabelText(start_text)
            self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            self.progress_dialog.setWindowFlags(Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)
            self.progress_dialog.setAccessibleName("Okénko průběhu sestavování")
            self.progress_dialog.setAccessibleDescription(
                "Průběh sestavování aktualizace" if is_updater else "Průběh sestavování instalátoru")
            self.progress_dialog.setMinimumDuration(0)
            self.progress_dialog.setRange(0, 0)  # neurčitý dokud nepřijdou procenta
            self.progress_dialog.show()

            QApplication.processEvents()

            self.build_thread = BuildThread(data, file_path, mode=mode)
            self.build_thread.status_signal.connect(self.on_build_status)
            self.build_thread.progress_signal.connect(self.on_build_progress)
            self.build_thread.finished_signal.connect(self.on_build_finished)
            # Bezpečné zavření dialogu - přes lambda aby se nevolalo s bool/str argumenty
            self.build_thread.finished_signal.connect(lambda *_: self.close_progress_dialog())
            self.build_thread.finished_signal.connect(self.build_thread.deleteLater)
            self.build_thread.start()

    def on_build_status(self, text):
        self.statusLabel.setText(text)
        self.statusLabel.setAccessibleName(text)
        self.statusLabel.setAccessibleDescription(text)
        if self.progress_dialog:
            self.progress_dialog.setLabelText(text)
        self._announce(text)

    def on_build_progress(self, percent):
        try:
            p = int(percent)
            if p < 0: p = 0
            if p > 100: p = 100
            # Přepni z neurčitého na určitý při prvním procentu
            if self.progressBar.isHidden():
                self.progressBar.show()
            self.progressBar.setRange(0, 100)
            self.progressBar.setValue(p)
            if self.progress_dialog:
                # U QProgressDialog 0,0 = neurčitý, jinak určitý
                if self.progress_dialog.maximum() == 0 and self.progress_dialog.minimum() == 0:
                    self.progress_dialog.setRange(0, 100)
                self.progress_dialog.setValue(p)
        except Exception:
            pass

    def close_progress_dialog(self):
        if self.progress_dialog:
            try:
                self.progress_dialog.close()
            except Exception:
                pass
            self.progress_dialog = None

    def _build_noun(self):
        return "Aktualizace" if getattr(self, "_build_mode", "installer") == "updater" else "Instalátor"

    def on_build_finished(self, success, message):
        self.close_progress_dialog()
        self.is_building = False
        self.btnIss.setEnabled(True)
        self.btnExe.setEnabled(True)
        self.btnUpdate.setEnabled(True)
        noun = self._build_noun()
        if success:
            self.is_finished = True
            self.progressBar.setValue(100)
            self._output_path = message  # message je cesta u úspěchu
            self.statusLabel.setText(f"{noun} byl úspěšně vytvořen.")
            self.statusLabel.setAccessibleName(f"{noun} byl úspěšně vytvořen: {message}")
            self.statusLabel.setAccessibleDescription(f"{noun} byl úspěšně vytvořen: {message}")
            self.statusLabel.show()
            self._announce(f"{noun} byl úspěšně vytvořen: {message}")
        else:
            self.progressBar.hide()
            self.statusLabel.setText(f"Chyba: {message}")
            self.statusLabel.setAccessibleName(f"Chyba při sestavování: {message}")
            self.statusLabel.setAccessibleDescription(f"Chyba při sestavování: {message}")
            self.statusLabel.show()
            self._announce(f"Chyba při sestavování: {message}")
        # Mírné zpoždění (200ms) umožní NVDA dokončit hlášení o návratu fokusu
        # a čistě přejít na nové hlášení o úspěchu/chybě.
        QTimer.singleShot(200, lambda s=success, m=message: self.show_result(s, m))

    def show_result(self, success, message):
        noun = self._build_noun()
        if success:
            file_path = message
            self.statusLabel.setText(f"{noun} byl úspěšně vytvořen.")
            self.statusLabel.setAccessibleName(f"{noun} byl úspěšně vytvořen: {file_path}")
            self.statusLabel.setAccessibleDescription(f"{noun} byl úspěšně vytvořen: {file_path}")
            self.statusLabel.show()
            self.resultLabel.setText(f"Uloženo:\n{file_path}")
            self.resultLabel.setAccessibleName(f"Uloženo: {file_path}")
            self.resultLabel.setAccessibleDescription(f"Cesta k souboru: {file_path}")
            self.resultLabel.show()
            self.btnOpenFolder.show()
            self.resultLabel.setFocus()
            # Dialog s cestou a tlačítkem Otevřít složku
            msg = QMessageBox(self)
            msg.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
            msg.setWindowTitle("Úspěch")
            msg.setText(f"{noun} byl úspěšně vytvořen:\n{file_path}")
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            open_btn = msg.addButton("Otevřít složku", QMessageBox.ButtonRole.ActionRole)
            msg.setDefaultButton(QMessageBox.StandardButton.Ok)
            # Přístupnost
            msg.setAccessibleName(f"{noun} byl úspěšně vytvořen: {file_path}")
            msg.setAccessibleDescription(f"Cesta: {file_path}")
            msg.exec()
            if msg.clickedButton() == open_btn:
                self.open_output_folder()
        else:
            QMessageBox.critical(self, "Chyba při sestavování", message)
            self.statusLabel.setFocus()

    def open_output_folder(self):
        if not self._output_path or not os.path.exists(self._output_path):
            # Zkus alespoň adresář
            folder = os.path.dirname(os.path.abspath(self._output_path)) if self._output_path else ""
            if folder and os.path.isdir(folder):
                QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
                return
            QMessageBox.warning(self, "Soubor nenalezen", "Výstupní soubor nebyl nalezen.")
            return
        folder = os.path.dirname(os.path.abspath(self._output_path))
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def validatePage(self):
        return True
