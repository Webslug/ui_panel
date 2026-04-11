#!/usr/bin/env bash
# install.sh — Panel deploy + provisioning script
#
# ┌─ Run as a normal user ────────────────────────────────────────────────────┐
# │  Copies source to /opt/panel (via sudo), installs PyQt5, writes an        │
# │  autostart .desktop entry, provisions ~/.panel/ for the current user,     │
# │  and optionally launches the daemon now.                                   │
# └───────────────────────────────────────────────────────────────────────────┘
# ┌─ Run as root / sudo ──────────────────────────────────────────────────────┐
# │  Does everything above, THEN mass-provisions ~/.panel/ for every human    │
# │  user on the machine using this priority ladder per file:                  │
# │    1. ~/.panel/<file> already exists          → leave it alone (never clobber) │
# │    2. defaults/<username>/<file> exists       → deploy that user's loadout     │
# │    3. defaults/user/<file>       exists       → deploy the shared vanilla      │
# │    4. Nothing found on disk                   → hardcoded emergency inline      │
# └───────────────────────────────────────────────────────────────────────────┘

set -euo pipefail

# ── Constants ─────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/panel"
DEFAULTS_DIR="$INSTALL_DIR/defaults"
VANILLA_DIR="$DEFAULTS_DIR/user"          # shared vanilla fallback loadout
AUTOSTART_DIR="$HOME/.config/autostart"
DESKTOP_FILE="$AUTOSTART_DIR/panel.desktop"
DAEMON="$INSTALL_DIR/paneld.py"

# ── Colours ───────────────────────────────────────────────────────────────────

RED='\033[1;31m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
CYAN='\033[1;36m'
RESET='\033[0m'

# ═════════════════════════════════════════════════════════════════════════════
# PHASE 1 — Install source to /opt/panel
# ═════════════════════════════════════════════════════════════════════════════

echo -e "${CYAN}========================================${RESET}"
echo -e "${CYAN}     Panel — Installer / Provisioner    ${RESET}"
echo -e "${CYAN}========================================${RESET}"
echo

# ── 1a. Copy source files ─────────────────────────────────────────────────────

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

# ── 1b. Verify required files ─────────────────────────────────────────────────

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

# ── 1c. Python deps ───────────────────────────────────────────────────────────

echo -e "${YELLOW}Installing PyQt5…${RESET}"
if command -v apt-get &>/dev/null; then
    sudo apt-get install -y python3-pyqt5 >/dev/null
    echo -e "${GREEN}  PyQt5 installed via apt.${RESET}"
else
    pip3 install --user PyQt5
    echo -e "${GREEN}  PyQt5 installed via pip.${RESET}"
fi

# ── 1d. Per-user autostart .desktop entry ────────────────────────────────────

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

# ═════════════════════════════════════════════════════════════════════════════
# SHARED — provision_file (used by both single-user and mass-provision phases)
#
# Usage: provision_file <dest> <per-user-src> <vanilla-src>
#
# Priority ladder:
#   1. dest already exists           → skip (never clobber existing data)
#   2. per-user-src exists on disk   → copy it  (custom loadout for this user)
#   3. vanilla-src exists on disk    → copy it  (shared default in defaults/user/)
#   4. nothing found                 → print an error, leave dest absent
# ═════════════════════════════════════════════════════════════════════════════

provision_file() {
    local dest="$1"
    local per_user_src="$2"    # defaults/<username>/<file>  — may not exist
    local vanilla_src="$3"     # defaults/user/<file>        — should always exist
    local filename
    filename="$(basename "$dest")"

    if [[ -f "$dest" ]]; then
        echo -e "    ${CYAN}↷  $filename already exists — skipping.${RESET}"
        return
    fi

    if [[ -n "$per_user_src" && -f "$per_user_src" ]]; then
        cp "$per_user_src" "$dest"
        local rel_src
        rel_src="$(realpath --relative-to="$DEFAULTS_DIR" "$per_user_src")"
        echo -e "    ${GREEN}✔  $filename  ←  defaults/${rel_src}  (per-user loadout)${RESET}"
        return
    fi

    if [[ -f "$vanilla_src" ]]; then
        cp "$vanilla_src" "$dest"
        echo -e "    ${YELLOW}✔  $filename  ←  defaults/user/  (vanilla default)${RESET}"
        return
    fi

    echo -e "    ${RED}✘  $filename: no source found — expected ${vanilla_src}${RESET}"
    echo -e "    ${RED}   Create defaults/user/${filename} to resolve this.${RESET}"
}

# ═════════════════════════════════════════════════════════════════════════════
# PHASE 2a — Provision the current user (always runs, regardless of EUID)
# ═════════════════════════════════════════════════════════════════════════════

CURRENT_USER="${SUDO_USER:-$USER}"
CURRENT_HOME="$(eval echo "~$CURRENT_USER")"
CURRENT_PANEL="$CURRENT_HOME/.panel"
CURRENT_DEFAULTS="$DEFAULTS_DIR/$CURRENT_USER"

echo
echo -e "${CYAN}Provisioning ~/.panel/ for ${CURRENT_USER}…${RESET}"

