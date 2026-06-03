import sys
import os
import shutil
import json
import subprocess
from PyQt6.QtWidgets import (QApplication, QWizard, QWizardPage, QVBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QHBoxLayout, 
                             QProgressBar, QMessageBox, QCheckBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

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
        """Vytvoří zástupce pomocí PowerShellu."""
        try:
            ps_script = f'$s = (New-Object -ComObject WScript.Shell).CreateShortcut("{shortcut_path}"); $s.TargetPath = "{target_path}"; $s.WorkingDirectory = "{os.path.dirname(target_path)}"; $s.Save()'
            subprocess.run(["powershell", "-Command", ps_script], check=True, capture_output=True)
            return True
        except Exception as e:
            print(f"Chyba při vytváření zástupce: {e}")
            return False

    def run(self):
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
                desktop = os.path.join(os.environ['USERPROFILE'], 'Desktop')
                shortcut_path = os.path.join(desktop, f"{app_name}.lnk")
                self.create_shortcut(target_exe, shortcut_path)

            if self.config.get('createStartMenuShortcut'):
                self.status.emit("Vytvářím zástupce v nabídce Start...")
                start_menu = os.path.join(os.environ['APPDATA'], 'Microsoft', 'Windows', 'Start Menu', 'Programs')
                shortcut_path = os.path.join(start_menu, f"{app_name}.lnk")
                self.create_shortcut(target_exe, shortcut_path)
            
            self.progress.emit(100)
            
            # Uložíme konfiguraci pro odinstalátor
            config_for_uninstaller = os.path.join(self.dest_dir, "install_config.json")
            with open(config_for_uninstaller, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
            self.finished_signal.emit(True, "Instalace byla úspěšně dokončena.")
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
        self.setTitle("Instalace dokončena")
        text = f"Program {config['appName']} byl úspěšně nainstalován. Nyní můžete okno zavřít tlačítkem Dokončit."
        self.setAccessibleName("Dokončeno")
        
        layout = QVBoxLayout()
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.label.setAccessibleName(text)
        layout.addWidget(self.label)
        self.setLayout(layout)

    def initializePage(self):
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
