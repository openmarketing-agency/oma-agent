"""OMA creatives: collectors, storage rules and the validator, driven through fake pages offline.

The collectors' contract is honesty: a source is ``checked`` only when its page really loaded and was
read; a login wall is ``limited`` with the visible count; a challenge, firewall page or unloaded
search is ``blocked``/``not_checked`` with proof, never an empty ``checked``.
"""

from dataclasses import dataclass, field
import datetime as dt
import importlib
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

from PIL import Image
import pytest

from tools.skills_sync import sync_skills
from tools.skills_tool import skill_view

NOW = dt.datetime(2026, 11, 26, 12, 0, tzinfo=dt.UTC)


@pytest.fixture
def oc(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    sync_skills(quiet=True)
    skill = json.loads(skill_view("oma/oma-creatives"))
    assert skill["success"], skill
    scripts = Path(skill["skill_dir"]) / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    modules = {name: importlib.import_module(f"oma_collect.{name}")
               for name in ("ads", "browser", "run", "social", "store", "values")}
    return SimpleNamespace(scripts=scripts, home=tmp_path, **modules)


def _jpeg() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (64, 64), "red").save(buffer, format="JPEG")
    return buffer.getvalue()


class FakeFetcher:
    def __init__(self, pages=None):
        self.pages = pages or {}

    def get_text(self, url, *, params=None):
        return self.pages.get(url)

    def get_json(self, url, *, params=None):
        return self.pages.get(url)

    def download(self, url, dest, *, referer=None):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(_jpeg())
        return dest, "image/jpeg"


@dataclass
class FakePage:
    state: dict = field(default_factory=dict)
    answers: dict = field(default_factory=dict)  # substring of the JS expression -> value
    clicks: dict = field(default_factory=dict)


class FakeBrowser:
    """Serves scripted page states; ``js`` answers by a marker substring of the collector's script."""

    name = "fake"

    def __init__(self, oc, pages: dict[str, FakePage]):
        self.oc, self.pages, self.url, self.after = oc, pages, None, {}

    def _page(self):
        return next(page for prefix, page in self.pages.items() if self.url.startswith(prefix))

    def _state(self, page):
        base = {"url": self.url, "title": "", "http_status": 200, "text_len": 5000, "captcha": False,
                "login_dialog": False, "login_wall": False, "denied": False}
        return self.oc.browser.PageState(**{**base, **page.state, **self.after.get(self.url, {})})

    def goto(self, url, *, wait=0.0):
        self.url = url
        return self._state(self._page())

    def current(self, http_status=0):
        return self._state(self._page())

    def js(self, expression):
        for marker, value in self._page().answers.items():
            if marker in expression:
                return value(expression) if callable(value) else value
        return None

    def click(self, selector):
        return self._page().clicks.get(selector, False)

    def scroll(self, times, *, pause=2.0):
        return None

    def screenshot(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_jpeg())
        return path

    def close(self):
        return None


def _brand(home: Path, socials: dict | None = None) -> Path:
    brand = home / "oma" / "brand"
    brand.mkdir(parents=True)
    social = [{"platform": p, "status": "verified", "url": u} for p, u in (socials or {}).items()]
    (brand / "config.yaml").write_text(json.dumps({"id": "brand", "name": "Brand", "channels": {"social": social}}))
    return brand


def _ctx(oc, brand, target, browser=None, fetcher=None):
    return oc.run.Context(brand, target, moment=NOW, fetcher=fetcher or FakeFetcher(), _browser=browser)


def _validate(oc, brand, target):
    done = subprocess.run([sys.executable, str(oc.scripts / "validate_creatives.py"), str(brand), target],
                          capture_output=True, text=True, check=False)
    return done.returncode, done.stdout


# ---- values and parsers ------------------------------------------------------------------

