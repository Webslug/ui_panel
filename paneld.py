#!/usr/bin/env python3
"""
paneld.py — Panel Daemon (The Soldier on the Wall)
System tray applet for LXQt/Lubuntu.
  Right-click  → context menu, top-N commands + Refresh + Edit + Quit
  Double-click → opens CommandEditor GUI
Refreshes command list every REFRESH_MS milliseconds via QTimer.

User data lives in ~/.panel/ — multi-user safe, kim-free.
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

MENU_LIMIT       = 10              # Max commands shown in the tray context menu
REFRESH_MS       = 5 * 60 * 1000  # Auto-refresh interval (milliseconds)
DEFAULT_TERMINAL = "qterminal"     # Fallback if prefs.json has no "terminal" key
ICON_COLOR       = "#89b4fa"       # Catppuccin blue — fallback icon fill

TRAY_POLL_INTERVAL = 2             # seconds between tray availability checks
TRAY_POLL_MAX      = 60            # seconds to wait before giving up entirely


# ── Bootstrap ─────────────────────────────────────────────────────────────────

store.bootstrap()   # Ensure ~/.panel/ + defaults exist before anything else


# ── Terminal emulator resolution ──────────────────────────────────────────────

def _resolve_terminal() -> str:
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


# ── Icon ──────────────────────────────────────────────────────────────────────

def _make_icon(color: str = ICON_COLOR) -> QIcon:
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
    return QIcon.fromTheme("utilities-terminal", _make_icon())


# ── Tray availability — poll until ready ──────────────────────────────────────

def _wait_for_tray(app: QApplication) -> bool:
    """
    Qt's isSystemTrayAvailable() can return False even after the X11 tray
    atom is set — the tray host needs a moment to finish registering with Qt.
    Poll here in-process rather than dying immediately.
    Returns True if the tray became available, False if we timed out.
    """
    elapsed = 0
    while not QSystemTrayIcon.isSystemTrayAvailable():
        if elapsed >= TRAY_POLL_MAX:
            return False
        app.processEvents()          # keep Qt alive during the wait
        time.sleep(TRAY_POLL_INTERVAL)
        elapsed += TRAY_POLL_INTERVAL
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
        records = store.get_top_n(MENU_LIMIT)

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
