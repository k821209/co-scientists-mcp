"""CLI: init / link / auth.

The HTTP call to Firebase is mocked; no actual network IO. The link command
operates on a tmp_path target. The repo_root() helper resolves to the real
checkout since the CLI module lives inside it.
"""
from __future__ import annotations

import json
import pathlib
import tomllib

import pytest

from co_scientist_cli import repo_root
from co_scientist_cli.firebase_auth import SignInError, sign_in_email_password
from co_scientist_cli.init_cmd import do_init
from co_scientist_cli.link_cmd import do_link


# ──────────────────────────────────────────────────────────────────────────────
# Fake HTTP
# ──────────────────────────────────────────────────────────────────────────────


class _FakeResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body
    def json(self):
        return self._body


class FakeHttpPost:
    """Programmable HTTP poster, mimics firebase_auth._real_http_post."""
    def __init__(self):
        self.calls: list[dict] = []
        self.responses: list[tuple[int, dict]] = []

    def expect(self, *, status: int = 200, body: dict | None = None):
        self.responses.append((status, body or {}))

    def __call__(self, url: str, body: dict) -> _FakeResponse:
        self.calls.append({"url": url, "body": body})
        if not self.responses:
            return _FakeResponse(200, {})
        status, b = self.responses.pop(0)
        return _FakeResponse(status, b)


# ──────────────────────────────────────────────────────────────────────────────
# sign_in_email_password
# ──────────────────────────────────────────────────────────────────────────────


def test_sign_in_success():
    fake = FakeHttpPost()
    fake.expect(body={
        "localId": "uid-abc",
        "email": "x@y.com",
        "idToken": "id-tok",
        "refreshToken": "ref-tok",
        "expiresIn": "3600",
    })
    out = sign_in_email_password(
        email="x@y.com", password="pw", web_api_key="key", http_post=fake,
    )
    assert out["localId"] == "uid-abc"
    assert out["refreshToken"] == "ref-tok"
    # Hit the right URL with the right shape
    assert fake.calls[0]["url"].startswith(
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=key"
    )
    assert fake.calls[0]["body"]["returnSecureToken"] is True


def test_sign_in_failure_surfaces_message():
    fake = FakeHttpPost()
    fake.expect(status=400, body={"error": {"message": "INVALID_PASSWORD"}})
    with pytest.raises(SignInError, match="INVALID_PASSWORD"):
        sign_in_email_password(
            email="x@y.com", password="pw", web_api_key="key", http_post=fake,
        )


def test_sign_in_rejects_empty_args():
    with pytest.raises(ValueError):
        sign_in_email_password(email="", password="x", web_api_key="k")


# ──────────────────────────────────────────────────────────────────────────────
# do_init
# ──────────────────────────────────────────────────────────────────────────────


def test_do_init_writes_config(tmp_path):
    fake = FakeHttpPost()
    fake.expect(body={
        "localId": "uid-xyz",
        "email": "a@b.com",
        "refreshToken": "ref-XYZ",
        "expiresIn": "3600",
    })
    config_path = tmp_path / "config.toml"
    result = do_init(
        email="a@b.com", password="pw",
        config_path=config_path, http_post=fake,
    )
    assert result["uid"] == "uid-xyz"
    assert result["config_path"] == str(config_path)
    assert config_path.is_file()

    with open(config_path, "rb") as f:
        cfg = tomllib.load(f)
    # The .firebase-config.json shipped in the repo
    assert cfg["uid"] == "uid-xyz"
    assert cfg["refresh_token"] == "ref-XYZ"
    assert cfg["project_id"] == "co-scientist-5af1a"
    assert cfg["storage_bucket"].endswith(".firebasestorage.app")
    assert cfg["image_gen_mode"] == "disabled"
    assert "generate_image" in cfg["function_urls"]["generate_image"]


def test_do_init_passes_through_image_gen_mode(tmp_path):
    fake = FakeHttpPost()
    fake.expect(body={"localId": "u", "email": "e", "refreshToken": "r", "expiresIn": "3600"})
    config_path = tmp_path / "config.toml"
    do_init(
        email="e", password="p",
        config_path=config_path, http_post=fake,
        image_gen_mode="local", gemini_api_key="g-key",
    )
    with open(config_path, "rb") as f:
        cfg = tomllib.load(f)
    assert cfg["image_gen_mode"] == "local"
    assert cfg["gemini_api_key"] == "g-key"


def test_do_init_propagates_signin_error(tmp_path):
    fake = FakeHttpPost()
    fake.expect(status=400, body={"error": {"message": "EMAIL_NOT_FOUND"}})
    with pytest.raises(SignInError, match="EMAIL_NOT_FOUND"):
        do_init(
            email="a@b.com", password="pw",
            config_path=tmp_path / "config.toml", http_post=fake,
        )
    assert not (tmp_path / "config.toml").is_file()


def test_do_init_validates_resulting_config(tmp_path):
    """The config we write must satisfy the local MCP's own validator."""
    from co_scientist_local import config as mcp_config

    fake = FakeHttpPost()
    fake.expect(body={"localId": "u", "email": "e", "refreshToken": "r", "expiresIn": "3600"})
    cfg_path = tmp_path / "config.toml"
    do_init(email="e", password="p", config_path=cfg_path, http_post=fake)

    cfg = mcp_config.load_and_validate(cfg_path)
    assert cfg["uid"] == "u"


# ──────────────────────────────────────────────────────────────────────────────
# do_link
# ──────────────────────────────────────────────────────────────────────────────


