"""Upgrade the shipped OMA persona without replacing user customizations."""

from pathlib import Path

import pytest

from hermes_cli.config import ensure_hermes_home
from hermes_cli.default_soul import is_legacy_template_soul, starter_soul


@pytest.mark.parametrize("customized", [False, True])
def test_upgrades_only_stock_oma_persona(tmp_path, monkeypatch, customized):
    fixture = Path(__file__).parents[1] / "fixtures" / "oma-default-soul-before-paused-create.md"
    existing = fixture.read_text(encoding="utf-8")
    if customized:
        existing += "\nUse British spelling.\n"
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    assert not is_legacy_template_soul(existing, home=tmp_path / "profiles" / "cloned")
    soul_path = tmp_path / "SOUL.md"
    soul_path.write_text(existing, encoding="utf-8")
    ensure_hermes_home()
    expected = existing if customized else starter_soul(tmp_path)
    assert soul_path.read_text(encoding="utf-8") == expected
