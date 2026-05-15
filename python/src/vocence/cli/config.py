"""Config persistence for the CLI.

State is stored at ``~/.vocence/config.json`` with file mode ``0600`` so the
key isn't world-readable on Unix systems. Callers can always override the
saved key by setting ``VOCENCE_API_KEY`` in the environment.

Security posture
----------------
On Unix, both the config directory (``0o700``) and the config file
(``0o600``) are tightened on every write. On read, we refuse to load a
file whose perms are looser than ``0o600`` (other-readable) and instead
print a warning + return ``{}`` — this prevents a CLI from happily
sending requests with a key that any local user could already read.

The user can opt into OS-keyring storage with
``pip install vocence[keyring]`` + ``vocence config set-keyring on``,
which writes the key to the platform-native keychain (macOS Keychain,
Windows Credential Locker, freedesktop Secret Service) instead of a
flat file.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

CONFIG_DIR = Path(os.environ.get("VOCENCE_CONFIG_DIR") or Path.home() / ".vocence")
CONFIG_FILE = CONFIG_DIR / "config.json"
KEYRING_SERVICE = "vocence-cli"
KEYRING_USER = "default"


def _is_world_or_group_readable(path: Path) -> bool:
    """Check if other-readable / group-readable bits are set."""
    if os.name == "nt":  # Windows ACLs — skip POSIX perm check
        return False
    try:
        mode = path.stat().st_mode
    except OSError:
        return False
    return bool(mode & (stat.S_IRGRP | stat.S_IROTH | stat.S_IWGRP | stat.S_IWOTH))


def load() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        return {}
    # Refuse to load a file with loose permissions — fail loud so the
    # user fixes it before a CLI run accidentally exposes the key.
    if _is_world_or_group_readable(CONFIG_FILE):
        sys.stderr.write(
            f"\033[33m[vocence] {CONFIG_FILE} has insecure permissions "
            f"(group/world readable). Run `chmod 600 {CONFIG_FILE}` and "
            f"retry. Refusing to read the file.\033[0m\n"
        )
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text())
    except json.JSONDecodeError:
        return {}


def save(cfg: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    # Tighten the dir too — owner-only.
    try:
        os.chmod(CONFIG_DIR, 0o700)
    except OSError:
        pass
    tmp = CONFIG_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cfg, indent=2))
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass  # best-effort on Windows / unusual file systems
    tmp.replace(CONFIG_FILE)


def _keyring_enabled(cfg: dict[str, Any] | None = None) -> bool:
    cfg = cfg if cfg is not None else load()
    return bool(cfg.get("use_keyring"))


def _keyring_module():
    """Lazy-import ``keyring`` so it stays an optional dependency."""
    try:
        import keyring  # noqa: I001
        return keyring
    except ImportError:
        return None


def get_api_key() -> str | None:
    """Pick up the key from env var first, then keyring (if enabled),
    then the config file."""
    env = os.environ.get("VOCENCE_API_KEY")
    if env and env.strip():
        return env.strip()
    cfg = load()
    if _keyring_enabled(cfg):
        kr = _keyring_module()
        if kr is not None:
            try:
                val = kr.get_password(KEYRING_SERVICE, KEYRING_USER)
            except Exception:
                val = None
            if val:
                return val.strip()
    return (cfg.get("api_key") or "").strip() or None


def set_api_key(key: str) -> None:
    cfg = load()
    if _keyring_enabled(cfg):
        kr = _keyring_module()
        if kr is None:
            sys.stderr.write(
                "[vocence] keyring storage is enabled but the `keyring` "
                "package is not installed. Falling back to the config file.\n"
            )
        else:
            try:
                kr.set_password(KEYRING_SERVICE, KEYRING_USER, key.strip())
                # Wipe any stale plaintext key from the config file so we
                # never silently keep two copies.
                cfg.pop("api_key", None)
                save(cfg)
                return
            except Exception as e:
                sys.stderr.write(f"[vocence] keyring write failed: {e}. Falling back to file.\n")
    cfg["api_key"] = key.strip()
    save(cfg)


def set_keyring_enabled(on: bool) -> None:
    cfg = load()
    cfg["use_keyring"] = bool(on)
    save(cfg)


def clear_keyring_entry() -> None:
    """Remove the key from the OS keychain (no-op if missing)."""
    kr = _keyring_module()
    if kr is None:
        return
    try:
        kr.delete_password(KEYRING_SERVICE, KEYRING_USER)
    except Exception:
        pass


def get_base_url() -> str | None:
    env = os.environ.get("VOCENCE_BASE_URL")
    if env and env.strip():
        return env.strip()
    return (load().get("base_url") or "").strip() or None


def set_base_url(url: str | None) -> None:
    cfg = load()
    if url is None:
        cfg.pop("base_url", None)
    else:
        cfg["base_url"] = url.strip()
    save(cfg)


def mask(secret: str) -> str:
    """Render a key in ``voc_live_XXXX…XXXX`` form for safe display."""
    s = secret.strip()
    if len(s) <= 12:
        return "*" * len(s)
    return f"{s[:12]}…{s[-4:]}"
