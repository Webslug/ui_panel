#!/usr/bin/env bash
set -euo pipefail

# Simple reusable Git push helper.
# Usage:
#   ./git_push_template.sh
#   ./git_push_template.sh "my commit message"
#
# Edit the variables below when reusing this in another folder.

# Absolute path to the local project folder you want to push.
WORK_DIR="${WORK_DIR:-/opt/panel}"
#WORK_DIR="${WORK_DIR:-$HOME/projects/panel}"

# GitHub repo URL for the remote named origin.
REPO_URL="${REPO_URL:-https://github.com/webslug/ui_panel.git}"

# Branch to use locally and remotely.
BRANCH="${BRANCH:-main}"

# Default commit message if you do not pass one as an argument.
MSG="${1:-auto update $(date '+%Y-%m-%d %H:%M:%S')}"

# Move into the project folder.
cd "$WORK_DIR"

# Initialize repo if this folder is not yet a Git repository.
if [ ! -d .git ]; then
    git init
    git branch -M "$BRANCH"
    git remote add origin "$REPO_URL"
fi

# If origin already exists, make sure it points at the repo you want.
if git remote get-url origin >/dev/null 2>&1; then
    git remote set-url origin "$REPO_URL"
else
    git remote add origin "$REPO_URL"
fi

# Stage everything and commit if there is anything new.
git add -A
if git diff --cached --quiet; then
    echo "Nothing new to commit."
else
    git commit -m "$MSG"
fi

# Force-push so the local folder wins.
git push -u origin "$BRANCH" --force
