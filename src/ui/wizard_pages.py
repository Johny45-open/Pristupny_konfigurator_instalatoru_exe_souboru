from PyQt6.QtWidgets import (QWizardPage, QVBoxLayout, QLabel, QLineEdit, QFileDialog, 
                             QPushButton, QHBoxLayout, QComboBox, QMessageBox, QProgressDialog, QApplication, QCheckBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
import os
from generator.iss_generator import generate_iss
from generator.exe_builder import build_installer

class BuildThread(QThread):
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, data, output_path):
        super().__init__()
        self.data = data
        self.output_path = output_path

    def run(self):
        try:
            success = build_installer(self.data, self.output_path)
            if success:
                self.finished_signal.emit(True, "Instalátor byl úspěšně vytvořen.")
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
        self.setLayout(layout)

    def initializePage(self):
        self.label.setFocus()

class AppInfoPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Informace o aplikaci")
        self.setAccessibleName("Informace o aplikaci")
        
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Název aplikace:"))
        self.appNameEdit = QLineEdit()
        self.appNameEdit.setAccessibleName("Název aplikace, povinné pole")
        layout.addWidget(self.appNameEdit)
        self.registerField("appName*", self.appNameEdit)

        layout.addWidget(QLabel("Autor:"))
        self.appAuthorEdit = QLineEdit()
        self.appAuthorEdit.setAccessibleName("Autor, nepovinné pole")
        layout.addWidget(self.appAuthorEdit)
        self.registerField("appAuthor", self.appAuthorEdit)

        layout.addWidget(QLabel("Verze:"))
        self.appVersionEdit = QLineEdit()
        self.appVersionEdit.setText("1.0.0")
        self.appVersionEdit.setAccessibleName("Verze, nepovinné pole")
        layout.addWidget(self.appVersionEdit)
        self.registerField("appVersion", self.appVersionEdit)

        self.setLayout(layout)

class FileSelectionPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Výběr souborů")
        self.setAccessibleName("Výběr souborů")
        
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Cesta k hlavnímu EXE souboru:"))
        exeLayout = QHBoxLayout()
        self.exePathEdit = QLineEdit()
        self.exePathEdit.setAccessibleName("Cesta k hlavnímu EXE souboru, povinné pole")
        self.exeBrowseBtn = QPushButton("Procházet...")
        self.exeBrowseBtn.setAccessibleName("Procházet a vybrat hlavní EXE soubor")
        self.exeBrowseBtn.clicked.connect(self.browseExe)
        exeLayout.addWidget(self.exePathEdit)
        exeLayout.addWidget(self.exeBrowseBtn)
        layout.addLayout(exeLayout)
        self.registerField("exePath*", self.exePathEdit)

        self.dirDescLabel = QLabel("Složka se všemi soubory aplikace (DŮLEŽITÉ: U --onedir vyberte složku, kde je přímo váš EXE a složka _internal):")
        self.dirDescLabel.setWordWrap(True)
        layout.addWidget(self.dirDescLabel)
        dirLayout = QHBoxLayout()
        self.dirPathEdit = QLineEdit()
        self.dirPathEdit.setPlaceholderText("Např. C:\\projekty\\moje_aplikace\\dist\\hlavni_program")
        self.dirPathEdit.setAccessibleName("Složka se všemi soubory aplikace, nepovinné pole (pokud není potřeba přibalit další soubory)")
        self.dirBrowseBtn = QPushButton("Procházet...")
        self.dirBrowseBtn.setAccessibleName("Procházet a vybrat složku aplikace")
        self.dirBrowseBtn.clicked.connect(self.browseDir)
        dirLayout.addWidget(self.dirPathEdit)
        dirLayout.addWidget(self.dirBrowseBtn)
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
        layout.addWidget(QLabel("Výchozí umístění instalace:"))
        self.installDirCombo = QComboBox()
        self.installDirCombo.addItems(["Program Files (64-bit)", "Program Files (32-bit/x86)"])
        self.installDirCombo.setAccessibleName("Výchozí umístění")
        layout.addWidget(self.installDirCombo)
        self.registerField("installDir", self.installDirCombo)

        layout.addSpacing(20)
        
        self.createDesktopShortcut = QCheckBox("Vytvořit zástupce na ploše")
        self.createDesktopShortcut.setAccessibleName("Vytvořit zástupce na ploše")
        self.createDesktopShortcut.setChecked(True)
        layout.addWidget(self.createDesktopShortcut)
        self.registerField("createDesktopShortcut", self.createDesktopShortcut)

        self.createStartMenuShortcut = QCheckBox("Vytvořit zástupce v nabídce Start")
        self.createStartMenuShortcut.setAccessibleName("Vytvořit zástupce v nabídce Start")
        self.createStartMenuShortcut.setChecked(True)
        layout.addWidget(self.createStartMenuShortcut)
        self.registerField("createStartMenuShortcut", self.createStartMenuShortcut)

        self.setLayout(layout)

class FinishPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Dokončení")
        desc = "Nyní si můžete vybrat, zda chcete vygenerovat pouze Inno Setup skript, nebo přímo vytvořit hotový EXE instalátor."
        self.setAccessibleName("Dokončení")
        self.is_building = False
        self.is_finished = False
        
        layout = QVBoxLayout()
        self.label = QLabel(desc)
        self.label.setWordWrap(True)
        self.label.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        layout.addWidget(self.label)

        self.btnIss = QPushButton("Generovat .iss skript")
        self.btnIss.setAccessibleName("Generovat ISS")
        self.btnIss.clicked.connect(self.handle_iss)
        layout.addWidget(self.btnIss)

        self.btnExe = QPushButton("Vytvořit přímo EXE instalátor")
        self.btnExe.setAccessibleName("Vytvořit EXE")
        self.btnExe.clicked.connect(self.handle_exe)
        layout.addWidget(self.btnExe)

        self.setLayout(layout)

    def initializePage(self):
        self.label.setFocus()

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
            template_path = os.path.join(os.path.dirname(__file__), "..", "..", "templates", "base_template.iss")
            try:
                generate_iss(data, file_path, template_path)
                # Dáme systému čas zpracovat návrat fokusu z file dialogu
                QApplication.processEvents()
                QMessageBox.information(self, "Úspěch", f"Skript byl úspěšně vygenerován.")
            except Exception as e:
                QApplication.processEvents()
                QMessageBox.critical(self, "Chyba", str(e))

    def handle_exe(self):
        data = self.get_data()
        if not self.validate_paths(data): return
        
        file_path, _ = QFileDialog.getSaveFileName(self, "Uložit EXE instalátor", f"{data['appName']}_Setup.exe", "Spustitelný soubor (*.exe)")
        if file_path:
            self.is_building = True
            progress = QProgressDialog("Sestavuji instalátor, prosím čekejte...", None, 0, 0, self.window())
            progress.setWindowTitle("Pracuji...")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setWindowFlags(Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)
            progress.setAccessibleName("Okénko průběhu")
            progress.show()
            progress.setFocus()
            
            QApplication.processEvents()
            
            self.build_thread = BuildThread(data, file_path)
            self.build_thread.finished_signal.connect(self.on_build_finished)
            self.build_thread.finished_signal.connect(progress.close)
            self.build_thread.start()

    def on_build_finished(self, success, message):
        self.is_building = False
        if success:
            self.is_finished = True
        # Mírné zpoždění (200ms) umožní NVDA dokončit hlášení o návratu fokusu 
        # a čistě přejít na nové hlášení o úspěchu/chybě.
        QTimer.singleShot(200, lambda: self.show_result(success, message))

    def show_result(self, success, message):
        if success:
            QMessageBox.information(self, "Úspěch", message)
        else:
            QMessageBox.critical(self, "Chyba při sestavování", message)

    def validatePage(self):
        return True
