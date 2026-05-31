import sys
from PyQt6.QtWidgets import QApplication, QWizard
from ui.wizard_pages import IntroPage, AppInfoPage, FileSelectionPage, InstallationSettingsPage, FinishPage

# Moderní Tmavý Režim (Dark Mode) pro vysokou přístupnost a kontrast
DARK_STYLESHEET = """
QWizard, QWizardPage, QDialog {
    background-color: #000000;
    color: #ffffff;
}
QLabel {
    color: #ffffff;
    font-size: 15px;
    background-color: transparent;
}
QLineEdit {
    padding: 10px;
    border: 2px solid #ffffff;
    border-radius: 4px;
    background-color: #121212;
    color: #ffffff;
}
QPushButton {
    padding: 10px 20px;
    background-color: #222222;
    border: 2px solid #ffffff;
    border-radius: 4px;
    color: #ffffff;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #333333;
    border-color: #0078d7;
}
QComboBox {
    padding: 8px;
    border: 2px solid #ffffff;
    background-color: #121212;
    color: #ffffff;
}
"""

class AccessibleWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Přístupný konfigurátor instalátorů - Wizard")
        self.setStyleSheet(DARK_STYLESHEET)
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        
        # Vynucení české lokalizace tlačítek
        self.setButtonText(QWizard.WizardButton.NextButton, "Další >")
        self.setButtonText(QWizard.WizardButton.BackButton, "< Zpět")
        self.setButtonText(QWizard.WizardButton.CancelButton, "Zrušit")
        self.setButtonText(QWizard.WizardButton.FinishButton, "Dokončit")

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Přístupný konfigurátor instalátorů")
    
    wizard = AccessibleWizard()
    
    # Přidání stránek wizardu
    wizard.addPage(IntroPage())
    wizard.addPage(AppInfoPage())
    wizard.addPage(FileSelectionPage())
    wizard.addPage(InstallationSettingsPage())
    wizard.addPage(FinishPage())
    
    wizard.resize(750, 550)
    wizard.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
