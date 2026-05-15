"""Config persistence for the CLI.

State is stored at ``~/.vocence/config.json`` with file mode ``0600`` so the
key isn't world-readable on Unix systems. Callers can always override the
saved key by setting ``VOCENCE_API_KEY`` in the environment.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

CONFIG_DIR = Path(os.environ.get("VOCENCE_CONFIG_DIR") or Path.home() / ".vocence")
CONFIG_FILE = CONFIG_DIR / "config.json"


def load() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text())
    except json.JSONDecodeError:
        return {}


def save(cfg: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cfg, indent=2))
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass  # best-effort on Windows / unusual file systems
    tmp.replace(CONFIG_FILE)


def get_api_key() -> str | None:
    """Pick up the key from env var first, then the config file."""
    env = os.environ.get("VOCENCE_API_KEY")
    if env and env.strip():
        return env.strip()
    return (load().get("api_key") or "").strip() or None


def set_api_key(key: str) -> None:
    cfg = load()
    cfg["api_key"] = key.strip()
    save(cfg)


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
