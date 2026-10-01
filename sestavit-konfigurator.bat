@echo off
REM Sestaveni Pristupneho konfiguratoru instalatoru do EXE s verzi.
REM Pouziti: sestavit-konfigurator.bat [patch ^| minor ^| major ^| no]
REM   bez parametru = no, tj. bez bumpu (respektuje rucni editaci VERSION).
REM Vystup: dist\Konfigurator-vX.Y.Z.exe (prepise stejnojmenny soubor).
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

echo Sestaveni Konfiguratoru...
echo.

REM --- Napoveda ---
if /i "%~1"=="/?" goto :usage
if /i "%~1"=="-h" goto :usage
if /i "%~1"=="--help" goto :usage
goto :bump_parse

:usage
echo Pouziti: sestavit-konfigurator.bat [patch ^| minor ^| major ^| no]
echo   no     - verzi nebumpovat, pouzit presne to, co je v souboru VERSION (vychozi)
echo   patch  - zvysi cislo opravy, napr. 2.3.0 na 2.3.1
echo   minor  - zvysi mensi verzi, napr. 2.3.0 na 2.4.0
echo   major  - zvysi hlavni verzi, napr. 2.3.0 na 3.0.0
echo.
echo Vysledek: dist\Konfigurator-vX.Y.Z.exe
echo Verze je i uvnitr EXE (Vlastnosti souboru - Podrobnosti).
endlocal
exit /b 0

REM --- Parametr bumpu ---
:bump_parse
set "BUMP=no"
if not "%~1"=="" set "BUMP=%~1"
if /i "%BUMP%"=="patch" goto :bump_ok
if /i "%BUMP%"=="minor" goto :bump_ok
if /i "%BUMP%"=="major" goto :bump_ok
if /i "%BUMP%"=="no" goto :bump_ok
echo CHYBA: Neznamy parametr "%~1". Povolené: patch, minor, major, no.
echo Pro napovedu spustte: sestavit-konfigurator.bat --help
echo.
pause
endlocal
exit /b 1

:bump_ok
REM --- Najdi Python (zkus "python", pak "py") ---
set "PYTHON_CMD=python"
%PYTHON_CMD% --version >nul 2>&1
if errorlevel 1 (
  set "PYTHON_CMD=py"
  %PYTHON_CMD% --version >nul 2>&1
  if errorlevel 1 (
    echo CHYBA: Neni nainstalovany Python 3.10 nebo novsi.
    echo Nainstalujte Python z https://www.python.org/downloads/ a zkuste to znovu.
    echo.
    pause
    endlocal
    exit /b 1
  )
)
echo Nalezen Python:
%PYTHON_CMD% --version
echo.

REM --- Kontrola PyInstalleru, pripadne automaticka instalace ---
%PYTHON_CMD% -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
  echo PyInstaller chybi, instaluji automaticky...
  %PYTHON_CMD% -m pip install "pyinstaller>=6.0"
  if errorlevel 1 (
    echo CHYBA: Instalace PyInstalleru selhala.
    echo Zkuste rucne: %PYTHON_CMD% -m pip install "pyinstaller>=6.0"
    echo.
    pause
    endlocal
    exit /b 1
  )
  %PYTHON_CMD% -m PyInstaller --version >nul 2>&1
  if errorlevel 1 (
    echo CHYBA: PyInstaller se nepodarilo zprovoznit ani po instalaci.
    echo.
    pause
    endlocal
    exit /b 1
  )
)
echo PyInstaller je pripraven.
echo.

REM --- Sestaveni pres build.py (ten resi bump i verzi uvnitr EXE) ---
echo Spoustim sestaveni (bump: %BUMP%)...
%PYTHON_CMD% build.py --bump %BUMP%
if errorlevel 1 (
  echo.
  echo CHYBA: Sestaveni selhalo, viz vypis vyse.
  echo.
  pause
  endlocal
  exit /b 1
)
echo.

REM --- Nacti finalni verzi ze souboru VERSION ---
set "APP_VERSION="
for /f "usebackq delims=" %%V in ("%~dp0VERSION") do (
  if not defined APP_VERSION set "APP_VERSION=%%V"
)
if not defined APP_VERSION (
  echo CHYBA: Nepodarilo se precist verzi ze souboru VERSION.
  echo.
  pause
  endlocal
  exit /b 1
)
echo Verze konfiguratoru: %APP_VERSION%
echo.

REM --- Prejmenuj vystup na verzi a prepiste stejnojmenny soubor ---
if not exist "%~dp0dist\Konfigurator.exe" (
  echo CHYBA: Soubor dist\Konfigurator.exe nebyl vytvoren.
  echo Zkontrolujte vypis sestaveni vyse.
  echo.
  pause
  endlocal
  exit /b 1
)
move /Y "%~dp0dist\Konfigurator.exe" "%~dp0dist\Konfigurator-v%APP_VERSION%.exe" >nul
if errorlevel 1 (
  echo CHYBA: Nepodarilo se prejmenovat EXE na verzi %APP_VERSION%.
  echo.
  pause
  endlocal
  exit /b 1
)

echo.
echo HOTOVO: dist\Konfigurator-v%APP_VERSION%.exe
echo Verze je i uvnitr EXE (Pravy klik - Vlastnosti - Podrobnosti).
echo.
pause
endlocal
exit /b 0
