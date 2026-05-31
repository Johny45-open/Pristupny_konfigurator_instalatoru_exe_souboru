import sys
import os
import shutil
import json
from PyQt6.QtWidgets import (QApplication, QWizard, QWizardPage, QVBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QHBoxLayout, 
                             QProgressBar, QMessageBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

# Moderní a přístupný styl (QSS)
STYLESHEET = """
QWizard {
    background-color: #f5f5f5;
}
QWizardPage {
    background-color: #f5f5f5;
}
QLabel {
    color: #333333;
    font-size: 14px;
}
QLineEdit {
    padding: 8px;
    border: 1px solid #cccccc;
    border-radius: 4px;
    background-color: white;
    color: black;
}
QProgressBar {
    border: 1px solid #cccccc;
    border-radius: 4px;
    text-align: center;
    background-color: white;
}
QProgressBar::chunk {
    background-color: #0078d7;
}
QPushButton {
    padding: 8px 16px;
    background-color: #e1e1e1;
    border: 1px solid #adadad;
    border-radius: 4px;
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
        self.setTitle(f"Instalace programu {config['appName']}")
        layout = QVBoxLayout()
        text = f"Vítá vás instalace programu {config['appName']} verze {config['appVersion']}.\n\n" \
               f"Tento instalátor je navržen s ohledem na maximální přístupnost.\n" \
               f"Pokračujte stisknutím tlačítka Další."
        label = QLabel(text)
        label.setWordWrap(True)
        label.setAccessibleName(text)
        layout.addWidget(label)
        self.setLayout(layout)

class DirectoryPage(QWizardPage):
    def __init__(self, config):
        super().__init__()
        self.setTitle("Zvolte cílové umístění")
        layout = QVBoxLayout()
        
        desc = f"Kam má být produkt {config['appName']} nainstalován?"
        label = QLabel(desc)
        label.setAccessibleName(desc)
        layout.addWidget(label)

        self.pathEdit = QLineEdit()
        default_path = os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), config['appName'])
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
        self.setTitle("Průběh instalace")
        layout = QVBoxLayout()
        
        self.statusLabel = QLabel("Připraveno k instalaci...")
        self.statusLabel.setAccessibleName("Stav instalace: Připraveno")
        layout.addWidget(self.statusLabel)
        
        self.progressBar = QProgressBar()
        self.progressBar.setAccessibleName("Progress bar průběhu instalace")
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
        self.statusLabel.setAccessibleName(f"Aktuálně: {text}")

    def on_finished(self, success, message):
        if success:
            self.wizard().next()
        else:
            QMessageBox.critical(self, "Chyba", f"Instalace selhala: {message}")

class FinishPage(QWizardPage):
    def __init__(self, config):
        super().__init__()
        self.setTitle("Instalace dokončena")
        layout = QVBoxLayout()
        text = f"Program {config['appName']} byl úspěšně nainstalován.\n" \
               f"Nyní můžete okno zavřít tlačítkem Dokončit."
        label = QLabel(text)
        label.setWordWrap(True)
        label.setAccessibleName(text)
        layout.addWidget(label)
        self.setLayout(layout)

class InstallerWizard(QWizard):
    def __init__(self, config, source_dir):
        super().__init__()
        self.setWindowTitle(f"Instalace - {config['appName']}")
        self.setStyleSheet(STYLESHEET)
        self.addPage(IntroPage(config))
        self.addPage(DirectoryPage(config))
        self.addPage(ProgressPage(config, source_dir))
        self.addPage(FinishPage(config))
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)

def main():
    # Zjištění cesty k dočasné složce (pokud běžíme z PyInstalleru)
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    
    config_path = os.path.join(base_path, "config.json")
    if not os.path.exists(config_path):
        config = {"appName": "Test App", "appVersion": "1.0", "appAuthor": "Test"}
    else:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

    app = QApplication(sys.argv)
    
    source_dir = os.path.join(base_path, "payload")
    if not os.path.exists(source_dir):
        os.makedirs(source_dir)

    wizard = InstallerWizard(config, source_dir)
    wizard.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
