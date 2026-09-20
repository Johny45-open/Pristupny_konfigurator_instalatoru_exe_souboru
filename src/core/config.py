"""Datové modely + sanitizace BUILD→RUNTIME.

BUILD-TIME data (nikdy nesmí do instalátoru):
  exePath (absolutní zdroj), dirPath (absolutní zdroj), tmp cesty
RUNTIME data (jediné co jde do config.json v EXE):
  appName, appVersion, appAuthor, safeName, exeName, installDir, zástupci
"""
from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass, asdict
from typing import Optional, Literal, Dict, Any


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value).strip().replace(" ", "_")
    return re.sub(r"[-\s]+", "-", value)


@dataclass(frozen=True)
class InstallerConfig:
    """RUNTIME config – jediné co patří do config.json uvnitř instalátoru."""
    appName: str
    appVersion: str  # semver like 1.0.0
    appAuthor: str
    safeName: str  # bez diakritiky, pro složku
    exeName: str  # basename, např. app.exe
    installDir: int  # 0=pf64, 1=pf32
    createDesktopShortcut: bool
    createStartMenuShortcut: bool

    def __post_init__(self):
        if not self.appName or not self.appName.strip():
            raise ValueError("appName nesmí být prázdný")
        if not self.exeName or not self.exeName.strip():
            raise ValueError("exeName nesmí být prázdný")
        if self.installDir not in (0, 1):
            raise ValueError("installDir musí být 0 nebo 1")


@dataclass(frozen=True)
class BuildConfig:
    """BUILD-TIME config – obsahuje absolutní zdrojové cesty, nikdy nejde do EXE."""
    exePath: str  # absolutní zdroj
    dirPath: Optional[str]  # absolutní zdroj nebo None
    outputExePath: str
    installer: InstallerConfig


# --- Sanitizace / konverze -------------------------------------------------

def dict_to_installer_config(data: Dict[str, Any]) -> InstallerConfig:
    """Převede volný wizard dict na validovaný InstallerConfig."""
    app_name = str(data.get("appName", "")).strip()
    app_version = str(data.get("appVersion", "")).strip() or "1.0.0"
    app_author = str(data.get("appAuthor", "")).strip()
    exe_path = str(data.get("exePath", "")).strip()
    if not exe_path:
        raise ValueError("exePath je povinný")
    exe_name = os.path.basename(exe_path)
    # safeName: pokud už existuje v data, použij; jinak slugify
    safe_name = str(data.get("safeName", "")).strip() or slugify(app_name)
    if not safe_name:
        safe_name = slugify(app_name) or "app"
    try:
        install_dir = int(data.get("installDir", 0))
    except Exception:
        install_dir = 0
    if install_dir not in (0, 1):
        install_dir = 0

    return InstallerConfig(
        appName=app_name,
        appVersion=app_version,
        appAuthor=app_author,
        safeName=safe_name,
        exeName=exe_name,
        installDir=install_dir,
        createDesktopShortcut=bool(data.get("createDesktopShortcut", True)),
        createStartMenuShortcut=bool(data.get("createStartMenuShortcut", True)),
    )


def sanitize_runtime_config(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Vrátí RUNTIME dict vhodný k zápisu do config.json uvnitř instalátoru.
    Odstraní absolutní zdrojové cesty (exePath/dirPath) a ponechá jen runtime klíče.
    """
    cfg = dict_to_installer_config(data)
    d = asdict(cfg)
    # Přidáme volitelný installerVersion pro diagnostiku (není PII)
    try:
        from version import __version__  # type: ignore
    except Exception:
        try:
            from src.version import __version__  # type: ignore
        except Exception:
            __version__ = "0.0.0-dev"  # type: ignore
    d["installerVersion"] = __version__  # type: ignore
    # Explicitně NIKDY neukládat exePath/dirPath/output cestu
    return d


def build_config_from_dict(data: Dict[str, Any], output_exe_path: str) -> BuildConfig:
    """Vytvoří BuildConfig z wizard dictu + výstupní cesty."""
    installer = dict_to_installer_config(data)
    exe_path = os.path.abspath(str(data.get("exePath", "")).strip())
    dir_path_raw = data.get("dirPath")
    dir_path = os.path.abspath(str(dir_path_raw).strip()) if dir_path_raw and str(dir_path_raw).strip() else None
    return BuildConfig(
        exePath=exe_path,
        dirPath=dir_path,
        outputExePath=os.path.abspath(output_exe_path),
        installer=installer,
    )
