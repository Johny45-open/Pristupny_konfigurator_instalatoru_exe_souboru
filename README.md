# Přístupný konfigurátor instalátorů (.EXE)

Tento nástroj slouží k vytváření instalátorů pomocí Inno Setup s důrazem na maximální přístupnost pro uživatele čteček obrazovky (NVDA, JAWS).

## Hlavní vlastnosti
- **Přístupné GUI**: Vytvořeno v PyQt6, kde každý prvek má definované `AccessibleName`. To řeší problém originálního Inno Setup Script Wizardu, kde některá pole postrádají popisky.
- **Vylepšené Inno Setup šablony**: Generované `.iss` soubory obsahují úpravy v sekci `[Messages]`. Konkrétně je upraven dialog pro zrušení instalace (`ExitSetupMessage`), aby čtečka po jeho zobrazení přečetla celou otázku i s instrukcemi, nikoliv jen tlačítka "Ano/Ne".
- **Podpora PyInstaller**: Umožňuje snadno přidat hlavní EXE i celou složku aplikace (vhodné pro konfiguraci `--onedir`).

## Požadavky
- Python 3.x
- PyQt6 (`pip install -r requirements.txt`)
- Inno Setup Compiler (pro výslednou kompilaci `.iss` na `.exe`)

## Použití
1. Spusťte aplikaci pomocí `python src/main.py`.
2. Projděte kroky průvodce (všechny prvky jsou přístupné tabulátorem a mají popisky pro čtečky).
3. Na konci vyberte umístění pro uložení `.iss` skriptu.
4. Vygenerovaný skript otevřete v Inno Setup Compileru a zkompilujte (F9).

## Poznámky k přístupnosti Inno Setupu
V sekci `[Messages]` generovaného skriptu je vložen upravený text pro češtinu, který zajišťuje, že při pokusu o zrušení instalace čtečka přečte:
*"Chcete skutečně přerušit instalaci programu [Název]? Pokud ji nyní ukončíte, program nebude nainstalován. Stiskněte Ano pro ukončení nebo Ne pro pokračování v instalaci."*
