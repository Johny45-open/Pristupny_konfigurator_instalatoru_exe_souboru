import sys
from PyQt6.QtWidgets import QApplication, QWizard
from ui.wizard_pages import IntroPage, AppInfoPage, FileSelectionPage, InstallationSettingsPage, FinishPage

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
    selection-background-color: #0078d7;
}
QLineEdit:focus {
    border: 2px solid #0078d7;
}
QPushButton {
    padding: 8px 16px;
    background-color: #e1e1e1;
    border: 1px solid #adadad;
    border-radius: 4px;
    min-width: 80px;
    color: black;
}
QPushButton:hover {
    background-color: #e5f1fb;
    border-color: #0078d7;
}
QPushButton:pressed {
    background-color: #cce4f7;
}
QComboBox {
    padding: 5px;
    border: 1px solid #cccccc;
    background-color: white;
    color: black;
}
"""

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Přístupný konfigurátor instalátorů")
    app.setStyleSheet(STYLESHEET)
    
    wizard = QWizard()
    wizard.setWindowTitle("Přístupný konfigurátor instalátorů - Wizard")
    
    # Nastavení moderního stylu wizardu
    wizard.setWizardStyle(QWizard.WizardStyle.ModernStyle)
    
    # Přidání stránek wizardu
    wizard.addPage(IntroPage())
    wizard.addPage(AppInfoPage())
    wizard.addPage(FileSelectionPage())
    wizard.addPage(InstallationSettingsPage())
    wizard.addPage(FinishPage())
    
    wizard.resize(700, 500)
    wizard.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
