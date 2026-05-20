import json
import plistlib
import re
from pathlib import Path
from xml.etree import ElementTree


REPO_ROOT = Path(__file__).resolve().parents[2]
IOS_DIR = REPO_ROOT / "ios"
PROJECT_FILE = IOS_DIR / "LLMQuest.xcodeproj" / "project.pbxproj"
SCHEME_FILE = (
    IOS_DIR
    / "LLMQuest.xcodeproj"
    / "xcshareddata"
    / "xcschemes"
    / "LLMQuest.xcscheme"
)
INFO_PLIST = IOS_DIR / "LLMQuest" / "Info.plist"
APP_ICON_SET = IOS_DIR / "LLMQuest" / "Assets.xcassets" / "AppIcon.appiconset"
EXPORT_OPTIONS = IOS_DIR / "export" / "ExportOptions.plist.template"
TESTFLIGHT_DOC = REPO_ROOT / "docs" / "IOS_TESTFLIGHT.md"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_ios_project_bundles_static_site_and_swift_sources():
    project = read_text(PROJECT_FILE)

    assert "LLMQuest.app" in project
    assert "AppDelegate.swift in Sources" in project
    assert "SceneDelegate.swift in Sources" in project
    assert "QuestWebViewController.swift in Sources" in project
    assert "LocalSiteSchemeHandler.swift in Sources" in project
    assert "site in Resources" in project
    assert "path = ../site;" in project
    assert "PRODUCT_BUNDLE_IDENTIFIER = io.github.yourconscience.llmquestbenchmark;" in project
    assert "IPHONEOS_DEPLOYMENT_TARGET = 16.0;" in project


def test_ios_app_serves_play_page_from_bundle_scheme():
    controller = read_text(IOS_DIR / "LLMQuest" / "QuestWebViewController.swift")
    scheme_handler = read_text(IOS_DIR / "LLMQuest" / "LocalSiteSchemeHandler.swift")

    assert 'setURLSchemeHandler(LocalSiteSchemeHandler(), forURLScheme: "lqb")' in controller
    assert 'URL(string: "lqb://app/play.html")' in controller
    assert "allowsInlineMediaPlayback = true" in controller
    assert "mediaTypesRequiringUserActionForPlayback = []" in controller
    assert 'appendingPathComponent("site", isDirectory: true)' in scheme_handler
    assert 'let relativePath = requestedPath.isEmpty ? "play.html" : requestedPath' in scheme_handler
    assert '"application/gzip"' in scheme_handler
    assert '"audio/mpeg"' in scheme_handler


def test_ios_metadata_and_export_options_are_valid():
    info = plistlib.loads(INFO_PLIST.read_bytes())
    export = plistlib.loads(EXPORT_OPTIONS.read_bytes())
    ElementTree.parse(SCHEME_FILE)
    json.loads((IOS_DIR / "LLMQuest" / "Assets.xcassets" / "Contents.json").read_text())
    icons = json.loads((APP_ICON_SET / "Contents.json").read_text())

    assert info["CFBundleDisplayName"] == "LLM Quest"
    assert info["CFBundleIdentifier"] == "$(PRODUCT_BUNDLE_IDENTIFIER)"
    assert info["LSRequiresIPhoneOS"] is True
    assert export["method"] == "app-store-connect"
    assert export["destination"] == "upload"
    assert export["signingStyle"] == "automatic"
    assert any(icon.get("idiom") == "ios-marketing" for icon in icons["images"])


def test_ios_app_icon_files_match_declared_sizes():
    icons = json.loads((APP_ICON_SET / "Contents.json").read_text())["images"]

    for icon in icons:
        filename = icon["filename"]
        expected_size = int(float(icon["size"].split("x", 1)[0]) * int(icon["scale"].rstrip("x")))
        path = APP_ICON_SET / filename
        assert path.exists(), filename
        header = path.read_bytes()[:24]
        assert header[:8] == b"\x89PNG\r\n\x1a\n", filename
        width = int.from_bytes(header[16:20], "big")
        height = int.from_bytes(header[20:24], "big")
        assert width == expected_size, filename
        assert height == expected_size, filename


def test_ios_testflight_docs_include_archive_and_upload_commands():
    doc = read_text(TESTFLIGHT_DOC)

    assert "Full Xcode, not Command Line Tools only." in doc
    assert "APPLE_TEAM_ID" in doc
    assert "IOS_BUNDLE_ID" in doc
    assert re.search(r"xcodebuild archive\s+\\", doc)
    assert "-project ios/LLMQuest.xcodeproj" in doc
    assert "-scheme LLMQuest" in doc
    assert "-destination 'generic/platform=iOS'" in doc
    assert "xcodebuild -exportArchive" in doc
    assert "-exportOptionsPlist ios/export/ExportOptions.plist.template" in doc
