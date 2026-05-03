#!/usr/bin/env bash
# acl_panel.sh — Grant co-owner access to /opt/panel for named users.
# Uses POSIX ACLs (setfacl) — no new groups, no chown changes.
# Run as root or with sudo.

set -euo pipefail

TARGET="/opt/panel"
COOWNERS=("kim" "teacher")

RED='\033[1;31m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
CYAN='\033[1;36m'
RESET='\033[0m'

# ── Guard ─────────────────────────────────────────────────────────────────────

if [[ "$EUID" -ne 0 ]]; then
    echo -e "${RED}ERROR: Run with sudo or as root.${RESET}"
    exit 1
fi

# ── Ensure setfacl is available ───────────────────────────────────────────────

if ! command -v setfacl &>/dev/null; then
    echo -e "${YELLOW}setfacl not found — installing acl package…${RESET}"
    apt-get install -y acl >/dev/null
    echo -e "${GREEN}  acl installed.${RESET}"
fi

echo -e "${CYAN}========================================${RESET}"
echo -e "${CYAN}   Panel — ACL Co-owner Provisioning    ${RESET}"
echo -e "${CYAN}========================================${RESET}"
echo

# ── Apply ACLs ────────────────────────────────────────────────────────────────

for USERNAME in "${COOWNERS[@]}"; do

    # Verify the user actually exists on this machine before touching anything
    if ! id "$USERNAME" &>/dev/null; then
        echo -e "${YELLOW}  ⚠  User '$USERNAME' not found — skipping.${RESET}"
        continue
    fi

    echo -e "${CYAN}── $USERNAME${RESET}"

    # rwx on the directory itself and all existing files/subdirectories
    setfacl -R -m "u:${USERNAME}:rwx" "$TARGET"
    echo -e "${GREEN}  ✔  rwx granted on ${TARGET} (recursive)${RESET}"

    # Default ACL — any new files/folders created under /opt/panel
    # inherit the same rwx for this user automatically
    setfacl -R -d -m "u:${USERNAME}:rwx" "$TARGET"
    echo -e "${GREEN}  ✔  Default ACL set — new files will inherit access${RESET}"

    echo
done

# ── Verify ────────────────────────────────────────────────────────────────────

echo -e "${CYAN}Current ACL on ${TARGET}:${RESET}"
getfacl "$TARGET"

echo -e "${GREEN}========================================${RESET}"
echo -e "${GREEN}  ACL provisioning complete.            ${RESET}"
echo -e "${GREEN}========================================${RESET}"
