#!/usr/bin/env bash
# install.sh — Panel deploy script
# Installs to /opt/panel (system-wide source of truth).
# Each user gets their own ~/.panel/ data dir on first daemon launch.
# Safe to run from anywhere, including from /opt/panel itself.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/panel"
AUTOSTART_DIR="$HOME/.config/autostart"
DESKTOP_FILE="$AUTOSTART_DIR/panel.desktop"
DAEMON="$INSTALL_DIR/paneld.py"

RED='\033[1;31m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
CYAN='\033[1;36m'
RESET='\033[0m'

echo -e "${CYAN}=== Panel Installer ===${RESET}"

# ── 1. Copy source to /opt/panel (skip if already there) ─────────────────────
if [[ "$SCRIPT_DIR" == "$INSTALL_DIR" ]]; then
    echo -e "${CYAN}  Already running from ${INSTALL_DIR} — skipping copy.${RESET}"
else
    echo -e "${YELLOW}Installing panel source → ${INSTALL_DIR}…${RESET}"
    sudo mkdir -p "$INSTALL_DIR"

    for f in paneld.py store.py gui.py; do
        if [[ -f "$SCRIPT_DIR/$f" ]]; then
            sudo cp "$SCRIPT_DIR/$f" "$INSTALL_DIR/$f"
            echo -e "${GREEN}  Copied $f${RESET}"
        else
            echo -e "${RED}  WARNING: $f not found in $SCRIPT_DIR — skipping.${RESET}"
        fi
    done
fi

# Verify all three required files are present before proceeding
MISSING=()
for f in paneld.py store.py gui.py; do
    [[ -f "$INSTALL_DIR/$f" ]] || MISSING+=("$f")
done

if [[ ${#MISSING[@]} -gt 0 ]]; then
    echo -e "${RED}ERROR: Missing required files in ${INSTALL_DIR}:${RESET}"
    for f in "${MISSING[@]}"; do
        echo -e "${RED}  - $f${RESET}"
    done
    echo -e "${YELLOW}Copy them manually:  sudo cp <source>/<file> ${INSTALL_DIR}/${RESET}"
    exit 1
fi

sudo chmod 755 "$INSTALL_DIR/paneld.py"
echo -e "${GREEN}  Source verified in ${INSTALL_DIR}.${RESET}"

# ── 2. Python deps ────────────────────────────────────────────────────────────
echo -e "${YELLOW}Installing PyQt5…${RESET}"
if command -v apt-get &>/dev/null; then
    sudo apt-get install -y python3-pyqt5 >/dev/null
    echo -e "${GREEN}  PyQt5 installed via apt.${RESET}"
else
    pip3 install --user PyQt5
    echo -e "${GREEN}  PyQt5 installed via pip.${RESET}"
fi

# ── 3. Per-user autostart .desktop entry ──────────────────────────────────────
mkdir -p "$AUTOSTART_DIR"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Panel Daemon
Comment=Quick-command system tray applet
Exec=python3 ${DAEMON}
Icon=utilities-terminal
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
X-LXQt-Autostart=true
EOF

echo -e "${GREEN}  Autostart entry written → ${DESKTOP_FILE}${RESET}"
echo -e "${CYAN}  Re-run install.sh as any other user to wire up their autostart.${RESET}"

# ── 4. Optional: launch now ───────────────────────────────────────────────────
echo
read -rp "Launch panel daemon now? [y/N] " LAUNCH
if [[ "${LAUNCH,,}" == "y" ]]; then
    echo -e "${YELLOW}Starting paneld.py in background…${RESET}"
    nohup python3 "$DAEMON" &>/dev/null &
    echo -e "${GREEN}  PID $! — tray icon should appear shortly.${RESET}"
fi

echo
echo -e "${GREEN}=== Install complete. ===${RESET}"
echo -e "${CYAN}  Each user's data lives in ~/.panel/ and is created automatically on first run.${RESET}"
