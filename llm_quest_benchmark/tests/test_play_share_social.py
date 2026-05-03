from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_SOURCE = REPO_ROOT / "site" / "play" / "app.jsx"
BLOG_PAGE = REPO_ROOT / "site" / "blog.html"
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