def test_do_link_writes_all_files(tmp_path):
    target = tmp_path / "my-paper"
    target.mkdir()
    result = do_link(target, paper_slug="my-paper")
    written = set(result["files_written"])
    assert ".mcp.json" in written
    assert ".claude/settings.json" in written
    assert ".co-scientist-paper" in written
    assert "CLAUDE.md" in written

    mcp = json.loads((target / ".mcp.json").read_text())
    assert mcp["mcpServers"]["co_scientist"]["type"] == "stdio"
    assert mcp["mcpServers"]["co_scientist"]["args"] == ["-m", "co_scientist_local"]


def test_do_link_settings_has_absolute_hook_paths(tmp_path):
    target = tmp_path / "p"
    target.mkdir()
    do_link(target)
    settings = json.loads((target / ".claude" / "settings.json").read_text())
    session_start_cmd = settings["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert pathlib.Path(session_start_cmd).is_absolute()
    assert pathlib.Path(session_start_cmd).is_file()
    # All hooks point at real files
    for matcher in settings["hooks"]["PreToolUse"]:
        for h in matcher["hooks"]:
            assert pathlib.Path(h["command"]).is_file()


def test_do_link_permissions_allow_co_scientist_mcp(tmp_path):
    target = tmp_path / "p"
    target.mkdir()
    do_link(target)
    settings = json.loads((target / ".claude" / "settings.json").read_text())
    assert "mcp__co_scientist__*" in settings["permissions"]["allow"]


def test_do_link_creates_skills_symlink(tmp_path):
    target = tmp_path / "p"
    target.mkdir()
    result = do_link(target, skills_strategy="symlink")
    skills_link = target / ".claude" / "skills"
    assert skills_link.is_symlink() or skills_link.is_dir()
    # The template skills are reachable
    assert (skills_link / "paper-writing" / "SKILL.md").is_file()
    assert "symlink" in result["skills_strategy"] or "copy" in result["skills_strategy"]


def test_do_link_copy_strategy(tmp_path):
    target = tmp_path / "p"
    target.mkdir()
    do_link(target, skills_strategy="copy")
    skills_dir = target / ".claude" / "skills"
    # Copy → it's a real directory, not a symlink
    assert skills_dir.is_dir()
    assert not skills_dir.is_symlink()
    assert (skills_dir / "paper-writing" / "SKILL.md").is_file()


def test_do_link_idempotent(tmp_path):
    target = tmp_path / "p"
    target.mkdir()
    do_link(target)
    do_link(target)  # second run should not raise
    assert (target / ".mcp.json").is_file()


def test_do_link_missing_target_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        do_link(tmp_path / "does-not-exist")


# ──────────────────────────────────────────────────────────────────────────────
# repo_root
# ──────────────────────────────────────────────────────────────────────────────


def test_repo_root_finds_firebase_config():
    """repo_root() must resolve to a checkout with the Firebase web config."""
    fb = repo_root() / "apps" / "web" / ".firebase-config.json"
    assert fb.is_file()


# ──────────────────────────────────────────────────────────────────────────────
# auth subcommands (whoami / logout)
# ──────────────────────────────────────────────────────────────────────────────


def test_whoami_prints_uid(tmp_path, monkeypatch, capsys):
    from co_scientist_cli import auth_cmd, init_cmd
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        'uid = "u-test"\n'
        'web_api_key = "k"\n'
        'refresh_token = "r"\n'
        'project_id = "co-scientist-5af1a"\n'
        'storage_bucket = "b"\n'
        'image_gen_mode = "disabled"\n'
    )
    monkeypatch.setattr(init_cmd, "DEFAULT_CONFIG_PATH", config_path)
    monkeypatch.setattr(auth_cmd, "DEFAULT_CONFIG_PATH", config_path)
    rc = auth_cmd.whoami_command(None)
    assert rc == 0
    out = capsys.readouterr().out
    assert "u-test" in out
    assert "co-scientist-5af1a" in out


def test_whoami_no_config(tmp_path, monkeypatch, capsys):
    from co_scientist_cli import auth_cmd, init_cmd
    config_path = tmp_path / "missing.toml"
    monkeypatch.setattr(init_cmd, "DEFAULT_CONFIG_PATH", config_path)
    monkeypatch.setattr(auth_cmd, "DEFAULT_CONFIG_PATH", config_path)
    rc = auth_cmd.whoami_command(None)
    assert rc == 1
    assert "not signed in" in capsys.readouterr().out


def test_logout_removes_config(tmp_path, monkeypatch, capsys):
    from co_scientist_cli import auth_cmd, init_cmd
    config_path = tmp_path / "config.toml"
    config_path.write_text("uid = \"x\"\n")
    monkeypatch.setattr(init_cmd, "DEFAULT_CONFIG_PATH", config_path)
    monkeypatch.setattr(auth_cmd, "DEFAULT_CONFIG_PATH", config_path)
    rc = auth_cmd.logout_command(None)
    assert rc == 0
    assert not config_path.is_file()
    assert "Removed" in capsys.readouterr().out


def test_logout_idempotent(tmp_path, monkeypatch, capsys):
    from co_scientist_cli import auth_cmd, init_cmd
    config_path = tmp_path / "missing.toml"
    monkeypatch.setattr(init_cmd, "DEFAULT_CONFIG_PATH", config_path)
    monkeypatch.setattr(auth_cmd, "DEFAULT_CONFIG_PATH", config_path)
    rc = auth_cmd.logout_command(None)
    assert rc == 0
