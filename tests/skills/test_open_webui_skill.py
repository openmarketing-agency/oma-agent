"""The Open WebUI starter is default-only and confines requests to the configured instance."""

import json
from pathlib import Path
import runpy
from unittest.mock import MagicMock

import pytest

from agent.runtime_scope import bind_profile_scope
from tools.skills_sync import sync_skills
from tools.skills_tool import skill_view


@pytest.fixture
def bundled_skill(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    assert "open-webui" in sync_skills(quiet=True)["copied"]
    skill = json.loads(skill_view("open-webui", preprocess=False))
    assert skill["success"], skill
    skill_dir = Path(skill["skill_dir"])
    assert skill_dir == (tmp_path / "skills" / "integrations" / "open-webui").resolve()
    return skill_dir


@pytest.fixture
def client(bundled_skill):
    return runpy.run_path(str(bundled_skill / "scripts" / "openwebui.py"))["call"]


def test_named_profiles_cannot_seed_or_load_open_webui(tmp_path, bundled_skill):
    for name in ("maintenance", "campaign__writer"):
        profile = tmp_path / "profiles" / name
        profile.mkdir(parents=True)
        with bind_profile_scope(profile, hydrate_secrets=False):
            assert "open-webui" not in sync_skills(quiet=True)["copied"]
            assert not json.loads(skill_view("open-webui", preprocess=False))["success"]


def test_saved_endpoint_gets_model_request_and_redirect_is_not_followed(client):
    http = MagicMock()
    reply = http.request.return_value.__enter__.return_value
    reply.status_code = 200
    reply.json.return_value = {"data": [{"id": "test-model"}]}
    base = "https://webui.example/prefix/"
    assert client(http, "models", base, "fixture-token") == reply.json.return_value
    args, kwargs = http.request.call_args
    assert args == ("GET", "https://webui.example/prefix/api/models")
    assert kwargs["headers"] == {"Authorization": "Bearer fixture-token"}
    assert kwargs["allow_redirects"] is False

    http.reset_mock()
    reply.status_code = 302
    reply.headers = {"Location": "https://different.example"}
    with pytest.raises(ValueError, match="HTTP 302"):
        client(http, "models", base, "fixture-token")
    http.request.assert_called_once()


@pytest.mark.parametrize("base,item_id", [
    ("http://webui.example", "valid-id"),
    ("https://webui.example", "../secrets"),
    ("https://fixture@example.com", "valid-id"),
])
def test_invalid_destinations_are_rejected_without_sending_credentials(client, base, item_id):
    http = MagicMock()
    with pytest.raises(ValueError):
        client(http, "knowledge-show", base, "fixture-token", item_id=item_id)
    http.request.assert_not_called()
