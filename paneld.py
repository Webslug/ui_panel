#!/usr/bin/env python3
"""
paneld.py — Panel Daemon (The Soldier on the Wall)
System tray applet for LXQt/Lubuntu.
  Right-click  → context menu, top-N commands + Refresh + Edit + Quit
  Double-click → opens CommandEditor GUI
Refreshes command list every REFRESH_MS milliseconds via QTimer.

User data lives in ~/.panel/ — multi-user safe, kim-free.
menu_limit is read from the user's own prefs.json so each user controls
their own menu depth without touching shared config.
"""

import sys
import subprocess
import shutil
import os
import time

from PyQt5.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu, QAction, QMessageBox
)
from PyQt5.QtGui  import QIcon, QPixmap, QColor, QPainter
from PyQt5.QtCore import QTimer, Qt

import store
import gui

# ── Tunables — edit these freely ─────────────────────────────────────────────

REFRESH_MS         = 5 * 60 * 1000  # Auto-refresh interval (milliseconds)
DEFAULT_TERMINAL   = "qterminal"     # Fallback if prefs.json has no "terminal" key
ICON_COLOR         = "#89b4fa"       # Catppuccin blue — fallback icon fill

TRAY_POLL_INTERVAL = 0.1             # seconds between each tray availability probe
TRAY_POLL_MAX      = 60              # seconds before giving up entirely


# ── Bootstrap ─────────────────────────────────────────────────────────────────

store.bootstrap()   # Ensure ~/.panel/ + defaults exist before anything else


# ── Terminal emulator resolution ──────────────────────────────────────────────

def _resolve_terminal() -> str:
    """
    Terminal priority:
      1. prefs.json  "terminal" key
      2. DEFAULT_TERMINAL constant
      3. First available candidate from a fallback list
    Raises RuntimeError if nothing is found on PATH.
    """
    prefs     = store.load_prefs()
    preferred = prefs.get("terminal", DEFAULT_TERMINAL)

    if shutil.which(preferred):
        return preferred

    for candidate in ("qterminal", "terminator", "alacritty",
                      "lxterminal", "xterm", "gnome-terminal", "konsole"):
        if shutil.which(candidate):
            return candidate

    raise RuntimeError(
        f"Preferred terminal '{preferred}' not found, and no fallback is installed.\n"
        "Install one:  sudo apt install qterminal"
    )


# ── Menu limit ────────────────────────────────────────────────────────────────

def _resolve_menu_limit() -> int:
    """
    Read menu_limit from the user's own prefs.json at call time.
    Falls back to the store default (10) if the key is absent or non-integer.
    Called fresh on every menu build so a pref edit takes effect without restart.
    """
    prefs = store.load_prefs()
    raw   = prefs.get("menu_limit", store._DEFAULT_PREFS["menu_limit"])
    try:
        limit = int(raw)
        return limit if limit > 0 else store._DEFAULT_PREFS["menu_limit"]
    except (TypeError, ValueError):
        return store._DEFAULT_PREFS["menu_limit"]


# ── Icon ──────────────────────────────────────────────────────────────────────

def _make_icon(color: str = ICON_COLOR) -> QIcon:
    """Render a minimal '>_' rounded-square icon as a QPixmap fallback."""
    px = QPixmap(22, 22)
    px.fill(Qt.transparent)
    painter = QPainter(px)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(2, 2, 18, 18, 4, 4)
    painter.setPen(QColor("#1e1e2e"))
    font = painter.font()
    font.setBold(True)
    font.setPixelSize(11)
    painter.setFont(font)
    painter.drawText(px.rect(), Qt.AlignCenter, ">_")
    painter.end()
    return QIcon(px)


def _tray_icon() -> QIcon:
    """
    Use the system theme icon when available; fall back to our painted square.
    Theme name "utilities-terminal" is standard on FreeDesktop-compliant DEs.
    """
    return QIcon.fromTheme("utilities-terminal", _make_icon())


