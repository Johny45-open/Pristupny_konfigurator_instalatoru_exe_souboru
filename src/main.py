import sys
from PyQt6.QtWidgets import QApplication, QWizard
from ui.wizard_pages import IntroPage, AppInfoPage, FileSelectionPage, InstallationSettingsPage, FinishPage

# Moderní Tmavý Režim (Dark Mode) pro vysokou přístupnost a kontrast
DARK_STYLESHEET = """
QWizard, QWizardPage {
    background-color: #121212;
    color: #ffffff;
}
QLabel {
    color: #ffffff;
    font-size: 14px;
}
QLineEdit {
    padding: 8px;
    border: 1px solid #3d3d3d;
    border-radius: 4px;
    background-color: #1e1e1e;
    color: #ffffff;
    selection-background-color: #0078d7;
}
QLineEdit:focus {
    border: 2px solid #0078d7;
}
QPushButton {
    padding: 8px 16px;
    background-color: #333333;
    border: 1px solid #555555;
    border-radius: 4px;
    min-width: 80px;
    color: #ffffff;
}
QPushButton:hover {
    background-color: #444444;
    border-color: #0078d7;
}
QPushButton:pressed {
    background-color: #222222;
}
QComboBox {
    padding: 5px;
    border: 1px solid #3d3d3d;
    background-color: #1e1e1e;
    color: #ffffff;
}
QComboBox QAbstractItemView {
    background-color: #1e1e1e;
    color: #ffffff;
    selection-background-color: #0078d7;
}
"""

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Přístupný konfigurátor instalátorů")
    
    # Nastavení palety pro tmavý režim (aby i systémové prvky byly tmavé)
    app.setStyleSheet(DARK_STYLESHEET)
    
    wizard = QWizard()
    wizard.setWindowTitle("Přístupný konfigurátor instalátorů - Wizard")
    
    # Použijeme ClassicStyle, který je v tmavém režimu často přehlednější pro čtečky
    wizard.setWizardStyle(QWizard.WizardStyle.ClassicStyle)
    
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
