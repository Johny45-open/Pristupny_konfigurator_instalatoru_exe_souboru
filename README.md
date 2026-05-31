
lang = "cs"

# Přístupný konfigurátor instalátorů (.EXE)

Tento nástroj slouží k vytváření instalátorů pomocí Inno Setup nebo pomocí vlastního nativního řešení v PyQt6 s důrazem na maximální přístupnost pro uživatele čteček obrazovky (NVDA, JAWS).

## Hlavní vlastnosti
- **Přístupné GUI**: Vytvořeno v PyQt6, kde každý prvek má definované `AccessibleName`.
- **Dva režimy výstupu**:
    1. **Nativní EXE instalátor (DOPORUČENO)**: Vytvoří hotový `.exe` soubor přímo v PyQt6. Tento instalátor má absolutní kontrolu nad přístupností, správně oznamuje průběh instalace a má perfektně čitelná okna pro čtečky.
    2. **Inno Setup skript (.iss)**: Generuje skript pro Inno Setup s úpravami pro lepší čtení dialogů (opravený dialog zrušení).
- **Podpora PyInstaller**: Umožňuje snadno zabalit hlavní EXE i celou složku aplikace.

## Požadavky
- Python 3.x
- PyQt6 a PyInstaller (`pip install -r requirements.txt`)

## Použití
1. Spusťte aplikaci pomocí `python src/main.py`.
2. Projděte kroky průvodce.
3. Na poslední stránce zvolte:
    - **Vytvořit přímo EXE instalátor**: Vypadne vám hotový soubor připravený k distribuci.
    - **Generovat .iss skript**: Pokud dáváte přednost Inno Setupu.

## Proč používat Nativní EXE instalátor?
U běžných instalátorů (jako Inno Setup) čtečky často přeskakují důležité pokyny a čtou jen editační pole. Náš nativní instalátor v PyQt6 tyto pokyny čtečce aktivně "vnucuje", takže uživatel se zrakovým postižením vždy přesně ví, co má dělat.
