import os
import re
import sys


def get_version():
    """Vrátí verzi konfigurátoru z VERSION souboru. Funguje ve vývoji i ve frozen buildu."""
    candidates = []

    # 1. PyInstaller _MEIPASS (frozen)
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        candidates.append(os.path.join(meipass, "VERSION"))

    # 2. Vedle tohoto souboru (src/) a kořen repa
    here = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(here, "VERSION"))
    candidates.append(os.path.join(here, "..", "VERSION"))
    candidates.append(os.path.join(os.path.dirname(here), "VERSION"))

    # 3. Aktuální pracovní adresář (pro py build.py)
    candidates.append(os.path.join(os.getcwd(), "VERSION"))
    candidates.append(os.path.join(os.getcwd(), "src", "VERSION"))

    for p in candidates:
        try:
            p = os.path.abspath(p)
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    v = f.read().strip()
                    if v and re.match(r"^\d+\.\d+\.\d+", v):
                        return v
        except Exception:
            continue

    return "0.0.0-dev"


__version__ = get_version()
