from PyQt6.QtWidgets import (QWizardPage, QVBoxLayout, QLabel, QLineEdit, QFileDialog, 
                             QPushButton, QHBoxLayout, QComboBox, QMessageBox, QProgressDialog, QApplication)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
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
        self.setTitle("Vítejte v přístupném konfigurátoru")
        layout = QVBoxLayout()
        label = QLabel("Tento průvodce vám pomůže vytvořit přístupný instalátor pro vaši aplikaci.")
        label.setWordWrap(True)
        # Nastavení přístupného jména pro čtečky
        label.setAccessibleName("Úvodní text: Tento průvodce vám pomůže vytvořit přístupný instalátor pro vaši aplikaci.")
        layout.addWidget(label)
        self.setLayout(layout)

class AppInfoPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Informace o aplikaci")
        layout = QVBoxLayout()

        # Název aplikace
        self.appNameLabel = QLabel("Název aplikace:")
        self.appNameEdit = QLineEdit()
        self.appNameEdit.setAccessibleName("Zadejte název aplikace")
        layout.addWidget(self.appNameLabel)
        layout.addWidget(self.appNameEdit)
        self.registerField("appName*", self.appNameEdit)

        # Autor
        self.appAuthorLabel = QLabel("Autor:")
        self.appAuthorEdit = QLineEdit()
        self.appAuthorEdit.setAccessibleName("Zadejte jméno autora nebo firmy")
        layout.addWidget(self.appAuthorLabel)
        layout.addWidget(self.appAuthorEdit)
        self.registerField("appAuthor*", self.appAuthorEdit)

        # Verze
        self.appVersionLabel = QLabel("Verze:")
        self.appVersionEdit = QLineEdit()
        self.appVersionEdit.setPlaceholderText("1.0.0")
        self.appVersionEdit.setAccessibleName("Zadejte verzi aplikace, například 1.0.0")
        layout.addWidget(self.appVersionLabel)
        layout.addWidget(self.appVersionEdit)
        self.registerField("appVersion*", self.appVersionEdit)

        self.setLayout(layout)

class FileSelectionPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Výběr souborů")
        layout = QVBoxLayout()

        # Hlavní EXE
        self.exeLabel = QLabel("Cesta k hlavnímu EXE souboru:")
        exeLayout = QHBoxLayout()
        self.exePathEdit = QLineEdit()
        self.exePathEdit.setAccessibleName("Cesta k hlavnímu spustitelnému souboru")
        self.exeBrowseBtn = QPushButton("Procházet...")
        self.exeBrowseBtn.setAccessibleName("Tlačítko Procházet pro výběr EXE souboru")
        self.exeBrowseBtn.clicked.connect(self.browseExe)
        exeLayout.addWidget(self.exePathEdit)
        exeLayout.addWidget(self.exeBrowseBtn)
        layout.addWidget(self.exeLabel)
        layout.addLayout(exeLayout)
        self.registerField("exePath*", self.exePathEdit)

        # Složka (pro onedir)
        self.dirLabel = QLabel("Cesta ke složce aplikace (pokud používáte --onedir):")
        dirLayout = QHBoxLayout()
        self.dirPathEdit = QLineEdit()
        self.dirPathEdit.setAccessibleName("Cesta k hlavní složce aplikace")
        self.dirBrowseBtn = QPushButton("Procházet...")
        self.dirBrowseBtn.setAccessibleName("Tlačítko Procházet pro výběr složky aplikace")
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

    def browseDir(self):
        directory = QFileDialog.getExistingDirectory(self, "Vybrat složku aplikace")
        if directory:
            self.dirPathEdit.setText(directory)

class InstallationSettingsPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Nastavení instalace")
        layout = QVBoxLayout()

        # Výchozí složka
        self.installDirLabel = QLabel("Výchozí umístění instalace:")
        self.installDirCombo = QComboBox()
        self.installDirCombo.addItems(["Program Files (64-bit)", "Program Files (32-bit/x86)"])
        self.installDirCombo.setAccessibleName("Vyberte výchozí umístění instalace")
        layout.addWidget(self.installDirLabel)
        layout.addWidget(self.installDirCombo)
        self.registerField("installDir", self.installDirCombo)

        self.setLayout(layout)

class FinishPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Dokončení")
        layout = QVBoxLayout()
        self.label = QLabel("Nyní si můžete vybrat, zda chcete vygenerovat pouze Inno Setup skript, nebo přímo vytvořit hotový EXE instalátor.")
        self.label.setWordWrap(True)
        self.label.setAccessibleName(self.label.text())
        layout.addWidget(self.label)

        self.btnIss = QPushButton("Generovat .iss skript")
        self.btnIss.setAccessibleName("Tlačítko pro generování Inno Setup skriptu")
        self.btnIss.clicked.connect(self.handle_iss)
        layout.addWidget(self.btnIss)

        self.btnExe = QPushButton("Vytvořit přímo EXE instalátor")
        self.btnExe.setAccessibleName("Tlačítko pro přímé vytvoření hotového EXE instalátoru. Pozor, sestavování může trvat až minutu.")
        self.btnExe.clicked.connect(self.handle_exe)
        layout.addWidget(self.btnExe)

        self.setLayout(layout)

    def get_data(self):
        return {
            "appName": self.field("appName"),
            "appVersion": self.field("appVersion"),
            "appAuthor": self.field("appAuthor"),
            "exePath": self.field("exePath"),
            "dirPath": self.field("dirPath"),
            "installDir": self.field("installDir")
        }

    def handle_iss(self):
        data = self.get_data()
        file_path, _ = QFileDialog.getSaveFileName(self, "Uložit Inno Setup skript", f"{data['appName']}.iss", "Inno Setup Script (*.iss)")
        if file_path:
            template_path = os.path.join(os.path.dirname(__file__), "..", "..", "templates", "base_template.iss")
            try:
                generate_iss(data, file_path, template_path)
                QMessageBox.information(self, "Úspěch", f"Skript byl úspěšně vygenerován do:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Chyba", str(e))

    def handle_exe(self):
        data = self.get_data()
        file_path, _ = QFileDialog.getSaveFileName(self, "Uložit EXE instalátor", f"{data['appName']}_Setup.exe", "Spustitelný soubor (*.exe)")
        if file_path:
            self.progress = QProgressDialog("Sestavuji instalátor, prosím čekejte...", None, 0, 0, self)
            self.progress.setWindowTitle("Pracuji...")
            self.progress.setWindowModality(Qt.WindowModality.WindowModal)
            self.progress.setAccessibleName("Probíhá sestavování instalátoru, prosím čekejte. Tato operace může trvat až minutu.")
            self.progress.show()
            
            # Použijeme vlákno, aby GUI nezamrzlo
            self.build_thread = BuildThread(data, file_path)
            self.build_thread.finished_signal.connect(self.on_build_finished)
            self.build_thread.start()

    def on_build_finished(self, success, message):
        self.progress.close()
        if success:
            QMessageBox.information(self, "Úspěch", f"{message}\nCesta: {self.build_thread.output_path}")
        else:
            QMessageBox.critical(self, "Chyba při sestavování", message)

    def validatePage(self):
        return True
