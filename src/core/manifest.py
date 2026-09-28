"""Instalační manifest – bezpečné odinstalování.

Manifest eviduje POUZE soubory/adresáře nainstalované touto instalací.
Odinstalátor maže jen položky z manifestu, nikdy cizí soubory.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any


MANIFEST_FILENAME = "install_manifest.json"
CONFIG_FILENAME = "install_config.json"

# Ochrana proti mazání kořene
PROTECTED_DIRS = [
    os.path.abspath(os.environ.get("SystemRoot", r"C:\Windows")),
    os.path.abspath(os.environ.get("SystemRoot", r"C:\Windows") + r"\System32"),
    os.path.abspath("C:\\"),
    os.path.abspath("C:/"),
]


def is_protected_dir(path: str) -> bool:
    """Vrátí True pokud je cesta chráněná (kořen, Windows)."""
    try:
        p = os.path.abspath(path).rstrip(os.sep).lower()
        for prot in PROTECTED_DIRS:
            pp = os.path.abspath(prot).rstrip(os.sep).lower()
            if p == pp:
                return True
        if len(p) <= 3:  # např. "c:" nebo "c:\\"
            return True
    except Exception:
        return True
    return False


@dataclass
class InstallationManifest:
    appName: str
    safeName: str
    version: str
    installDir: str
    installedAt: str  # ISO8601
    files: List[str] = field(default_factory=list)  # relativní vůči installDir
    dirs: List[str] = field(default_factory=list)   # relativní, seřazené od nejhlubších
    shortcuts: List[Dict[str, str]] = field(default_factory=list)  # {path, scope}
    status: str = "success"  # success | partial | failed
    installerVersion: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "InstallationManifest":
        return InstallationManifest(
            appName=d.get("appName", ""),
            safeName=d.get("safeName", ""),
            version=d.get("version", ""),
            installDir=d.get("installDir", ""),
            installedAt=d.get("installedAt", ""),
            files=list(d.get("files", [])),
            dirs=list(d.get("dirs", [])),
            shortcuts=list(d.get("shortcuts", [])),
            status=d.get("status", "success"),
            installerVersion=d.get("installerVersion", ""),
        )


def collect_payload_manifest(payload_dir: str) -> tuple[List[str], List[str]]:
    """Projít payload a vrátit (files, dirs) relativně."""
    files: List[str] = []
    dirs: List[str] = []
    if not os.path.isdir(payload_dir):
        return files, dirs
    for root, dirnames, filenames in os.walk(payload_dir):
        rel_root = os.path.relpath(root, payload_dir)
        if rel_root == ".":
            rel_root = ""
        for dn in dirnames:
            rel = os.path.join(rel_root, dn) if rel_root else dn
            dirs.append(rel)
        for fn in filenames:
            rel = os.path.join(rel_root, fn) if rel_root else fn
            files.append(rel)
    dirs.sort(key=lambda p: p.count(os.sep), reverse=True)
    files.sort()
    return files, dirs


def build_manifest_from_payload(
    payload_dir: str,
    runtime_config: Dict[str, Any],
    install_dir: str,
    status: str = "success",
    shortcuts: Optional[List[Dict[str, str]]] = None,
) -> InstallationManifest:
    files, dirs = collect_payload_manifest(payload_dir)
    now = datetime.now(timezone.utc).isoformat()
    return InstallationManifest(
        appName=runtime_config.get("appName", ""),
        safeName=runtime_config.get("safeName", ""),
        version=runtime_config.get("appVersion", ""),
        installDir=os.path.abspath(install_dir),
        installedAt=now,
        files=files,
        dirs=dirs,
        shortcuts=shortcuts or [],
        status=status,
        installerVersion=runtime_config.get("installerVersion", ""),
    )


def _parse_version_tuple(version: str) -> tuple[int, int, int]:
    """Parsuje '1.2.3', '1.2', '1.2.3-xyz' na (major, minor, patch). Nečíselné → 0."""
    import re as _re

    s = str(version or "").strip()
    m = _re.match(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?", s)
    if not m:
        return (0, 0, 0)
    try:
        maj = int(m.group(1) or 0)
        min_ = int(m.group(2) or 0)
        pat = int(m.group(3) or 0)
    except Exception:
        return (0, 0, 0)
    return (maj, min_, pat)


def compare_versions(old: str, new: str) -> int:
    """Porovná dvě verze. Vrátí -1 (new < old), 0 (shodné), 1 (new > old)."""
    o = _parse_version_tuple(old)
    n = _parse_version_tuple(new)
    if n < o:
        return -1
    if n > o:
        return 1
    return 0


def diff_payload(
    old_files: list[str] | None,
    new_files: list[str] | None,
    old_dirs: list[str] | None = None,
    new_dirs: list[str] | None = None,
) -> dict[str, list[str]]:
    """Vrátí diff payloadu: added / removed / kept (+ dirs_added / dirs_removed).

    Porovnání je case-insensitive na Windows (normalizace lower + sep).
    """
    def _norm(items: list[str] | None) -> set[str]:
        out: set[str] = set()
        for it in items or []:
            out.add(os.path.normpath(str(it)).lower())
        return out

    def _original_map(items: list[str] | None) -> dict[str, str]:
        m: dict[str, str] = {}
        for it in items or []:
            m.setdefault(os.path.normpath(str(it)).lower(), str(it))
        return m

    old_n = _norm(old_files)
    new_n = _norm(new_files)
    new_map = _original_map(new_files)
    old_map = _original_map(old_files)
    added = sorted(new_map[k] for k in (new_n - old_n))
    removed = sorted(old_map[k] for k in (old_n - new_n))
    kept = sorted(new_map[k] for k in (new_n & old_n))
    result: dict[str, list[str]] = {"added": added, "removed": removed, "kept": kept}
    if old_dirs is not None or new_dirs is not None:
        old_dn = _norm(old_dirs)
        new_dn = _norm(new_dirs)
        new_dmap = _original_map(new_dirs)
        old_dmap = _original_map(old_dirs)
        result["dirs_added"] = sorted(new_dmap[k] for k in (new_dn - old_dn))
        result["dirs_removed"] = sorted(old_dmap[k] for k in (old_dn - new_dn))
    return result


def write_manifest(manifest: InstallationManifest, dest_dir: str) -> str:
    """Zapíše manifest do dest_dir/install_manifest.json, vrátí cestu."""
    os.makedirs(dest_dir, exist_ok=True)
    path = os.path.join(dest_dir, MANIFEST_FILENAME)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest.to_dict(), f, ensure_ascii=False, indent=2)
    return path


def load_manifest(install_dir: str) -> Optional[InstallationManifest]:
    """Načte manifest z install_dir, nebo None pokud neexistuje/poškozen."""
    path = os.path.join(install_dir, MANIFEST_FILENAME)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        return InstallationManifest.from_dict(d)
    except Exception:
        return None


def load_config(install_dir: str) -> Optional[Dict[str, Any]]:
    """Načte install_config.json (runtime config)."""
    path = os.path.join(install_dir, CONFIG_FILENAME)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None
