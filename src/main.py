import sys
from PyQt6.QtWidgets import QApplication, QWizard, QMessageBox
from PyQt6.QtCore import Qt
from ui.wizard_pages import IntroPage, AppInfoPage, FileSelectionPage, InstallationSettingsPage, FinishPage

try:
    from version import __version__
except ImportError:
    try:
        from src.version import __version__
    except ImportError:
        __version__ = "0.0.0-dev"

class AccessibleWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Přístupný konfigurátor instalátorů v{__version__} - Wizard")
        
        # Použijeme nativní styl systému
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        
        # Ponecháme lokalizaci tlačítek (nezávisí na barvách)
        self.setButtonText(QWizard.WizardButton.NextButton, "Další >")
        self.setButtonText(QWizard.WizardButton.BackButton, "< Zpět")
        self.setButtonText(QWizard.WizardButton.CancelButton, "Zrušit")
        self.setButtonText(QWizard.WizardButton.FinishButton, "Dokončit")

        # Tlačítko "O aplikaci" viditelné na všech stránkách (HelpButton)
        self.setOption(QWizard.WizardOption.HaveHelpButton, True)
        self.setButtonText(QWizard.WizardButton.HelpButton, "O aplikaci")
        self.helpRequested.connect(self.show_about)

    def show_about(self):
        """Zobrazí dialog O aplikaci s verzí konfigurátoru a balené aplikace."""
        # Verze balené aplikace je v poli wizardu (AppInfoPage), pokud je vyplněna
        try:
            app_version = self.field("appVersion")
        except Exception:
            app_version = ""
        if not app_version:
            app_version = "— (nezadáno, výchozí 1.0.0)"

        msg = QMessageBox(self)
        msg.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
        msg.setWindowTitle("O aplikaci")
        msg.setText(
            f"Přístupný konfigurátor instalátorů\n\n"
            f"Verze konfigurátoru: {__version__}\n"
            f"Verze balené aplikace: {app_version}\n\n"
            f"Tento nástroj slouží k vytváření přístupných instalátorů pro Windows.\n"
            f"Vytvořeno s důrazem na přístupnost bez bariér."
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.button(QMessageBox.StandardButton.Ok).setText("OK")
        # Přístupnost
        msg.setAccessibleName(f"O aplikaci. Verze konfigurátoru {__version__}. Verze balené aplikace {app_version}")
        msg.exec()

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
            msg = QMessageBox(self)
            msg.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
            msg.setWindowTitle("Probíhá sestavování")
            msg.setText("Právě probíhá vytváření instalátoru. Pokud aplikaci zavřete, proces bude přerušen.\n\n"
                "Opravdu chcete ukončit aplikaci?")
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg.button(QMessageBox.StandardButton.Yes).setText("Ano")
            msg.button(QMessageBox.StandardButton.No).setText("Ne")
            reply = msg.exec()
            return reply == QMessageBox.StandardButton.Yes
        elif is_in_progress:
            msg = QMessageBox(self)
            msg.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
            msg.setWindowTitle("Ukončit aplikaci?")
            msg.setText("Máte rozpracovanou konfiguraci instalátoru. Pokud aplikaci zavřete, veškerá nastavení budou ztracena.\n\n"
                "Opravdu chcete ukončit aplikaci?")
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg.button(QMessageBox.StandardButton.Yes).setText("Ano")
            msg.button(QMessageBox.StandardButton.No).setText("Ne")
            reply = msg.exec()
            return reply == QMessageBox.StandardButton.Yes
        
        return True

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Přístupný konfigurátor instalátorů")
    app.setApplicationVersion(__version__)
    
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
