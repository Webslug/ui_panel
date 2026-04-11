#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/webslug/ui_panel.git"
BRANCH="main"
MSG="${1:-auto update $(date '+%Y-%m-%d %H:%M:%S')}"

if [ ! -d .git ]; then
    git init
    git branch -M "$BRANCH"
    git remote add origin "$REPO_URL"
fi

git add -A
git commit -m "$MSG" || echo "Nothing new to commit."
git push origin "$BRANCH" --force-with-lease
