"""Vocence() without args falls back to the CLI config file.

Precedence: ``api_key=`` > ``VOCENCE_API_KEY`` env > ``~/.vocence/config.json``
> keyring (if enabled) > raise.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vocence import Vocence
from vocence.cli import config as cfg_mod


def test_kwarg_wins_over_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOCENCE_API_KEY", "voc_live_env_zzzzzzzzzzzzzzzzzzzzzzz")
    c = Vocence(api_key="voc_live_kwarg_yyyyyyyyyyyyyyyyyyy", base_url="http://x")
    assert c._http._api_key == "voc_live_kwarg_yyyyyyyyyyyyyyyyyyy"
    c.close()


def test_env_wins_over_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg_dir = tmp_path / ".vocence"
    cfg_dir.mkdir(mode=0o700)
    cfg_file = cfg_dir / "config.json"
    cfg_file.write_text(json.dumps({"api_key": "voc_live_file_xxxxxxxxxxxxxxxxxxx"}))
    import os
    os.chmod(cfg_file, 0o600)
    monkeypatch.setattr(cfg_mod, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(cfg_mod, "CONFIG_FILE", cfg_file)
    monkeypatch.setenv("VOCENCE_API_KEY", "voc_live_env_zzzzzzzzzzzzzzzzzzzzzzz")
    c = Vocence(base_url="http://x")
    assert c._http._api_key == "voc_live_env_zzzzzzzzzzzzzzzzzzzzzzz"
    c.close()


def test_file_used_when_no_env_or_kwarg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg_dir = tmp_path / ".vocence"
    cfg_dir.mkdir(mode=0o700)
    cfg_file = cfg_dir / "config.json"
    cfg_file.write_text(json.dumps({"api_key": "voc_live_file_xxxxxxxxxxxxxxxxxxx"}))
    import os
    os.chmod(cfg_file, 0o600)
    monkeypatch.setattr(cfg_mod, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(cfg_mod, "CONFIG_FILE", cfg_file)
    monkeypatch.delenv("VOCENCE_API_KEY", raising=False)
    c = Vocence(base_url="http://x")
    assert c._http._api_key == "voc_live_file_xxxxxxxxxxxxxxxxxxx"
    c.close()


def test_error_when_nothing_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cfg_mod, "CONFIG_DIR", tmp_path / ".vocence")
    monkeypatch.setattr(cfg_mod, "CONFIG_FILE", tmp_path / ".vocence" / "config.json")
    monkeypatch.delenv("VOCENCE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="vocence login"):
        Vocence(base_url="http://x")


def test_base_url_falls_back_to_cli_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg_dir = tmp_path / ".vocence"
    cfg_dir.mkdir(mode=0o700)
    cfg_file = cfg_dir / "config.json"
    cfg_file.write_text(json.dumps({
        "api_key": "voc_live_xxxxxxxxxxxxxxxxxxxxxxx",
        "base_url": "http://127.0.0.1:8031",
    }))
    import os
    os.chmod(cfg_file, 0o600)
    monkeypatch.setattr(cfg_mod, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(cfg_mod, "CONFIG_FILE", cfg_file)
    monkeypatch.delenv("VOCENCE_API_KEY", raising=False)
    monkeypatch.delenv("VOCENCE_BASE_URL", raising=False)
    c = Vocence()
    assert c._base_url == "http://127.0.0.1:8031"
    c.close()