# ── Tray availability — poll until ready ──────────────────────────────────────

def _wait_for_tray(app: QApplication) -> bool:
    """
    Qt's isSystemTrayAvailable() returns False if the tray host hasn't
    finished registering yet — even when lxqt-panel is already running.
    Poll in small increments, pumping the Qt event loop each tick so the
    application stays responsive.  Returns True when the tray is ready,
    False if TRAY_POLL_MAX seconds pass with no tray in sight.
    """
    deadline = time.monotonic() + TRAY_POLL_MAX
    while not QSystemTrayIcon.isSystemTrayAvailable():
        if time.monotonic() >= deadline:
            return False
        app.processEvents()      # keep Qt alive — never starve the event loop
        time.sleep(TRAY_POLL_INTERVAL)
    return True


# ── Tray application ──────────────────────────────────────────────────────────

class PanelDaemon(QSystemTrayIcon):

    def __init__(self, app: QApplication):
        super().__init__(_tray_icon())
        self.app = app
        self.setToolTip("Panel — Quick Commands")

        self._menu = QMenu()
        self._build_menu()
        self.setContextMenu(self._menu)

        self.activated.connect(self._on_activated)

        self._timer = QTimer()
        self._timer.timeout.connect(self._build_menu)
        self._timer.start(REFRESH_MS)

        self.show()

    # ── Menu ──────────────────────────────────────────────────────────────────

    def _build_menu(self):
        self._menu.clear()
        records = store.get_top_n(_resolve_menu_limit())

        if not records:
            empty = QAction("(no commands — double-click to add)", self._menu)
            empty.setEnabled(False)
            self._menu.addAction(empty)
        else:
            for rec in records:
                label  = rec.get("display", rec.get("full", "???"))
                full   = rec.get("full", "")
                uses   = rec.get("uses", 0)
                action = QAction(label, self._menu)
                action.setToolTip(f"{full}  [{uses} use{'s' if uses != 1 else ''}]")
                action.triggered.connect(lambda checked, cmd=full: self._run(cmd))
                self._menu.addAction(action)

        self._menu.addSeparator()

        act_refresh = QAction("⟳  Refresh Now", self._menu)
        act_refresh.triggered.connect(self._build_menu)
        self._menu.addAction(act_refresh)

        act_edit = QAction("✎  Edit Commands…", self._menu)
        act_edit.triggered.connect(self._open_editor)
        self._menu.addAction(act_edit)

        self._menu.addSeparator()

        act_quit = QAction("✕  Quit", self._menu)
        act_quit.triggered.connect(self.app.quit)
        self._menu.addAction(act_quit)

    # ── Dispatch ──────────────────────────────────────────────────────────────

    def _run(self, full_command: str):
        """
        Resolve the user's preferred terminal from prefs at dispatch time
        (not at startup) so pref changes take effect without a restart.
        Runs:  <terminal> -e <full_command>
        """
        try:
            term = _resolve_terminal()
            env  = {**os.environ, "DISPLAY": os.environ.get("DISPLAY", ":0")}

            subprocess.Popen(
                [term, "-e", full_command],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                close_fds=True,
                env=env,
            )
            store.record_use(full_command)
            self._build_menu()

        except RuntimeError as exc:
            QMessageBox.critical(None, "No Terminal Found", str(exc))
        except Exception as exc:
            QMessageBox.critical(None, "Launch Failed", str(exc))

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self._open_editor()

    def _open_editor(self):
        dlg = gui.CommandEditor()
        dlg.exec_()
        self._build_menu()


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    if not _wait_for_tray(app):
        QMessageBox.critical(
            None, "Panel",
            f"System tray did not become available after {TRAY_POLL_MAX}s.\n"
            "Is lxqt-panel running?"
        )
        sys.exit(1)

    daemon = PanelDaemon(app)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
