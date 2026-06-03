import sys
import os
import shutil
import json
from PyQt6.QtWidgets import (QApplication, QWizard, QWizardPage, QVBoxLayout, 
                             QLabel, QProgressBar, QMessageBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

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
            # Odstranění zástupců
            app_name = self.config.get('appName', 'Aplikace')
            
            # Plocha
            desktop = os.path.join(os.environ['USERPROFILE'], 'Desktop')
            desktop_shortcut = os.path.join(desktop, f"{app_name}.lnk")
            if os.path.exists(desktop_shortcut):
                self.status.emit("Odstraňuji zástupce na ploše...")
                os.remove(desktop_shortcut)

            # Nabídka Start
            start_menu = os.path.join(os.environ['APPDATA'], 'Microsoft', 'Windows', 'Start Menu', 'Programs')
            start_shortcut = os.path.join(start_menu, f"{app_name}.lnk")
            if os.path.exists(start_shortcut):
                self.status.emit("Odstraňuji zástupce v nabídce Start...")
                os.remove(start_shortcut)

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
