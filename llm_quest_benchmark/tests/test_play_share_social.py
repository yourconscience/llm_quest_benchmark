from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_SOURCE = REPO_ROOT / "site" / "play" / "app.jsx"
BLOG_PAGE = REPO_ROOT / "site" / "about.html"
BLOG_SCREENSHOT = REPO_ROOT / "site" / "img" / "play_quest_in_progress.png"


def test_share_result_supports_social_fallbacks():
    source = APP_SOURCE.read_text(encoding="utf-8")

    assert "navigator.canShare" in source
    assert "navigator.share" in source
    assert "navigator.clipboard" in source
    assert "downloadCanvas(canvas, 'quest-result.png')" in source
    assert "Copied share text and downloaded result image." in source


def test_blog_embeds_current_play_screenshot():
    blog = BLOG_PAGE.read_text(encoding="utf-8")

    assert BLOG_SCREENSHOT.exists()
    assert "img/play_quest_in_progress.png" in blog
    assert "decision history and AI cohort comparison" in blog


def test_play_history_does_not_claim_ai_agreement_with_limited_data():
    source = APP_SOURCE.read_text(encoding="utf-8")

    assert "const MIN_COHORT_LOCATION_RUNS = 3;" in source
    assert "function hasCohortLocationData(cohortLoc)" in source
    assert "const hasCohortData = isBranching && hasCohortLocationData(cohortLoc);" in source
    assert "agreed: hasCohortData ? agreed : null" in source
    assert "Limited AI data" in source
