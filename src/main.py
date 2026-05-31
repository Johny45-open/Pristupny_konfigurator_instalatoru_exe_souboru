import sys
from PyQt6.QtWidgets import QApplication, QWizard
from ui.wizard_pages import IntroPage, AppInfoPage, FileSelectionPage, InstallationSettingsPage, FinishPage

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Přístupný konfigurátor instalátorů")
    
    wizard = QWizard()
    wizard.setWindowTitle("Přístupný konfigurátor instalátorů - Wizard")
    
    # Přidání stránek wizardu
    wizard.addPage(IntroPage())
    wizard.addPage(AppInfoPage())
    wizard.addPage(FileSelectionPage())
    wizard.addPage(InstallationSettingsPage())
    wizard.addPage(FinishPage())
    
    wizard.resize(600, 400)
    wizard.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
