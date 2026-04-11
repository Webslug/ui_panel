"""
store.py — Command Armory
Handles all read/write/sort operations on commands.json and prefs.json.
All user data lives in ~/.panel/ — user-agnostic, XDG-friendly.
No business logic. No UI. Just the ledger.
"""

import json
import os
import tempfile
from datetime import datetime

# ── Constants ────────────────────────────────────────────────────────────────

PANEL_DIR    = os.path.join(os.path.expanduser("~"), ".panel")
STORE_PATH   = os.path.join(PANEL_DIR, "commands.json")
PREFS_PATH   = os.path.join(PANEL_DIR, "prefs.json")
TOP_N        = 10   # Default — overridden by MENU_LIMIT in paneld.py

# ── Default records ───────────────────────────────────────────────────────────

_DEFAULT_COMMANDS = [
    {
        "display":   "Hello World",
        "full":      'bash -c "echo Hello World"',
        "terminal":  False,
        "uses":      0,
        "last_used": None,
    }
]

_DEFAULT_PREFS = {
    "terminal": "qterminal",
    # Future keys: "theme", "icon_color", "lancedb_path", etc.
}


# ── Bootstrap ─────────────────────────────────────────────────────────────────

def bootstrap() -> None:
    """
    Ensure ~/.panel/ exists and seed commands.json / prefs.json
    if either is absent. Called once at daemon startup — idempotent.
    """
    os.makedirs(PANEL_DIR, exist_ok=True)

    if not os.path.exists(STORE_PATH):
        _save_raw(_DEFAULT_COMMANDS)

    if not os.path.exists(PREFS_PATH):
        _save_prefs(_DEFAULT_PREFS)


# ── Internal helpers ─────────────────────────────────────────────────────────

def _shorten(full_command: str) -> str:
    """
    Produce a display-friendly label from a full command string.
    Strips directory paths from the final argument while preserving the verb.

    Examples:
        bash /home/kim/Desktop/webstack.sh  →  bash webstack.sh
        python3 /opt/scripts/runner.py      →  python3 runner.py
        /usr/bin/htop                       →  htop
    """
    parts = full_command.strip().split()
    if not parts:
        return full_command

    shortened = []
    for part in parts:
        if "/" in part:
            shortened.append(os.path.basename(part))
        else:
            shortened.append(part)
    return " ".join(shortened)


def _load_raw() -> list:
    """Return raw list from disk, or empty list if file absent/corrupt."""
    if not os.path.exists(STORE_PATH):
        return []
    try:
        with open(STORE_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_raw(records: list) -> None:
    """Atomic write — swap via temp file so a crash never corrupts the ledger."""
    os.makedirs(PANEL_DIR, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=PANEL_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(records, fh, indent=2, ensure_ascii=False)
        os.replace(tmp_path, STORE_PATH)
    except Exception:
        os.unlink(tmp_path)
        raise


def _sort_key(record: dict):
    """Primary: uses (desc). Tiebreak: last_used timestamp (desc)."""
    ts = record.get("last_used") or "1970-01-01T00:00:00"
    return (-record.get("uses", 0), ts)


# ── Prefs API ─────────────────────────────────────────────────────────────────

def load_prefs() -> dict:
    """Return prefs dict, falling back to defaults for any missing key."""
    if not os.path.exists(PREFS_PATH):
        return dict(_DEFAULT_PREFS)
    try:
        with open(PREFS_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            if not isinstance(data, dict):
                return dict(_DEFAULT_PREFS)
            # Merge: defaults fill in any keys absent from disk
            merged = dict(_DEFAULT_PREFS)
            merged.update(data)
            return merged
    except (json.JSONDecodeError, OSError):
        return dict(_DEFAULT_PREFS)


def _save_prefs(prefs: dict) -> None:
    """Atomic write for prefs.json."""
    os.makedirs(PANEL_DIR, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=PANEL_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(prefs, fh, indent=2, ensure_ascii=False)
        os.replace(tmp_path, PREFS_PATH)
    except Exception:
        os.unlink(tmp_path)
        raise


def save_pref(key: str, value) -> None:
    """Update a single pref key and persist."""
    prefs = load_prefs()
    prefs[key] = value
    _save_prefs(prefs)


# ── Public Commands API ───────────────────────────────────────────────────────

def load_all() -> list:
    """Return all records sorted by frequency, newest-first on ties."""
    records = _load_raw()
    records.sort(key=_sort_key)
    return records


def get_top_n(n: int = TOP_N) -> list:
    """Return the top-N records for menu display."""
    return load_all()[:n]


def record_use(full_command: str) -> None:
    """
    Increment use-count and refresh last_used for a command.
    If the command is not in the store, this is a no-op.
    """
    records = _load_raw()
    for rec in records:
        if rec.get("full") == full_command:
            rec["uses"]      = rec.get("uses", 0) + 1
            rec["last_used"] = datetime.now().isoformat(timespec="seconds")
            break
    _save_raw(records)


def add_command(full_command: str, display: str = None) -> dict:
    """
    Add a new command to the store.
    If it already exists, returns the existing record untouched.
    Returns the (new or existing) record.
    """
    full_command = full_command.strip()
    records = _load_raw()

    for rec in records:
        if rec.get("full") == full_command:
            return rec

    new_record = {
        "display":   display if display else _shorten(full_command),
        "full":      full_command,
        "terminal":  False,
        "uses":      0,
        "last_used": None,
    }
    records.append(new_record)
    _save_raw(records)
    return new_record


def remove_command(full_command: str) -> bool:
    """Remove a command by its full string. Returns True if found and removed."""
    records  = _load_raw()
    filtered = [r for r in records if r.get("full") != full_command]
    if len(filtered) == len(records):
        return False
    _save_raw(filtered)
    return True


def edit_command(old_full: str, new_full: str, new_display: str = None) -> bool:
    """
    Update an existing command's full string and optionally its display label.
    Preserves use-count and last_used. Returns True on success.
    """
    records = _load_raw()
    for rec in records:
        if rec.get("full") == old_full:
            rec["full"]    = new_full.strip()
            rec["display"] = new_display.strip() if new_display else _shorten(new_full)
            _save_raw(records)
            return True
    return False


def update_display(full_command: str, new_display: str) -> bool:
    """Rename only the display label without touching the full command or stats."""
    records = _load_raw()
    for rec in records:
        if rec.get("full") == full_command:
            rec["display"] = new_display.strip()
            _save_raw(records)
            return True
    return False
