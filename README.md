# Panel — Quick-Command Tray Applet

<p align="center">
  <img src="https://github.com/Webslug/ui_panel/blob/main/preview.jpg?raw=true" alt="Panel preview" width="600"/>
</p>

A lightweight system tray daemon for LXQt / Lubuntu that keeps your most-used shell commands one click away. No desktop clutter, no extra windows — just a tray icon, a right-click menu, and your commands ranked by how often you actually run them.

**License:** GNU General Public License v2.0 — fork it, break it, fix it, ship it.

---

## What It Does

- **Tray icon** lives in your system panel (LXQt, XFCE, or any FreeDesktop-compliant DE).
- **Right-click** opens a ranked menu of your top N commands — sorted by use-count, with recency as the tiebreaker.
- **Click any command** to launch it in your preferred terminal emulator.
- **Double-click the icon** to open the Command Editor — a table UI for adding, removing, and renaming commands without touching any JSON.
- **Auto-refreshes** the menu every 5 minutes so new entries appear without a restart.
- **Per-user data** lives in `~/.panel/` — safe for multi-user machines, no shared state.

---

## Project Structure

```
/opt/panel/
├── paneld.py       — Tray daemon (the soldier on the wall)
├── store.py        — Read/write layer for commands.json and prefs.json
├── gui.py          — Command Editor dialog (PyQt5)
├── install.sh      — Deploy + provisioning script
└── defaults/
    └── user/
        ├── commands.json   — Vanilla default command list
        └── prefs.json      — Vanilla default preferences
```

User data (never touched by updates):

```
~/.panel/
├── commands.json   — Your personal command roster
└── prefs.json      — Your personal preferences
```

---

## Installation

### Quick install (single user)

```bash
git clone https://github.com/Webslug/ui_panel.git
cd ui_panel
bash install.sh
```

The script will:

1. Copy source files to `/opt/panel/`
2. Install `python3-pyqt5` via `apt` (or `pip3` as fallback)
3. Write an autostart `.desktop` entry to `~/.config/autostart/panel.desktop`
4. Provision `~/.panel/` with default config files (skipped if they already exist)
5. Optionally launch the daemon immediately

### Multi-user install (all users on the machine)

```bash
sudo bash install.sh
```

Running as root triggers **mass provisioning**: every human user (UID 1000–59999 with a home under `/home/`) gets their own `~/.panel/` seeded from the defaults. Existing user files are **never overwritten**.

### Per-user custom loadouts (optional)

Drop user-specific default files into `/opt/panel/defaults/<username>/` before running the installer:

```
/opt/panel/defaults/
├── kim/
│   ├── commands.json   ← Kim's custom starter commands
│   └── prefs.json
└── user/
    ├── commands.json   ← Vanilla fallback for everyone else
    └── prefs.json
```

Priority ladder per file: existing file → per-user override → vanilla default → error.

---

## Configuration

All preferences live in **`~/.panel/prefs.json`**. Edit this file directly — changes take effect on the next menu open (no restart required for most settings).

```json
{
  "terminal":   "qterminal",
  "menu_limit": 10
}
```

| Key          | Type    | Default      | Description                                               |
|--------------|---------|--------------|-----------------------------------------------------------|
| `terminal`   | string  | `qterminal`  | Terminal emulator used to launch commands. Any emulator on your `$PATH` works: `alacritty`, `lxterminal`, `xterm`, `gnome-terminal`, `konsole`, etc. |
| `menu_limit` | integer | `10`         | Maximum number of commands shown in the tray menu.        |

If the preferred terminal is not found on `$PATH`, the daemon falls back through a built-in candidate list before raising an error.

---

## Managing Commands

### Via the GUI

Double-click the tray icon (or right-click → **Edit Commands…**) to open the Command Editor.

- **Add** — paste a shell command and an optional display label, then click ＋ Add.
- **Edit** — double-click any cell in the table to edit in place.
- **Terminal checkbox** — tick this for interactive scripts that need their own terminal window (e.g. `kobold.sh`, anything with a TUI).
- **Remove** — select a row and click ✕ Remove Selected.
- **Save** — click ✔ Save Changes to persist all edits.

### Via `~/.panel/commands.json` directly

Each entry follows this schema:

```json
{
  "display":   "kobold",
  "full":      "bash /home/kim/Desktop/kobold.sh",
  "terminal":  true,
  "uses":      10,
  "last_used": "2026-04-10T07:27:46"
}
```

| Field       | Type    | Description                                               |
|-------------|---------|-----------------------------------------------------------|
| `display`   | string  | Label shown in the tray menu                              |
| `full`      | string  | The exact shell command that gets executed                |
| `terminal`  | boolean | `true` = launch in a terminal window                      |
| `uses`      | integer | Auto-incremented on each launch — drives menu rank order  |
| `last_used` | string  | ISO-8601 timestamp — used as tiebreaker in sort           |

---

## Uninstall

```bash
# Remove the daemon and source
sudo rm -rf /opt/panel

# Remove your personal data (optional — your data, your call)
rm -rf ~/.panel

# Remove the autostart entry
rm ~/.config/autostart/panel.desktop
```

---

## Requirements

- Python 3.8+
- PyQt5
- A FreeDesktop-compliant desktop environment (LXQt, XFCE, GNOME, KDE, etc.)
- Any terminal emulator (`qterminal` recommended on Lubuntu)

---

## Lubuntu Repository

Packaging for the official Lubuntu / Ubuntu repositories is on the roadmap. If you want to help package this as a proper `.deb`, contributions are welcome — open an issue or a pull request.

---

## Contributing

1. Fork the repo
2. Make your changes
3. Open a pull request

This project is licensed under the **GNU General Public License v2.0** — you are free to use, modify, and redistribute it under the same terms.
