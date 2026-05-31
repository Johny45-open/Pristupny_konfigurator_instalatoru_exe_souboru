import sys
from PyQt6.QtWidgets import QApplication, QWizard
from ui.wizard_pages import IntroPage, AppInfoPage, FileSelectionPage, InstallationSettingsPage, FinishPage

class AccessibleWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Přístupný konfigurátor instalátorů - Wizard")
        
        # Použijeme nativní styl systému
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        
        # Ponecháme lokalizaci tlačítek (nezávisí na barvách)
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
