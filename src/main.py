import sys
from PyQt6.QtWidgets import QApplication, QWizard, QMessageBox
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

    def closeEvent(self, event):
        if self.can_close():
            event.accept()
        else:
            event.ignore()

    def reject(self):
        if self.can_close():
            super().reject()

    def can_close(self):
        # Najdeme poslední stránku pro kontrolu stavu
        finish_page = None
        for i in self.pageIds():
            page = self.page(i)
            if isinstance(page, FinishPage):
                finish_page = page
                break
        
        # Podmínky pro dotaz na ukončení:
        # 1. Právě probíhá sestavování
        # 2. Uživatel je dále než na úvodní stránce a ještě nemá hotovo
        is_building = finish_page and finish_page.is_building
        is_in_progress = self.currentId() > 0 and not (finish_page and finish_page.is_finished)
        
        if is_building:
            reply = QMessageBox.question(self, "Probíhá sestavování", 
                "Právě probíhá vytváření instalátoru. Pokud aplikaci zavřete, proces bude přerušen.\n\n"
                "Opravdu chcete ukončit aplikaci?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            return reply == QMessageBox.StandardButton.Yes
        elif is_in_progress:
            reply = QMessageBox.question(self, "Ukončit aplikaci?", 
                "Máte rozpracovanou konfiguraci instalátoru. Pokud aplikaci zavřete, veškerá nastavení budou ztracena.\n\n"
                "Opravdu chcete ukončit aplikaci?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            return reply == QMessageBox.StandardButton.Yes
        
        return True

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
