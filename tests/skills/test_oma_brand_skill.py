"""OMA brand management is available on demand without creating user data."""

import base64
import json
from pathlib import Path
import runpy
from unittest.mock import MagicMock, Mock

import pytest

from tools.skills_sync import sync_skills
from tools.skills_tool import skill_view


def test_oma_brand_loads_in_a_fresh_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    result = sync_skills(quiet=True)
    assert "oma-brand" in result["copied"]
    loaded = json.loads(skill_view("oma-brand"))
    assert loaded["success"], loaded
    assert loaded["name"] == "oma-brand"
    assert "`oma/brand/config.yaml`" in loaded["content"]
    for reference in ("references/website-integrations.md", "references/visual-references.md",
                      "references/design-system-template.md"):
        assert reference in loaded["linked_files"]["references"]
        assert reference in loaded["content"]
        assert json.loads(skill_view("oma-brand", file_path=reference))["success"]
    assert not (tmp_path / "oma").exists()


@pytest.fixture
def visual_helper(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sync_skills(quiet=True)
    skill = json.loads(skill_view("oma-brand"))
    helper = Path(skill["skill_dir"]) / "scripts" / "visual_reference.py"
    return runpy.run_path(str(helper))


@pytest.fixture
def capture_page(visual_helper):
    return visual_helper["capture_page"]


def test_public_profile_returns_avatar_and_captures_full_page(capture_page, tmp_path):
    url = "https://www.instagram.com/gurkhaweaves/"
    avatar = "https://scontent.cdninstagram.com/example.jpg"
    inspect = Mock(return_value={"url": url, "title": "Gurkha Weaves (@gurkhaweaves)",
                                "body": "Log In\nGurkha Weaves", "images": [avatar], "blocked": False})
    image = b"\x89PNG\r\n\x1a\nexample"
    browser = Mock(side_effect=[{"cssContentSize": {"width": 1280, "height": 2300}},
                                {"data": base64.b64encode(image).decode()}])

    result = capture_page(url, tmp_path, "profile-desktop", js=inspect, cdp=browser)

    assert result["image_candidates"] == [avatar]
    assert result["screenshots"] == [str(tmp_path / "profile-desktop.png")]
    assert Path(result["screenshots"][0]).read_bytes() == image
    assert browser.call_args.kwargs["clip"]["height"] == 2300
    assert browser.call_args.kwargs["captureBeyondViewport"] is True


def test_challenge_does_not_capture_or_return_image_candidates(capture_page, tmp_path):
    url = "https://www.tiktok.com/@unanimousofficial"
    inspect = Mock(return_value={"url": url, "title": "", "body": "Please wait...",
                                "images": ["https://example.com/platform.png"], "blocked": True})
    browser = Mock()

    result = capture_page(url, tmp_path, "tiktok-desktop", js=inspect, cdp=browser)

    assert result["status"] == "blocked"
    assert result["image_candidates"] == result["screenshots"] == []
    browser.assert_not_called()


def test_signup_overlay_retains_public_avatar_without_saving_dialog(capture_page, tmp_path):
    url = "https://www.instagram.com/gurkhaweaves/"
    avatar = "https://scontent.cdninstagram.com/example.jpg"
    inspect = Mock(return_value={"url": url, "title": "Gurkha Weaves", "body": "Sign up",
                                "images": [avatar], "blocked": False, "login_overlay": True})
    browser = Mock()

    result = capture_page(url, tmp_path, "instagram-desktop", js=inspect, cdp=browser)

    assert result["status"] == "login_overlay"
    assert result["image_candidates"] == [avatar]
    assert result["screenshots"] == []
    browser.assert_not_called()


def test_tall_document_is_captured_as_consecutive_sections(capture_page, tmp_path):
    url = "https://unanimousnepal.com/"
    inspect = Mock(return_value={"url": url, "title": "Unanimous", "body": "Shop collections",
                                "images": [], "blocked": False})
    browser = Mock(side_effect=lambda method, **kw: (
        {"cssContentSize": {"width": 1280, "height": 15000}} if method == "Page.getLayoutMetrics"
        else {"data": base64.b64encode(b"\x89PNG\r\n\x1a\nexample").decode()}
    ))

    result = capture_page(url, tmp_path, "home-desktop", js=inspect, cdp=browser)

    assert [Path(path).name for path in result["screenshots"]] == [
        "home-desktop-part-01.png", "home-desktop-part-02.png",
    ]
    segments = [call.kwargs["clip"] for call in browser.call_args_list[1:]]
    assert segments[0]["y"] == 0
    assert segments[1]["y"] == segments[0]["height"]
    assert sum(segment["height"] for segment in segments) == 15000


def test_website_logo_is_extracted_before_generic_preview(capture_page, tmp_path):
    url = "https://brand.example/"
    logo = url + "static/brand.svg"
    preview = url + "seasonal-campaign.jpg"
    png = b"\x89PNG\r\n\x1a\nlogo-png"
    encoded = base64.b64encode(png).decode()
    inspect = Mock(side_effect=[
        {"url": url, "title": "Brand", "body": "Shop collections", "blocked": False,
         "images": [preview], "logos": [{"kind": "structured-logo", "url": logo}]},
        encoded,
    ])
    browser = Mock(return_value={"cssContentSize": {"width": 1200, "height": 900}, "data": encoded})

    result = capture_page(url, tmp_path, "home-desktop", js=inspect, cdp=browser)

    assert result["image_candidates"] == [logo, preview]
    assert result["logo_candidate"] == {
        "file": str(tmp_path / "home-desktop-logo.png"), "kind": "structured-logo", "source_url": logo,
    }
    assert Path(result["logo_candidate"]["file"]).read_bytes() == png
    assert logo in inspect.call_args.args[0]


def test_rendered_inline_logo_is_cropped_when_it_has_no_download_url(capture_page, tmp_path):
    url = "https://brand.example/"
    clip = {"x": 42, "y": 15, "width": 120, "height": 36, "scale": 1}
    inspect = Mock(return_value={"url": url, "title": "Brand", "body": "Shop", "blocked": False,
                                 "images": [], "logos": [{"kind": "site-header", "clip": clip}]})
    png = b"\x89PNG\r\n\x1a\nlogo-crop"
    encoded = base64.b64encode(png).decode()
    browser = Mock(return_value={"cssContentSize": {"width": 1200, "height": 900}, "data": encoded})

    result = capture_page(url, tmp_path, "home-desktop", js=inspect, cdp=browser)

    assert result["logo_candidate"]["source_url"] == url
    assert result["logo_candidate"]["kind"] == "site-header"
    assert Path(result["logo_candidate"]["file"]).read_bytes() == png
    assert browser.call_args_list[0].kwargs["clip"] == clip
    inspect.assert_called_once()


def test_downloadable_logo_is_preferred_to_small_rendered_header_crop(capture_page, tmp_path):
    url = "https://brand.example/"
    logo = url + "brand-logo.png"
    encoded = base64.b64encode(b"\x89PNG\r\n\x1a\noriginal").decode()
    inspect = Mock(side_effect=[
        {"url": url, "title": "Brand", "body": "Shop", "blocked": False, "images": [],
         "logos": [{"kind": "site-header", "clip": {"x": 3, "y": 5, "width": 30, "height": 12, "scale": 1}},
                   {"kind": "logo-metadata", "url": logo}]},
        encoded,
    ])
    browser = Mock(return_value={"cssContentSize": {"width": 1200, "height": 900}, "data": encoded})

    result = capture_page(url, tmp_path, "home-desktop", js=inspect, cdp=browser)

    assert result["logo_candidate"]["source_url"] == logo
    assert browser.call_args_list[0].args == ("Page.getLayoutMetrics",)


def test_capture_inventories_all_asset_kinds_without_duplicate_urls(capture_page, tmp_path):
    url = "https://brand.example/"

    def candidate(kind, name):
        return {"kind": kind, "url": url + name}

    inspect = Mock(side_effect=[
        {"url": url, "title": "Brand", "body": "Shop", "blocked": False, "images": [],
         "logos": [candidate("site-header", "wordmark.png"), candidate("structured-logo", "symbol.png")],
         "assets": [candidate("images", "wordmark.png"), candidate("illustrations", "tree.svg"),
                    candidate("icons", "arrow.svg"), candidate("backgrounds", "paper.png"),
                    candidate("images", "product.png"), candidate("images", "product.png"),
                    {"kind": "images", "url": "data:image/png;base64,example"}]},
        None, None,
    ])
    encoded = base64.b64encode(b"\x89PNG\r\n\x1a\nfixture").decode()
    browser = Mock(return_value={"cssContentSize": {"width": 1200, "height": 900}, "data": encoded})

    result = capture_page(url, tmp_path, "home-desktop", js=inspect, cdp=browser)

    assert result["asset_counts"] == {"logos": 2, "illustrations": 1, "icons": 1, "backgrounds": 1, "images": 1}
    manifest = json.loads(Path(result["asset_inventory"]).read_text())
    assert manifest["source_url"] == url
    assert [asset["url"] for asset in manifest["assets"]["logos"]] == [url + "wordmark.png", url + "symbol.png"]
    assert [asset["url"] for asset in manifest["assets"]["images"]] == [url + "product.png"]
    assert manifest["screenshots"] == result["screenshots"]


def test_stage_assets_only_reads_approved_observed_entries(visual_helper, tmp_path):
    url = "https://brand.example/"
    image = url + "paper.png"
    clip = {"x": 10, "y": 12, "width": 24, "height": 24, "scale": 1}
    page = {"url": url, "title": "Brand", "body": "Shop", "blocked": False, "images": [],
            "assets": [{"kind": "backgrounds", "url": image}, {"kind": "icons", "clip": clip},
                       {"kind": "images", "url": url + "not-approved.png"}]}
    png = b"\x89PNG\r\n\x1a\nfixture"
    encoded = base64.b64encode(png).decode()
    browser = Mock(return_value={"cssContentSize": {"width": 1200, "height": 900}, "data": encoded})
    result = visual_helper["capture_page"](url, tmp_path, "home", js=Mock(return_value=page), cdp=browser)
    inspect = Mock(side_effect=[page, encoded])

    staged = visual_helper["stage_assets"](result["asset_inventory"], tmp_path / "library",
                                           ["icons-1", "backgrounds-1"], js=inspect, cdp=browser)

    assert set(staged) == {"icons-1", "backgrounds-1"}
    assert staged["backgrounds-1"]["source_url"] == image
    assert staged["icons-1"]["status"] == "rendered-reference"
    assert all(Path(item["file"]).read_bytes() == png for item in staged.values())
    assert image in inspect.call_args.args[0]

    manifest = Path(result["asset_inventory"])
    edited = json.loads(manifest.read_text())
    edited["assets"]["backgrounds"][0]["url"] = url + "different.png"
    manifest.write_text(json.dumps(edited))
    inspect = Mock(return_value=page)
    assert visual_helper["stage_assets"](manifest, tmp_path / "library", ["backgrounds-1"],
                                         js=inspect, cdp=browser) == {"backgrounds-1": {"status": "changed"}}
    inspect.assert_called_once()


@pytest.fixture
def camofox_helper(visual_helper):
    script = Path(visual_helper["__file__"]).with_name("camofox_visual_reference.py")
    return runpy.run_path(str(script))


@pytest.mark.parametrize(("destination_status", "evaluate_status", "challenge", "expected"), [
    (200, 501, False, "unavailable"),
    (403, 200, False, "blocked"),
    (200, 200, True, "blocked"),
])
def test_camofox_fallback_is_for_unavailable_backends_not_blocked_sites(
    camofox_helper, tmp_path, destination_status, evaluate_status, challenge, expected,
):
    url = "https://brand.example/"
    page = {"url": url, "title": "Brand", "body": "Shop", "images": [], "blocked": challenge}
    api = Mock()

    def response(method, endpoint, **kwargs):
        reply = MagicMock(status_code=200)
        reply.__enter__.return_value = reply
        if endpoint.endswith("/tabs"):
            reply.json.return_value = {"tabId": "tab-1"}
        elif endpoint.endswith("/navigate"):
            reply.json.return_value = {"url": url, "httpStatus": destination_status}
        elif endpoint.endswith("/evaluate"):
            reply.status_code = evaluate_status
            reply.json.return_value = {"result": page}
        else:
            reply.json.return_value = {"ok": True}
        return reply

    api.request.side_effect = response
    tab = camofox_helper["CamofoxTab"](api, "http://camofox:9377")
    output = tmp_path / "capture"
    result = camofox_helper["run"](tab, url, output, name="home", validate=Mock())
    assert result["status"] == expected
    assert not output.exists()
    assert not any(call.args[1].endswith("/screenshot") for call in api.request.call_args_list)
    assert api.request.call_args.args == ("DELETE", f"http://camofox:9377/sessions/{tab.user}")