def test_counts_and_post_ids_decode_to_what_the_platforms_show(oc):
    v = oc.values
    assert [v.parse_count(x) for x in ("1.2K", "2.6M", "12,400", "970.4K", "7")] == [1200, 2_600_000, 12400, 970400, 7]
    assert v.followers_in("Canva 2.6M followers 1,406 following") == 2_600_000
    assert v.x_post_time("2095923595922780297").date() == dt.date(2026, 9, 4)
    assert v.linkedin_post_time("7520905424926162944").date() == dt.date(2026, 10, 27)
    # A TikTok ID carries the upload time, seconds before the publish time the video page reports.
    assert abs(v.tiktok_post_time("7670952298088008967") - v.from_unix(1786032767)) < dt.timedelta(minutes=1)


def test_instagram_page_metadata_gives_metrics_date_and_caption(oc):
    post = oc.social.parse_instagram({"desc": '770 likes, 67 comments - canva on October 30, 2026: "What will you Canva today?"',
                                      "image": "https://cdn.example/p.jpg", "videos": ["https://cdn.example/v.mp4"]})
    assert post["metrics"]["likes"] == 770 and post["metrics"]["comments"] == 67
    assert post["posted_at"] == "2026-10-30T00:00:00Z"
    assert post["caption"] == "What will you Canva today?"
    assert [kind for _, kind in post["media_sources"]] == ["video", "image"]


def test_meta_cards_parse_status_run_dates_variants_and_landing(oc):
    today = NOW.date()
    active = oc.ads.parse_meta_card({"text": "Active\nLibrary ID: 111\nStarted running on Nov 1, 2026\nPlatforms\n"
                                             "2 ads use this creative and text\nSee summary details\nCanva\nSponsored\n"
                                             "Say so long to backgrounds.\nTry Canva\nSign up",
                                     "landing": "https://l.facebook.com/l.php?u=https%3A%2F%2Fwww.canva.com%2Fpro%2F&h=x",
                                     "videos": ["https://video.example/a.mp4"]}, today)
    inactive = oc.ads.parse_meta_card({"text": "Inactive\nLibrary ID: 222\nMar 26, 2026 - Aug 1, 2026\nCanva\nSponsored\nMake decks"},
                                      today)
    assert active["id"] == "meta-111" and active["active"] and active["variant_count"] == 2
    assert (active["first_seen"], active["last_seen"]) == ("2026-11-01", today.isoformat())
    assert active["landing_url"] == "https://www.canva.com/pro/" and active["advertiser"] == "Canva"
    assert (inactive["active"], inactive["first_seen"], inactive["last_seen"]) == (False, "2026-03-26", "2026-08-01")


def test_google_detail_names_the_advertiser_not_the_faq_link(oc):
    text = ("Ads Transparency Center\nHome\nCanva Pty Ltd\nAd details\nFAQ\nAd details\nCanva Pty Ltd\n"
            "Last shown: Nov 26, 2026\nFormat: Video\n1 of 7 variations")
    ad = oc.ads.parse_google_detail("https://adstransparency.google.com/advertiser/AR1/creative/CR9", {"text": text}, NOW.date())
    assert ad["advertiser"] == "Canva Pty Ltd" and ad["format"] == "video"
    assert ad["variant_count"] == 7 and ad["active"] and ad["last_seen"] == "2026-11-26"


# The text of a real LinkedIn Ad Library detail page (Nov 2026), trimmed after the impressions.
_LINKEDIN_DETAIL = ("Ad Library\nLinkedIn Ad Library\nAd Details\nBeautiful.ai\n\nPromoted\n\nLet AI do the heavy lifting "
                    "in slide design.\n\nStart Your Free Trial\nSign Up\nPlease note that this ad may have multiple "
                    "versions.\nAbout the ad\n\nVideo Ad\n\nAdvertiser Beautiful.ai\n\nPaid for by Beautiful Slides Inc.\n\n"
                    "Ran from Jun 24, 2026 to Jun 27, 2026\n\nAd Impressions\n\nTotal Impressions\n\n1k-5k\n\nCountry\n\nItaly")


def test_linkedin_ad_detail_reads_copy_button_dates_and_impressions(oc):
    ad = oc.ads.parse_linkedin_ad("https://www.linkedin.com/ad-library/detail/1479502326", {"text": _LINKEDIN_DETAIL})
    assert (ad["id"], ad["format"], ad["advertiser"]) == ("linkedin-1479502326", "video", "Beautiful.ai")
    assert ad["primary_text"] == "Let AI do the heavy lifting in slide design."
    assert (ad["headline"], ad["cta"]) == ("Start Your Free Trial", "Sign Up")
    assert (ad["first_seen"], ad["last_seen"], ad["reach"]) == ("2026-06-24", "2026-06-27", "1k-5k")


