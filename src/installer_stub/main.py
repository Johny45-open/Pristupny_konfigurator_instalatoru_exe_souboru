import sys
import os
import shutil
import json
from PyQt6.QtWidgets import (QApplication, QWizard, QWizardPage, QVBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QHBoxLayout, 
                             QProgressBar, QMessageBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

# Moderní Tmavý Režim (Dark Mode) pro instalátor
DARK_STYLESHEET = """
QWizard, QWizardPage, QDialog {
    background-color: #000000;
    color: #ffffff;
}
QLabel {
    color: #ffffff;
    font-size: 15px;
}
QLineEdit {
    padding: 10px;
    border: 2px solid #ffffff;
    border-radius: 4px;
    background-color: #121212;
    color: #ffffff;
}
QProgressBar {
    border: 2px solid #ffffff;
    border-radius: 4px;
    text-align: center;
    background-color: #121212;
    color: #ffffff;
}
QProgressBar::chunk {
    background-color: #0078d7;
}
QPushButton {
    padding: 10px 20px;
    background-color: #222222;
    border: 2px solid #ffffff;
    border-radius: 4px;
    color: #ffffff;
    font-weight: bold;
}
"""

class InstallationThread(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, source_dir, dest_dir, config):
        super().__init__()
        self.source_dir = source_dir
        self.dest_dir = dest_dir
        self.config = config

    def run(self):
        try:
            if not os.path.exists(self.dest_dir):
                os.makedirs(self.dest_dir)
            
            files = os.listdir(self.source_dir)
            total = len(files)
            
            if total == 0:
                self.finished_signal.emit(True, "Instalace byla úspěšně dokončena.")
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
                
                percent = int(((i + 1) / total) * 100)
                self.progress.emit(percent)
                self.status.emit(f"Instaluji: {f}")
            
            self.finished_signal.emit(True, "Instalace byla úspěšně dokončena.")
        except Exception as e:
            self.finished_signal.emit(False, str(e))

class IntroPage(QWizardPage):
    def __init__(self, config):
        super().__init__()
        self.setTitle("Vítejte")
        text = f"Vítá vás instalace programu {config['appName']}. Pokračujte stisknutím tlačítka Další."
        self.setAccessibleName(text)
        
        layout = QVBoxLayout()
        label = QLabel(text)
        label.setWordWrap(True)
        layout.addWidget(label)
        self.setLayout(layout)

class DirectoryPage(QWizardPage):
    def __init__(self, config):
        super().__init__()
        self.setTitle("Cílové umístění")
        text = f"Kam má být produkt {config['appName']} nainstalován?"
        self.setAccessibleName(f"Stránka Cílové umístění. {text}")
        
        layout = QVBoxLayout()
        label = QLabel(text)
        layout.addWidget(label)

        self.pathEdit = QLineEdit()
        
        if config.get('installDir', 0) == 0:
            pf = os.environ.get("ProgramW6432") or os.environ.get("ProgramFiles")
        else:
            pf = os.environ.get("ProgramFiles(x86)") or os.environ.get("ProgramFiles")
            
        default_path = os.path.join(pf, config['appName'])
        self.pathEdit.setText(default_path)
        self.pathEdit.setAccessibleName("Cesta k instalaci")
        layout.addWidget(self.pathEdit)
        self.registerField("installPath", self.pathEdit)
        
        self.setLayout(layout)

class ProgressPage(QWizardPage):
    def __init__(self, config, source_dir):
        super().__init__()
        self.config = config
        self.source_dir = source_dir
        self.setTitle("Průběh")
        self.setAccessibleName("Probíhá instalace, prosím čekejte.")
        
        layout = QVBoxLayout()
        self.statusLabel = QLabel("Připraveno...")
        layout.addWidget(self.statusLabel)
        
        self.progressBar = QProgressBar()
        self.progressBar.setAccessibleName("Průběh v procentech")
        layout.addWidget(self.progressBar)
        self.setLayout(layout)

    def initializePage(self):
        self.wizard().button(QWizard.WizardButton.BackButton).setEnabled(False)
        dest = self.field("installPath")
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
            self.wizard().next()
        else:
            QMessageBox.critical(self, "Chyba", f"Selhalo: {message}")

class FinishPage(QWizardPage):
    def __init__(self, config):
        super().__init__()
        self.setTitle("Dokončeno")
        text = f"Program {config['appName']} byl úspěšně nainstalován. Nyní můžete okno zavřít tlačítkem Dokončit."
        self.setAccessibleName(text)
        
        layout = QVBoxLayout()
        label = QLabel(text)
        label.setWordWrap(True)
        layout.addWidget(label)
        self.setLayout(layout)

class AccessibleWizard(QWizard):
    def __init__(self, config, source_dir):
        super().__init__()
        self.config = config
        self.setWindowTitle(f"Instalace - {config['appName']}")
        self.setStyleSheet(DARK_STYLESHEET)
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        
        # Vynucení češtiny
        self.setButtonText(QWizard.WizardButton.NextButton, "Další >")
        self.setButtonText(QWizard.WizardButton.BackButton, "< Zpět")
        self.setButtonText(QWizard.WizardButton.CancelButton, "Zrušit")
        self.setButtonText(QWizard.WizardButton.FinishButton, "Dokončit")

        self.addPage(IntroPage(config))
        self.addPage(DirectoryPage(config))
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
Applied fuzzy match at line 146-163.