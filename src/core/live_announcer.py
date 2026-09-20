"""LiveAnnouncer – throttled oznamování pro NVDA bez krádeže fokusu."""
from __future__ import annotations

import time
from typing import Optional

try:
    from PyQt6.QtGui import QAccessible
    from PyQt6.QtCore import QTimer
    HAS_ACCESSIBLE = True
except Exception:
    HAS_ACCESSIBLE = False


class LiveAnnouncer:
    def __init__(self, target_label=None, throttle_ms: int = 1200):
        self.target_label = target_label
        self.throttle_ms = throttle_ms
        self._last_text: str = ""
        self._last_time: float = 0.0
        self._pending_text: Optional[str] = None
        self._timer = None
        if HAS_ACCESSIBLE and target_label is not None:
            try:
                from PyQt6.QtCore import QTimer as _QTimer
                self._timer = _QTimer(target_label)
                self._timer.setSingleShot(True)
                self._timer.timeout.connect(self._flush_pending)
            except Exception:
                self._timer = None

    def _flush_pending(self):
        if self._pending_text is not None:
            text = self._pending_text
            self._pending_text = None
            self._do_announce(text)

    def _do_announce(self, text: str):
        if self.target_label is None:
            return
        try:
            self.target_label.setAccessibleDescription(text)
            if HAS_ACCESSIBLE:
                try:
                    QAccessible.updateAccessibility(self.target_label, 0, QAccessible.Event.ValueChanged)  # type: ignore
                except Exception:
                    pass
                try:
                    QAccessible.updateAccessibility(self.target_label, 0, QAccessible.Event.Alert)  # type: ignore
                except Exception:
                    pass
        except Exception:
            pass
        self._last_text = text
        self._last_time = time.monotonic()

    def announce(self, text: str, force: bool = False):
        if not text or not text.strip():
            return
        text = text.strip()
        if not force and text == self._last_text:
            return
        now = time.monotonic()
        elapsed_ms = (now - self._last_time) * 1000
        if not force and elapsed_ms < self.throttle_ms:
            self._pending_text = text
            if self._timer is not None and not self._timer.isActive():
                remaining = max(100, int(self.throttle_ms - elapsed_ms))
                try:
                    self._timer.start(remaining)
                except Exception:
                    pass
            return
        self._do_announce(text)

    def reset(self):
        self._last_text = ""
        self._last_time = 0
        self._pending_text = None
        if self._timer is not None:
            try:
                self._timer.stop()
            except Exception:
                pass