def test_a_broken_library_collector_is_recorded_without_stopping_the_run(oc, monkeypatch):
    brand = _brand(oc.home)

    def broken(ctx, spec):
        raise IndexError("no such group")

    monkeypatch.setitem(oc.run.LIBRARIES, "linkedin", oc.ads.Library(broken, "https://www.linkedin.com/ad-library/"))
    result = oc.run.collect_library(_ctx(oc, brand, "own", FakeBrowser(oc, {})), "linkedin", {"advertiser": "Brand"})
    index = oc.store.load(brand / "research/own/ads/linkedin/index.yaml")
    assert result["status"] == index["coverage"]["status"] == "not_checked"
    assert "IndexError" in index["coverage"]["note"]


def test_x_accessibility_label_maps_to_metrics(oc):
    metrics = oc.social.parse_x_metrics(["12 replies, 1 repost, 5 likes, 2 bookmarks, 23 views"])
    assert metrics == {"likes": 5, "comments": 12, "shares": 1, "saves": 2, "views": 23}


# ---- storage rules -----------------------------------------------------------------------

def _post(oc, n, days_ago, engagement):
    posted = NOW - dt.timedelta(days=days_ago)
    return oc.store.finish_post({"id": f"p{n}", "url": f"https://x/{n}", "posted_at": oc.values.iso(posted), "caption": "",
                                 "metrics": {"likes": engagement}, "media": []}, 1000, NOW)


def test_selection_keeps_latest_25_and_top_10_mature_posts_from_90_days(oc):
    posts = [_post(oc, n, n + 3, 10) for n in range(30)]
    posts += [_post(oc, 100, 200, 9999), _post(oc, 101, 1, 5000), _post(oc, 102, 40, 900)]
    selected, history = oc.store.select_posts(posts, NOW)
    ids = {p["id"] for p in selected}
    assert sum("latest" in p["selected_by"] for p in selected) == 25
    assert "p100" not in ids, "a post older than 90 days is not a top post"
    assert next(p for p in selected if p["id"] == "p101")["selected_by"] == ["latest"], "an immature post is not ranked"
    assert "top" in next(p for p in selected if p["id"] == "p102")["selected_by"]
    assert len(selected) <= 35 and {p["id"] for p in history} >= {"p100"}


def test_rerun_keeps_labels_and_marks_missing_ads_inactive_only_after_a_complete_check(oc):
    old = {"id": "meta-1", "active": True, "first_seen": "2026-10-01", "last_seen": "2026-11-20", "hook_type": "stat"}
    index = {"ads": [oc.store.finish_ad(dict(old))]}
    kept, _ = oc.store.merge_ads(index, [], complete=False)
    assert kept[0]["active"] is True
    gone, _ = oc.store.merge_ads(index, [], complete=True)
    assert gone[0]["active"] is False and gone[0]["hook_type"] == "stat" and gone[0]["last_seen"] == "2026-11-20"


# ---- collectors through fake pages -------------------------------------------------------

def _instagram_pages(login_dialog=True):
    links = {"links": [f"https://www.instagram.com/brand/p/Post{n}/" for n in range(3)], "text": "Brand 12K followers"}
    detail = {"desc": '10 likes, 2 comments - brand on November 1, 2026: "Launch day"', "image": "https://cdn.example/i.jpg",
              "videos": [], "posters": [], "images": []}
    return {"https://www.instagram.com/brand/p/": FakePage(answers={"og:description": detail}),
            "https://www.instagram.com/brand/": FakePage(state={"login_dialog": login_dialog}, answers={"new RegExp": links})}