mkdir -p "$CURRENT_PANEL"

if [[ -d "$CURRENT_DEFAULTS" ]]; then
    echo -e "  ${CYAN}★  Per-user defaults found: ${CURRENT_DEFAULTS}${RESET}"
fi

provision_file \
    "$CURRENT_PANEL/commands.json" \
    "$CURRENT_DEFAULTS/commands.json" \
    "$VANILLA_DIR/commands.json"

provision_file \
    "$CURRENT_PANEL/prefs.json" \
    "$CURRENT_DEFAULTS/prefs.json" \
    "$VANILLA_DIR/prefs.json"

# Ensure ownership is correct (matters when install.sh is run via sudo)
chown -R "$CURRENT_USER:$CURRENT_USER" "$CURRENT_PANEL"
echo -e "  ${GREEN}✔  ${CURRENT_PANEL} ready.${RESET}"

# ═════════════════════════════════════════════════════════════════════════════
# PHASE 2b — Mass provisioning (root only)
# Skipped entirely when running as a normal user.
# ═════════════════════════════════════════════════════════════════════════════

if [[ "$EUID" -ne 0 ]]; then
    echo
    echo -e "${CYAN}  (Running as normal user — skipping mass provisioning.)${RESET}"
    echo -e "${CYAN}  Re-run with sudo to provision all users on this machine.${RESET}"
else
    echo
    echo -e "${CYAN}========================================${RESET}"
    echo -e "${CYAN}     Phase 2b — Mass Provisioning       ${RESET}"
    echo -e "${CYAN}========================================${RESET}"
    echo

    # Resolve human users (UID 1000–59999, home under /home/).
    mapfile -t USERS < <(
        awk -F: '($3 >= 1000 && $3 < 60000 && $6 ~ /^\/home\//) { print $1 }' /etc/passwd
    )

    if [[ ${#USERS[@]} -eq 0 ]]; then
        echo -e "${YELLOW}No human users found in /etc/passwd — nothing to provision.${RESET}"
    else
        echo -e "${BLUE}Found ${#USERS[@]} human user(s): ${USERS[*]}${RESET}"
        echo

        for USERNAME in "${USERS[@]}"; do
            HOME_DIR="/home/$USERNAME"
            PANEL_DIR="$HOME_DIR/.panel"
            USER_DEFAULTS="$DEFAULTS_DIR/$USERNAME"

            echo -e "${BLUE}── $USERNAME${RESET}  (${HOME_DIR})"

            if [[ ! -d "$HOME_DIR" ]]; then
                echo -e "    ${RED}✘  Home directory not found — skipping.${RESET}"
                echo
                continue
            fi

            if [[ ! -d "$PANEL_DIR" ]]; then
                mkdir -p "$PANEL_DIR"
                echo -e "    ${GREEN}✔  Created ${PANEL_DIR}${RESET}"
            else
                echo -e "    ${CYAN}↷  ${PANEL_DIR} already exists.${RESET}"
            fi

            if [[ -d "$USER_DEFAULTS" ]]; then
                echo -e "    ${CYAN}★  Per-user defaults found: ${USER_DEFAULTS}${RESET}"
            fi

            provision_file \
                "$PANEL_DIR/commands.json" \
                "$USER_DEFAULTS/commands.json" \
                "$VANILLA_DIR/commands.json"

            provision_file \
                "$PANEL_DIR/prefs.json" \
                "$USER_DEFAULTS/prefs.json" \
                "$VANILLA_DIR/prefs.json"

            chown -R "$USERNAME:$USERNAME" "$PANEL_DIR"
            echo -e "    ${GREEN}✔  Ownership set → ${USERNAME}:${USERNAME}${RESET}"
            echo
        done
    fi

    echo -e "${GREEN}========================================${RESET}"
    echo -e "${GREEN}  Mass provisioning complete.           ${RESET}"
    echo -e "${GREEN}========================================${RESET}"
    echo -e "${CYAN}  Vanilla defaults:     ${VANILLA_DIR}/${RESET}"
    echo -e "${CYAN}  Per-user overrides:   ${DEFAULTS_DIR}/<username>/${RESET}"
    echo -e "${CYAN}  Existing user files are never overwritten.${RESET}"
fi

# ═════════════════════════════════════════════════════════════════════════════
# PHASE 3 — Optional immediate launch
# ═════════════════════════════════════════════════════════════════════════════

echo
read -rp "Launch panel daemon now? [y/N] " LAUNCH
if [[ "${LAUNCH,,}" == "y" ]]; then
    echo -e "${YELLOW}Starting paneld.py in background…${RESET}"
    nohup python3 "$DAEMON" &>/dev/null &
    echo -e "${YELLOW}  PID $! — tray icon should appear shortly.${RESET}"
fi

echo
echo -e "${GREEN}=== Install complete. ===${RESET}"
echo -e "${CYAN}  Each user's data lives in ~/.panel/ — created automatically on first run.${RESET}"
echo -e "${CYAN}  To provision a new user later:  sudo bash ${INSTALL_DIR}/install.sh${RESET}"
