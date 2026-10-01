<div lang="cs">

# Přístupný konfigurátor instalátorů (EXE)

Tento nástroj slouží k vytváření plně přístupných instalátorů pro Windows. Je navržen s důrazem na uživatele čteček obrazovky (NVDA, JAWS) a umožňuje vývojářům snadno zabalit jejich aplikace do profesionálních instalátorů (Inno Setup) nebo přímo do spustitelného EXE souboru.

## Hlavní funkce

*   **Vysoká přístupnost:** Rozhraní konfigurátoru i výsledných instalátorů je navrženo podle standardů přístupnosti. Obsahuje správné sémantické popisky, logické pořadí prvků a nápovědy pro čtečky.
*   **Podpora PyInstaller (onedir):** Automaticky detekuje a správně balí složku `_internal` a další závislosti, čímž předchází chybám typu "Failed to load Python DLL".
*   **Generování Inno Setup skriptů:** Vytvoří optimalizovaný `.iss` skript s vylepšenou přístupností (vlastní hlášení pro čtečky, srozumitelné dialogy).
*   **Přímá tvorba EXE:** Možnost vytvořit hotový instalátor bez nutnosti instalovat Inno Setup Compiler.
*   **Zástupci a odinstalace:** Volitelná tvorba zástupců na ploše a v nabídce Start a automatické generování odinstalátoru.

## Požadavky

*   Windows 10 nebo 11
*   Python 3.10+
*   PyQt6

## Instalace a spuštění

1. Klonujte tento repozitář.
2. Nainstalujte závislosti:
   ```bash
   pip install PyQt6 pyinstaller
   ```
3. Spusťte hlavní aplikaci:
   ```bash
   python src/main.py
   ```

## Sestavení EXE jedním dvojklikem

Ve Windows stačí dvakrát kliknout na `sestavit-konfigurator.bat`:

* Zkontroluje Python a PyInstaller (PyInstaller při chybění **automaticky doinstaluje**).
* Přečte verzi ze souboru `VERSION`, sestaví přes `build.py` a výsledek **přepíše** na `dist\Konfigurator-vX.Y.Z.exe`.
* Verze je **oboje**: v názvu souboru i uvnitř EXE (pravý klik → Vlastnosti → Podrobnosti).

Volitelný parametr určuje bump verze (výchozí `no` – bez bumpu, použije přesně to, co je ve VERSION):

```
sestavit-konfigurator.bat        ... bez bumpu, použije přesně to, co je ve VERSION
sestavit-konfigurator.bat patch  ... 2.3.0 → 2.3.1
sestavit-konfigurator.bat minor  ... 2.3.0 → 2.4.0
sestavit-konfigurator.bat major  ... 2.3.0 → 3.0.0
```

Ručně z příkazové řádky jde totéž přes `python build.py --bump patch|minor|major|no` (výchozí `no`).

## Jak používat

1. **Informace o aplikaci:** Zadejte název (povinné), autora a verzi.
2. **Výběr souborů:** Vyberte hlavní `.exe` soubor vaší aplikace. Pokud používáte režim `--onedir`, konfigurátor automaticky detekuje složku se závislostmi.
3. **Nastavení instalace:** Zvolte cílovou architekturu (64-bit/32-bit) a zda chcete vytvořit zástupce.
4. **Dokončení:** Vyberte, zda chcete vygenerovat `.iss` skript pro Inno Setup, nebo přímo sestavit EXE instalátor.

## Přístupnost pro nevidomé

Aplikace používá `AccessibleName` a `AccessibleDescription` pro všechna pole. Čtečka vás informuje o tom, zda je pole povinné, a poskytuje kontextovou nápovědu. Výsledný instalátor je rovněž upraven tak, aby čtečka oznamovala změny stránek a důležité instrukce, které standardní instalátory často přeskakují.

---
Vytvořeno s důrazem na přístupnost bez bariér.

</div>