def test_login_wall_is_limited_with_visible_count_and_proof(oc):
    brand = _brand(oc.home, {"instagram": "https://www.instagram.com/brand/"})
    ctx = _ctx(oc, brand, "own", FakeBrowser(oc, _instagram_pages()))
    result = oc.run.collect_platform(ctx, "instagram", "https://www.instagram.com/brand/")
    index = oc.store.load(brand / "research/own/socials/instagram/index.yaml")
    assert result["status"] == "limited" and index["coverage"]["visible_count"] == 3
    assert (brand / index["coverage"]["proof"]["screenshot"]).is_file()
    assert index["account"]["followers"] == 12000
    assert all(post["media"] and (brand / post["media"][0]).is_file() for post in index["posts"])
    assert {post["id"] for post in index["posts"]} == {"Post0", "Post1", "Post2"}, "case-sensitive IDs keep their case"


@pytest.mark.parametrize(("state", "status"), [({"captcha": True}, "blocked"), ({"denied": True}, "blocked")])
def test_challenge_or_firewall_page_is_blocked_never_an_empty_check(oc, state, status):
    brand = _brand(oc.home)
    pages = {"https://www.instagram.com/": FakePage(state=state, answers={"new RegExp": {"links": [], "text": ""}})}
    result = oc.run.collect_platform(_ctx(oc, brand, "own", FakeBrowser(oc, pages)), "instagram",
                                     "https://www.instagram.com/brand/")
    index = oc.store.load(brand / "research/own/socials/instagram/index.yaml")
    assert result["status"] == status and index["coverage"]["proof"]["url"]


def test_deferred_ads_record_every_library_without_opening_a_browser(oc, monkeypatch):
    brand = _brand(oc.home)
    oc.store.dump(brand / "research/own/sources.yaml", {"target": "own", "socials": {},
                                                         "ads": {"meta": {"page_id": "123"}, "google": {"domain": "b.example"}}})
    monkeypatch.setattr(oc.run, "open_browser", lambda *a, **k: pytest.fail("a deferred run opened a browser"))
    results = oc.run.run_ads(brand, "own", defer="Ad libraries are collected after signup.")
    assert {r["source"]: r["status"] for r in results} == dict.fromkeys(("meta", "google", "linkedin", "tiktok"), "not_checked")
    meta = oc.store.load(brand / "research/own/ads/meta/index.yaml")
    assert meta["coverage"]["note"] == "Ad libraries are collected after signup." and meta["ads"] == []


def test_unloaded_ad_results_are_not_recorded_as_no_ads(oc):
    brand = _brand(oc.home)
    for text, expected in (("Meta Ad Library  Search by keyword", "not_checked"), ("~0 results", "checked")):
        pages = {"https://www.facebook.com/ads/library/": FakePage(
            answers={"Library ID": {"total": 0, "cards": []}, "document.body ?": text})}
        result = oc.run.collect_library(_ctx(oc, brand, "own", FakeBrowser(oc, pages)), "meta", {"page_id": "123"})
        assert result["status"] == expected, text


def test_a_linkedin_company_with_no_ads_is_checked_not_unloaded(oc):
    brand = _brand(oc.home)
    search = "https://www.linkedin.com/ad-library/search?companyIds=28843016"
    for text, expected in (("Ad Library\nCompany or advertiser\nSearch\nNo results found\nAbout", "checked"),
                           ("Ad Library\nCompany or advertiser\nSearch\nAbout", "not_checked")):
        pages = {search: FakePage(answers={"/ad-library/detail/": [], "document.body ?": text})}
        result = oc.run.collect_library(_ctx(oc, brand, "own", FakeBrowser(oc, pages)), "linkedin",
                                        {"company_id": "28843016"})
        assert result["status"] == expected, text


def test_tiktok_without_a_selectable_country_never_reports_checked(oc):
    brand = _brand(oc.home)
    pages = {"https://library.tiktok.com/ads": FakePage(answers={"(async (country)": {"options": 0, "chosen": False}})}
    result = oc.run.collect_library(_ctx(oc, brand, "own", FakeBrowser(oc, pages)), "tiktok", {"advertiser": "Brand"})
    assert result["status"] == "not_checked" and "no countries" in result["note"]


