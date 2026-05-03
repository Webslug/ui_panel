#!/usr/bin/env bash
# uninstall.sh — Panel removal script
# Surgically removes every artifact this project ever deployed.
# Safe to run multiple times. Never touches user command/pref data in ~/.panel/.
#
# Removes:
#   /opt/panel/                         (system source files)
#   ~/.config/autostart/panel.desktop   (per-user autostart entry)
#   Any running paneld.py processes     (for all users on this machine)
#
# Does NOT remove:
#   ~/.panel/                           (user data — commands.json, prefs.json)
#   python3-pyqt5                       (system package, may be used by others)

set -euo pipefail

INSTALL_DIR="/opt/panel"
DESKTOP_FILENAME="panel.desktop"

RED='\033[1;31m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
CYAN='\033[1;36m'
RESET='\033[0m'

echo -e "${CYAN}========================================${RESET}"
echo -e "${CYAN}        Panel — Uninstaller             ${RESET}"
echo -e "${CYAN}========================================${RESET}"
echo

# ── 1. Kill all running paneld.py processes ───────────────────────────────────
echo -e "${YELLOW}Stopping any running paneld.py processes…${RESET}"
if pkill -f "paneld.py" 2>/dev/null; then
    echo -e "${GREEN}  ✔  paneld.py processes terminated.${RESET}"
else
    echo -e "${CYAN}  ↷  No running paneld.py found — nothing to kill.${RESET}"
fi

# ── 2. Remove system source files ─────────────────────────────────────────────
if [[ -d "$INSTALL_DIR" ]]; then
    echo -e "${YELLOW}Removing ${INSTALL_DIR}…${RESET}"
    sudo rm -rf "$INSTALL_DIR"
    echo -e "${GREEN}  ✔  ${INSTALL_DIR} removed.${RESET}"
else
    echo -e "${CYAN}  ↷  ${INSTALL_DIR} not found — already clean.${RESET}"
fi

# ── 3. Remove autostart entries for all human users ───────────────────────────
echo -e "${YELLOW}Removing autostart entries…${RESET}"

mapfile -t USERS < <(
    awk -F: '($3 >= 1000 && $3 < 60000 && $6 ~ /^\/home\//) { print $1 }' /etc/passwd
)

# Also check the user running this script (covers cases where home isn't /home/)
CURRENT_USER="$(whoami)"
CURRENT_HOME="$HOME"

_remove_desktop() {
    local home_dir="$1"
    local username="$2"
    local desktop_file="$home_dir/.config/autostart/$DESKTOP_FILENAME"
    if [[ -f "$desktop_file" ]]; then
        rm -f "$desktop_file"
        echo -e "${GREEN}  ✔  Removed autostart for ${username}: ${desktop_file}${RESET}"
    else
        echo -e "${CYAN}  ↷  No autostart entry for ${username} — skipping.${RESET}"
    fi
}

for USERNAME in "${USERS[@]}"; do
    _remove_desktop "/home/$USERNAME" "$USERNAME"
done

# Handle the running user if they live outside /home/ (e.g. root)
if [[ "$CURRENT_HOME" != /home/* ]]; then
    _remove_desktop "$CURRENT_HOME" "$CURRENT_USER"
fi

# ── 4. Summary ────────────────────────────────────────────────────────────────
echo
echo -e "${GREEN}========================================${RESET}"
echo -e "${GREEN}  Uninstall complete.                   ${RESET}"
echo -e "${GREEN}========================================${RESET}"
echo -e "${CYAN}  User data in ~/.panel/ was left untouched.${RESET}"
echo -e "${CYAN}  To also wipe user data, run:${RESET}"
echo -e "${CYAN}    rm -rf ~/.panel/${RESET}"
echo -e "${CYAN}  (or per-user:  sudo rm -rf /home/<username>/.panel/)${RESET}"
echo
echo -e "${YELLOW}  NOTE: python3-pyqt5 was NOT removed (may be used by other apps).${RESET}"
echo -e "${YELLOW}  To remove it:  sudo apt remove python3-pyqt5${RESET}"
