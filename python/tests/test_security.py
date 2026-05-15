"""Security-focused unit tests.

Cover the things a future contributor might accidentally regress:
- ``repr(client)`` never leaks the full key
- redact helper handles edge cases (None, short input, already-bearer-prefixed)
- The CLI config refuses to load a world-readable file
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from vocence import AsyncVocence, Vocence
from vocence._http import redact_key
from vocence.cli import config

from .conftest import API_KEY, BASE_URL

# ----- redaction -------------------------------------------------------


def test_redact_short_input() -> None:
    assert redact_key("short") == "*" * 5
    assert redact_key("") == "(unset)"
    assert redact_key(None) == "(unset)"


def test_redact_strips_bearer_prefix() -> None:
    out = redact_key("Bearer voc_live_AAAAAAAAAAAA1234")
    # First 12 chars are the prefix; last 4 are kept.
    assert out.startswith("voc_live_AAA")
    assert out.endswith("1234")
    assert "…" in out
    # Never reveals the full secret regardless of length.
    assert "voc_live_AAAAAAAAAAAA1234" not in out


def test_client_repr_does_not_leak_key() -> None:
    client = Vocence(api_key=API_KEY, base_url=BASE_URL)
    r = repr(client)
    assert API_KEY not in r
    # First 12 chars of the key (the "voc_live_" prefix + 3 entropy chars)
    # may appear, but the rest of the secret never should.
    assert "0000000000000000" not in r
    assert "…" in r
    client.close()


def test_async_client_repr_does_not_leak_key() -> None:
    client = AsyncVocence(api_key=API_KEY, base_url=BASE_URL)
    r = repr(client)
    assert API_KEY not in r
    assert "0000000000000000" not in r


def test_http_layer_repr_does_not_leak_key() -> None:
    client = Vocence(api_key=API_KEY, base_url=BASE_URL)
    assert API_KEY not in repr(client._http)
    client.close()


# ----- config file perms ----------------------------------------------


@pytest.mark.skipif(os.name == "nt", reason="POSIX perm test")
def test_cli_config_refuses_world_readable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A 644 config file (world-readable) must be rejected — we don't
    want to silently pick up a key from a file other local users can read.
    """
    cfg_dir = tmp_path / ".vocence"
    cfg_dir.mkdir()
    cfg_file = cfg_dir / "config.json"
    cfg_file.write_text(json.dumps({"api_key": "voc_live_sensitive_secret_xxxxxxxxxx"}))
    os.chmod(cfg_file, 0o644)  # world-readable on purpose

    monkeypatch.setattr(config, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(config, "CONFIG_FILE", cfg_file)
    # The env var must also be unset for this test to be meaningful.
    monkeypatch.delenv("VOCENCE_API_KEY", raising=False)

    captured: list[str] = []
    monkeypatch.setattr(sys.stderr, "write", lambda s: captured.append(s) or len(s))

    loaded = config.load()
    assert loaded == {}  # refused
    assert any("insecure permissions" in line for line in captured)


def test_cli_config_save_sets_tight_perms(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg_dir = tmp_path / ".vocence"
    cfg_file = cfg_dir / "config.json"
    monkeypatch.setattr(config, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(config, "CONFIG_FILE", cfg_file)
    config.save({"api_key": "voc_live_xxx"})
    if os.name != "nt":
        assert (cfg_file.stat().st_mode & 0o777) == 0o600
        assert (cfg_dir.stat().st_mode & 0o777) == 0o700


def test_get_api_key_prefers_env_over_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg_dir = tmp_path / ".vocence"
    cfg_dir.mkdir(mode=0o700)
    cfg_file = cfg_dir / "config.json"
    cfg_file.write_text(json.dumps({"api_key": "voc_live_from_file"}))
    os.chmod(cfg_file, 0o600)
    monkeypatch.setattr(config, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(config, "CONFIG_FILE", cfg_file)
    monkeypatch.setenv("VOCENCE_API_KEY", "voc_live_from_env")
    assert config.get_api_key() == "voc_live_from_env"