def test_tiktok_searches_every_country_and_stores_each_ad_once(oc):
    brand = _brand(oc.home)
    cards = {"total": "1", "cards": [{"href": "https://library.tiktok.com/ads/detail/?ad_id=77", "text": "Brand\n10/01/2026\n11/20/2026"}]}
    pages = {"https://library.tiktok.com/": FakePage(answers={"(async (country)": {"options": 30, "chosen": True},
                                                              "(async (name)": {"ok": True}, "Total ads": cards})}
    result = oc.ads.collect_tiktok(_ctx(oc, brand, "own", FakeBrowser(oc, pages)),
                                   {"advertiser": "Brand", "countries": ["DE", "FR", "IT"]})
    assert result.status == "checked" and len(result.ads) == 1
    assert result.ads[0]["regions"] == ["DE", "FR", "IT"] and result.extra["countries_checked"] == ["DE", "FR", "IT"]


def test_tiktok_challenge_on_search_stops_with_blocked(oc):
    brand = _brand(oc.home)
    browser = FakeBrowser(oc, {"https://library.tiktok.com/": FakePage(
        answers={"(async (country)": {"options": 30, "chosen": True}, "(async (name)": {"ok": True}})})
    browser.current = lambda http_status=0: oc.browser.PageState(
        url=browser.url, title="", http_status=200, text_len=900, captcha=True, login_dialog=False, login_wall=False)
    result = oc.ads.collect_tiktok(_ctx(oc, brand, "own", browser), {"advertiser": "Brand", "countries": ["DE", "FR"]})
    assert result.status == "blocked" and result.proof_reason == "captcha" and "0 of 2" in result.note


# ---- browser driver ----------------------------------------------------------------------

class _Reply:
    def __init__(self, status, body=None):
        self.status_code, self._body, self.content = status, body or {}, b""

    def json(self):
        return self._body


def test_camofox_reopens_a_dropped_tab_and_retries_a_busy_evaluate(oc, public_dns):
    calls = {"tabs": 0, "evaluate": 0, "navigate": 0}

    class Http:
        def request(self, method, url, **kwargs):
            if url.endswith("/tabs"):
                calls["tabs"] += 1
                return _Reply(200, {"tabId": f"t{calls['tabs']}"})
            if url.endswith("/navigate"):
                calls["navigate"] += 1
                return _Reply(410) if calls["navigate"] == 1 else _Reply(200, {"httpStatus": 200})
            if url.endswith("/evaluate"):
                calls["evaluate"] += 1
                if calls["evaluate"] == 1:
                    return _Reply(503)
                expression = kwargs["json"]["expression"]
                if "readyState" in expression:
                    return _Reply(200, {"result": {"href": "https://example.com/", "ready": "complete"}})
                return _Reply(200, {"result": {"href": "https://example.com/", "title": "Ok", "text_len": 900}})
            return _Reply(200, {"ok": True})

    browser = oc.browser.CamofoxBrowser(Http(), "http://camofox:9377")
    state = browser.goto("https://example.com/")
    assert state.verdict == "ok" and calls["tabs"] == 2, "the dropped tab was replaced and the page loaded"


# ---- validator ---------------------------------------------------------------------------

def _collected(oc, brand, target="own", socials=("pinterest", "bluesky")):
    root = oc.store.target_root(brand, target)
    sources = {"socials": {p: f"https://{p}.example/brand" for p in socials}, "ads": {lib: None for lib in oc.ads.LIBRARIES}}
    oc.store.dump(root / "sources.yaml", sources)
    for platform in socials:
        folder = root / "socials" / platform
        (folder / "p1").mkdir(parents=True)
        (folder / "p1" / "media-1.jpg").write_bytes(_jpeg())
        post = oc.store.finish_post({"id": "p1", "url": "https://x/p1", "posted_at": "2026-11-01T10:00:00Z", "caption": "Launch",
                                     "metrics": {"likes": 3}, "media": [f"{folder.relative_to(brand)}/p1/media-1.jpg"],
                                     "format": "image", "hook_type": "bold_claim", "angle": "outcome", "structure": "Hook, CTA"},
                                    100, NOW)
        post["selected_by"] = ["latest"]
        oc.store.dump(folder / "index.yaml", {"account": {"profile_url": sources["socials"][platform]},
                                              "coverage": oc.store.coverage("checked"), "posts": [post]})
    for library in oc.ads.LIBRARIES:
        oc.store.dump(root / "ads" / library / "index.yaml",
                      {"coverage": oc.store.coverage("not_checked", "No advertiser identifier."), "ads": []})
    (root / "creatives.md").write_text("# Creatives\n")
    return root


