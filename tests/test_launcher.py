"""The launcher's token rules.

v0.21.1 audit: the README shows `SURAVIDL_TOKEN=x python -m suravidl_engine.api`
— but `python -m suravidl_engine` (the entry the desktop app and the docs'
dev flow use) ignored the variable and quietly used `~/.suravidl/token`, so a
pinned token did nothing.
"""
from suravidl_engine import __main__ as launcher


def test_the_env_var_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("SURAVIDL_TOKEN", "envtok123")
    monkeypatch.setenv("HOME", str(tmp_path))
    assert launcher.load_or_create_token() == "envtok123"
    # an env var is a decision, not a file: nothing is written
    assert not (tmp_path / ".suravidl" / "token").exists()


def test_an_empty_env_var_is_not_a_token(monkeypatch, tmp_path):
    monkeypatch.setenv("SURAVIDL_TOKEN", "   ")
    monkeypatch.setenv("HOME", str(tmp_path))
    token = launcher.load_or_create_token()
    assert token and token.strip() == token
    assert (tmp_path / ".suravidl" / "token").read_text().strip() == token


def test_without_the_env_var_the_file_is_used_and_stays_private(monkeypatch, tmp_path):
    monkeypatch.delenv("SURAVIDL_TOKEN", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    first = launcher.load_or_create_token()
    token_file = tmp_path / ".suravidl" / "token"
    assert token_file.read_text(encoding="utf-8").strip() == first
    assert oct(token_file.stat().st_mode)[-3:] == "600"
    # stable across restarts: the same token keeps working
    assert launcher.load_or_create_token() == first
