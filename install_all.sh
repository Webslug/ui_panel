#!/usr/bin/env bash
# install_all.sh — Panel mass-provisioning script
# Iterates every human user on the machine and provisions ~/.panel/
# for each one using the following priority ladder:
#
#   1. User already has the file          → leave it alone (never overwrite)
#   2. /opt/panel/defaults/<username>/    → deploy that user's custom loadout
#   3. No defaults subfolder found        → deploy vanilla commands.json / prefs.json
#
# Run as root or with sudo.  Re-running is safe — existing files are never clobbered.

set -euo pipefail

INSTALL_DIR="/opt/panel"
DEFAULTS_DIR="$INSTALL_DIR/defaults"

# ── Vanilla fallback payloads ─────────────────────────────────────────────────

VANILLA_COMMANDS='[
  {
    "display":   "Hello World",
    "full":      "bash -c \"echo Hello World\"",
    "terminal":  false,
    "uses":      0,
    "last_used": null
  }
]'

VANILLA_PREFS='{
  "terminal": "qterminal"
}'

# ── Colours ───────────────────────────────────────────────────────────────────

RED='\033[1;31m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
CYAN='\033[1;36m'
RESET='\033[0m'

# ── Guard: must run as root ───────────────────────────────────────────────────

if [[ "$EUID" -ne 0 ]]; then
    echo -e "${RED}ERROR: Run this script with sudo or as root.${RESET}"
    exit 1
fi

echo -e "${CYAN}========================================${RESET}"
echo -e "${CYAN}     Panel — Mass Provisioning Run      ${RESET}"
echo -e "${CYAN}========================================${RESET}"
echo

# ── Resolve human users ───────────────────────────────────────────────────────
# Strategy: read /etc/passwd, keep only entries whose home dir is under /home
# and whose UID is in the human range (1000–59999).  Excludes root, system
# accounts, and service users (nobody, daemon, www-data, etc.).

mapfile -t USERS < <(
    awk -F: '($3 >= 1000 && $3 < 60000 && $6 ~ /^\/home\//) { print $1 }' /etc/passwd
)

if [[ ${#USERS[@]} -eq 0 ]]; then
    echo -e "${YELLOW}No human users found in /etc/passwd.  Nothing to do.${RESET}"
    exit 0
fi

echo -e "${BLUE}Found ${#USERS[@]} human user(s): ${USERS[*]}${RESET}"
echo

# ── Per-user provisioning loop ────────────────────────────────────────────────

provision_file() {
    # provision_file <dest_path> <source_path_or_"vanilla"> <vanilla_content> <username>
    local dest="$1"
    local source="$2"
    local vanilla="$3"
    local username="$4"
    local filename
    filename="$(basename "$dest")"

    if [[ -f "$dest" ]]; then
        echo -e "    ${CYAN}↷  $filename already exists — skipping.${RESET}"
        return
    fi

    if [[ "$source" != "vanilla" && -f "$source" ]]; then
        cp "$source" "$dest"
        echo -e "    ${GREEN}✔  $filename deployed from defaults/${username}/${RESET}"
    else
        echo "$vanilla" > "$dest"
        echo -e "    ${YELLOW}✔  $filename deployed (vanilla).${RESET}"
    fi
}

for USERNAME in "${USERS[@]}"; do
    HOME_DIR="/home/$USERNAME"
    PANEL_DIR="$HOME_DIR/.panel"
    USER_DEFAULTS="$DEFAULTS_DIR/$USERNAME"

    echo -e "${BLUE}── $USERNAME${RESET}  (${HOME_DIR})"

    # Verify the home directory actually exists on disk
    if [[ ! -d "$HOME_DIR" ]]; then
        echo -e "    ${RED}✘  Home directory not found — skipping.${RESET}"
        echo
        continue
    fi

    # Create ~/.panel/ owned by the user
    if [[ ! -d "$PANEL_DIR" ]]; then
        mkdir -p "$PANEL_DIR"
        echo -e "    ${GREEN}✔  Created ${PANEL_DIR}${RESET}"
    else
        echo -e "    ${CYAN}↷  ${PANEL_DIR} already exists.${RESET}"
    fi

    # Resolve source paths — vanilla keyword triggers inline fallback
    if [[ -d "$USER_DEFAULTS" ]]; then
        echo -e "    ${CYAN}★  Custom defaults found at ${USER_DEFAULTS}${RESET}"
        SRC_COMMANDS="$USER_DEFAULTS/commands.json"
        SRC_PREFS="$USER_DEFAULTS/prefs.json"
    else
        SRC_COMMANDS="vanilla"
        SRC_PREFS="vanilla"
    fi

    provision_file "$PANEL_DIR/commands.json" "$SRC_COMMANDS" "$VANILLA_COMMANDS" "$USERNAME"
    provision_file "$PANEL_DIR/prefs.json"    "$SRC_PREFS"    "$VANILLA_PREFS"    "$USERNAME"

    # Hand ownership back to the user — root created these, user must own them
    chown -R "$USERNAME:$USERNAME" "$PANEL_DIR"
    echo -e "    ${GREEN}✔  Ownership set → ${USERNAME}:${USERNAME}${RESET}"
    echo
done

echo -e "${GREEN}========================================${RESET}"
echo -e "${GREEN}  Provisioning complete.                ${RESET}"
echo -e "${GREEN}========================================${RESET}"
echo -e "${CYAN}  To provision a custom loadout for a user, create:${RESET}"
echo -e "${CYAN}    ${DEFAULTS_DIR}/<username>/commands.json${RESET}"
echo -e "${CYAN}    ${DEFAULTS_DIR}/<username>/prefs.json${RESET}"
echo -e "${CYAN}  then re-run this script.  Existing files are never overwritten.${RESET}"