def test_a_planned_and_collected_target_passes(oc):
    brand = _brand(oc.home)
    _collected(oc, brand)
    code, out = _validate(oc, brand, "own")
    assert code == 0, out


def test_a_summary_without_collections_fails(oc):
    brand = _brand(oc.home)
    root = oc.store.target_root(brand, "own")
    root.mkdir(parents=True)
    (root / "creatives.md").write_text("# Creatives\nAd libraries: blocked (not attempted).\n")
    code, out = _validate(oc, brand, "own")
    assert code == 1 and "sources.yaml is missing" in out and "not a collection" in out


@pytest.mark.parametrize(("coverage", "message"), [
    ({"status": "blocked", "note": "challenge"}, "proof.url"),
    ({"status": "limited", "note": "login wall"}, "visible_count"),
    ({"status": "not_checked", "note": ""}, "needs a note"),
])
def test_coverage_claims_need_their_evidence(oc, coverage, message):
    brand = _brand(oc.home)
    root = _collected(oc, brand)
    index_path = root / "socials" / "pinterest" / "index.yaml"
    index = oc.store.load(index_path)
    index["coverage"] = coverage
    oc.store.dump(index_path, index)
    code, out = _validate(oc, brand, "own")
    assert code == 1 and message in out


def test_planned_sources_and_the_brands_verified_profiles_must_be_collected(oc):
    brand = _brand(oc.home, {"tiktok": "https://www.tiktok.com/@brand"})
    root = _collected(oc, brand)
    sources = oc.store.load(root / "sources.yaml")
    sources["socials"]["instagram"] = "https://www.instagram.com/brand/"
    oc.store.dump(root / "sources.yaml", sources)
    code, out = _validate(oc, brand, "own")
    assert code == 1
    assert "socials/instagram: listed in sources.yaml but not collected" in out
    assert "verified tiktok profile is not planned" in out


def test_labels_outside_the_taxonomy_are_rejected(oc):
    brand = _brand(oc.home)
    _collected(oc, brand)
    allowed = {"format": {"image"}, "hook_type": {"stat"}, "angle": {"pain"}}
    result = oc.run.apply_labels(brand, "own", [{"source": "socials/pinterest", "id": "p1", "hook_type": "nonsense"},
                                                {"source": "socials/bluesky", "id": "p1", "hook_type": "stat"}], allowed)
    assert result["applied"] == 1 and result["rejected"][0]["invalid"] == ["hook_type"]
    assert oc.store.load(brand / "research/own/socials/bluesky/index.yaml")["posts"][0]["hook_type"] == "stat"


@pytest.mark.parametrize(("text", "status"), [("Brand  Posts  Replies", "not_checked"),
                                              ("Brand hasn't posted yet", "checked"),
                                              ("This account is private", "limited")])
def test_a_profile_without_visible_posts_is_empty_only_when_the_page_says_so(oc, text, status):
    """A page that has not rendered its feed (the Hermes browser on X) once came back as checked with 0 posts."""
    brand = _brand(oc.home)
    pages = {"https://x.com/": FakePage(answers={"new RegExp": {"links": [], "text": text}})}
    result = oc.run.collect_platform(_ctx(oc, brand, "own", FakeBrowser(oc, pages)), "x", "https://x.com/brand")
    assert result["status"] == status


def test_headless_denial_page_reads_as_a_block(oc):
    """X serves headless Chrome a 403 page; CDP navigation reports no status, the page's own timing does."""
    signals = {"href": "https://x.com/brand", "title": "x.com", "text_len": 90, "denied": True, "status": 403}
    state = oc.browser._state(signals, 0)
    assert state.http_status == 403 and state.verdict == "error"
