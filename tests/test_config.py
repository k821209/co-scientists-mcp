"""Config loader: happy path, missing fields, image_gen_mode validation."""
from __future__ import annotations

import pytest

from co_scientist_local import config as cfg


_MINIMAL_TOML = """\
uid = "u123"
web_api_key = "AIza-fake"
refresh_token = "rt-fake"
project_id = "proj"
storage_bucket = "proj.appspot.com"
image_gen_mode = "disabled"
"""


def _write(tmp_path, body: str):
    p = tmp_path / "config.toml"
    p.write_text(body)
    return p


def test_load_and_validate_minimal(tmp_path):
    p = _write(tmp_path, _MINIMAL_TOML)
    c = cfg.load_and_validate(p)
    assert c["uid"] == "u123"
    assert c["image_gen_mode"] == "disabled"


def test_missing_required_field(tmp_path):
    body = _MINIMAL_TOML.replace('refresh_token = "rt-fake"\n', "")
    p = _write(tmp_path, body)
    with pytest.raises(ValueError, match="refresh_token"):
        cfg.load_and_validate(p)


def test_invalid_image_gen_mode(tmp_path):
    body = _MINIMAL_TOML.replace(
        'image_gen_mode = "disabled"',
        'image_gen_mode = "magic"',
    )
    p = _write(tmp_path, body)
    with pytest.raises(ValueError, match="image_gen_mode"):
        cfg.load_and_validate(p)


def test_local_mode_requires_gemini_key(tmp_path):
    body = _MINIMAL_TOML.replace(
        'image_gen_mode = "disabled"',
        'image_gen_mode = "local"',
    )
    p = _write(tmp_path, body)
    with pytest.raises(ValueError, match="gemini_api_key"):
        cfg.load_and_validate(p)


def test_local_mode_with_gemini_key_ok(tmp_path):
    body = _MINIMAL_TOML.replace(
        'image_gen_mode = "disabled"',
        'image_gen_mode = "local"\ngemini_api_key = "g-fake"',
    )
    p = _write(tmp_path, body)
    c = cfg.load_and_validate(p)
    assert c["image_gen_mode"] == "local"
    assert c["gemini_api_key"] == "g-fake"


def test_cloud_mode_requires_function_url(tmp_path):
    body = _MINIMAL_TOML.replace(
        'image_gen_mode = "disabled"',
        'image_gen_mode = "cloud"',
    )
    p = _write(tmp_path, body)
    with pytest.raises(ValueError, match="function_urls.generate_image"):
        cfg.load_and_validate(p)


def test_cloud_mode_with_url_ok(tmp_path):
    body = _MINIMAL_TOML.replace(
        'image_gen_mode = "disabled"',
        'image_gen_mode = "cloud"\n\n[function_urls]\ngenerate_image = "https://x.cloud.fn"',
    )
    p = _write(tmp_path, body)
    c = cfg.load_and_validate(p)
    assert c["function_urls"]["generate_image"] == "https://x.cloud.fn"


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        cfg.load_and_validate(tmp_path / "does-not-exist.toml")
