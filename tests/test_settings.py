from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

import pytest
import yaml

from copier.errors import MissingSettingsWarning
from copier.settings import Settings


def test_default_settings() -> None:
    settings = Settings()

    assert settings.defaults == {}
    assert settings.trust == set()


def test_settings_from_default_location(settings_path: Path) -> None:
    settings_path.write_text("defaults:\n  foo: bar")

    settings = Settings.from_file()

    assert settings.defaults == {"foo": "bar"}


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-only test")
def test_default_windows_settings_path() -> None:
    settings = Settings()
    assert settings._default_settings_path() == Path(
        os.getenv("USERPROFILE", default=""),
        "AppData",
        "Local",
        "copier",
        "settings.yml",
    )


@pytest.mark.usefixtures("config_path")
def test_settings_from_default_location_dont_exists() -> None:
    settings = Settings.from_file()

    assert settings.defaults == {}


def test_settings_from_env_location(
    settings_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings_path.write_text("defaults:\n  foo: bar")

    settings_from_env_path = tmp_path / "settings.yml"
    settings_from_env_path.write_text("defaults:\n  foo: baz")

    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(settings_from_env_path))

    settings = Settings.from_file()

    assert settings.defaults == {"foo": "baz"}


def test_settings_from_param(
    settings_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings_path.write_text("defaults:\n  foo: bar")

    settings_from_env_path = tmp_path / "settings.yml"
    settings_from_env_path.write_text("defaults:\n  foo: baz")

    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(settings_from_env_path))

    file_path = tmp_path / "file.yml"
    file_path.write_text("defaults:\n  from: file")

    settings = Settings.from_file(file_path)

    assert settings.defaults == {"from": "file"}


def test_settings_defined_but_missing(
    settings_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(settings_path))

    with pytest.warns(MissingSettingsWarning):
        Settings.from_file()


@pytest.mark.parametrize(
    "encoding",
    ["utf-8", "utf-8-sig", "utf-16-le", "utf-16-be"],
)
def test_settings_from_utf_file(
    settings_path: Path, monkeypatch: pytest.MonkeyPatch, encoding: str
) -> None:
    def _encode(data: str) -> bytes:
        if encoding.startswith("utf-16"):
            data = f"\ufeff{data}"
        return data.encode(encoding)

    defaults = {
        "foo": "\u3053\u3093\u306b\u3061\u306f",  # japanese hiragana
        "bar": "\U0001f60e",  # smiling face with sunglasses
    }

    settings_path.write_bytes(
        _encode(yaml.dump({"defaults": defaults}, allow_unicode=True))
    )

    with monkeypatch.context() as m:
        # Override the factor that determines the default encoding when opening files.
        if sys.version_info >= (3, 10):
            m.setattr("io.text_encoding", lambda *_args: "cp932")
        else:
            m.setattr("_bootlocale.getpreferredencoding", lambda *_args: "cp932")

        settings = Settings.from_file()

    assert settings.defaults == defaults


@pytest.mark.parametrize(
    ("repository", "trust", "is_trusted"),
    [
        ("https://github.com/user/repo.git", set(), False),
        (
            "https://github.com/user/repo.git",
            {"https://github.com/user/repo.git"},
            True,
        ),
        ("https://github.com/user/repo", {"https://github.com/user/repo.git"}, False),
        ("https://github.com/user/repo.git", {"https://github.com/user/"}, True),
        ("https://github.com/user/repo.git", {"https://github.com/user/repo"}, False),
        ("https://github.com/user/repo.git", {"https://github.com/user"}, False),
        ("https://github.com/user/repo.git", {"https://github.com/"}, True),
        ("https://github.com/user/repo.git", {"https://github.com"}, False),
        (f"{Path.home()}/template", set(), False),
        (f"{Path.home()}/template", {f"{Path.home()}/template"}, True),
        (f"{Path.home()}/template", {"~/template"}, True),
        (f"{Path.home()}/path/to/template", {"~/path/to/template"}, True),
        (f"{Path.home()}/path/to/template", {"~/path/to/"}, True),
        (f"{Path.home()}/path/to/template", {"~/path/to"}, False),
    ],
)
def test_is_trusted(repository: str, trust: set[str], is_trusted: bool) -> None:
    settings = Settings(trust=trust)

    assert settings.is_trusted(repository) == is_trusted
