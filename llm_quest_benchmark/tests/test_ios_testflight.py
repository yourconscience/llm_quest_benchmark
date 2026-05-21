import json
import os
import plistlib
import re
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

REPO_ROOT = Path(__file__).resolve().parents[2]
IOS_DIR = REPO_ROOT / "ios"
SITE_DIR = REPO_ROOT / "site"
PLAY_PAGE = SITE_DIR / "play.html"
PLAY_DIR = SITE_DIR / "play"
PLAY_QUESTS_DIR = PLAY_DIR / "quests"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
PROJECT_FILE = IOS_DIR / "LLMQuest.xcodeproj" / "project.pbxproj"
SCHEME_FILE = IOS_DIR / "LLMQuest.xcodeproj" / "xcshareddata" / "xcschemes" / "LLMQuest.xcscheme"
INFO_PLIST = IOS_DIR / "LLMQuest" / "Info.plist"
PRIVACY_MANIFEST = IOS_DIR / "LLMQuest" / "PrivacyInfo.xcprivacy"
STAGE_SITE_SCRIPT = IOS_DIR / "scripts" / "stage_site.sh"
APP_ICON_SET = IOS_DIR / "LLMQuest" / "Assets.xcassets" / "AppIcon.appiconset"
EXPORT_OPTIONS = IOS_DIR / "export" / "ExportOptions.plist.template"
TESTFLIGHT_DOC = REPO_ROOT / "docs" / "IOS_TESTFLIGHT.md"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class AssetHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.assets = []

    def handle_starttag(self, tag, attrs):
        for attr, value in attrs:
            if attr in {"href", "src"} and value:
                self.assets.append(value)


def test_ios_project_bundles_static_site_and_swift_sources():
    project = read_text(PROJECT_FILE)

    assert "LLMQuest.app" in project
    assert "AppDelegate.swift in Sources" in project
    assert "SceneDelegate.swift in Sources" in project
    assert "QuestWebViewController.swift in Sources" in project
    assert "LocalSiteSchemeHandler.swift in Sources" in project
    assert "PrivacyInfo.xcprivacy in Resources" in project
    assert "Stage Play Site" in project
    assert "alwaysOutOfDate = 1;" in project
    assert 'shellScript = "\\"${SRCROOT}/scripts/stage_site.sh\\"\\n";' in project
    assert "path = ../site;" in project
    assert "site in Resources" not in project
    assert "PRODUCT_BUNDLE_IDENTIFIER = io.github.yourconscience.llmquestbenchmark;" in project
    assert "IPHONEOS_DEPLOYMENT_TARGET = 16.0;" in project
    assert 'SUPPORTED_PLATFORMS = "iphoneos iphonesimulator";' in project
    assert 'TARGETED_DEVICE_FAMILY = "1,2";' in project


def test_ios_app_serves_play_page_from_bundle_scheme():
    controller = read_text(IOS_DIR / "LLMQuest" / "QuestWebViewController.swift")
    scheme_handler = read_text(IOS_DIR / "LLMQuest" / "LocalSiteSchemeHandler.swift")

    assert 'setURLSchemeHandler(LocalSiteSchemeHandler(), forURLScheme: "lqb")' in controller
    assert 'URL(string: "lqb://app/play.html")' in controller
    assert "allowsInlineMediaPlayback = true" in controller
    assert "mediaTypesRequiringUserActionForPlayback = []" in controller
    assert 'url.scheme == "lqb"' in controller
    assert 'url.host == "yourconscience.github.io"' not in controller
    assert "UIApplication.shared.open(url)" in controller
    assert 'appendingPathComponent("site", isDirectory: true)' in scheme_handler
    assert 'let relativePath = requestedPath.isEmpty ? "play.html" : requestedPath' in scheme_handler
    assert "statusCode: 404" in scheme_handler
    assert "standardizedFileURL" in scheme_handler
    assert "fileURL.path.hasPrefix(siteRootPath + " in scheme_handler
    assert '"application/gzip"' in scheme_handler
    assert '"audio/mpeg"' in scheme_handler


def test_ios_metadata_and_export_options_are_valid():
    project = read_text(PROJECT_FILE)
    info = plistlib.loads(INFO_PLIST.read_bytes())
    privacy = plistlib.loads(PRIVACY_MANIFEST.read_bytes())
    export = plistlib.loads(EXPORT_OPTIONS.read_bytes())
    scheme = ElementTree.parse(SCHEME_FILE).getroot()
    json.loads((IOS_DIR / "LLMQuest" / "Assets.xcassets" / "Contents.json").read_text())
    icons = json.loads((APP_ICON_SET / "Contents.json").read_text())

    build_action_entry = scheme.find("./BuildAction/BuildActionEntries/BuildActionEntry")
    archive_action = scheme.find("./ArchiveAction")
    assert build_action_entry is not None
    assert build_action_entry.attrib["buildForArchiving"] == "YES"
    assert archive_action is not None
    assert archive_action.attrib["buildConfiguration"] == "Release"

    assert info["CFBundleDisplayName"] == "LLM Quest"
    assert info["CFBundleIdentifier"] == "$(PRODUCT_BUNDLE_IDENTIFIER)"
    assert info["CFBundleShortVersionString"] == "$(MARKETING_VERSION)"
    assert info["CFBundleVersion"] == "$(CURRENT_PROJECT_VERSION)"
    assert info["LSRequiresIPhoneOS"] is True
    assert info["ITSAppUsesNonExemptEncryption"] is False
    assert "UILaunchScreen" in info
    assert info["UISupportedInterfaceOrientations"] == [
        "UIInterfaceOrientationPortrait",
        "UIInterfaceOrientationLandscapeLeft",
        "UIInterfaceOrientationLandscapeRight",
    ]
    assert info["UISupportedInterfaceOrientations~ipad"] == [
        "UIInterfaceOrientationPortrait",
        "UIInterfaceOrientationPortraitUpsideDown",
        "UIInterfaceOrientationLandscapeLeft",
        "UIInterfaceOrientationLandscapeRight",
    ]
    assert export["method"] == "app-store-connect"
    assert export["destination"] == "upload"
    assert export["signingStyle"] == "automatic"
    assert any(icon.get("idiom") == "ios-marketing" for icon in icons["images"])
    assert project.count("MARKETING_VERSION = 1.0;") == 2
    assert project.count("CURRENT_PROJECT_VERSION = 1;") == 2
    assert privacy["NSPrivacyCollectedDataTypes"] == []
    assert privacy["NSPrivacyTracking"] is False
    assert privacy["NSPrivacyTrackingDomains"] == []
    assert privacy["NSPrivacyAccessedAPITypes"] == [
        {
            "NSPrivacyAccessedAPIType": "NSPrivacyAccessedAPICategoryFileTimestamp",
            "NSPrivacyAccessedAPITypeReasons": ["C617.1"],
        }
    ]


def test_ios_bundled_play_page_assets_are_present_after_site_build():
    page = read_text(PLAY_PAGE)
    parser = AssetHTMLParser()
    parser.feed(page)

    local_assets = [asset for asset in parser.assets if not asset.startswith(("http://", "https://", "#"))]
    local_runtime_assets = [asset for asset in local_assets if asset.startswith("play/")]

    assert "play/qmengine.js" in local_runtime_assets
    assert "play/app.js" in local_runtime_assets
    assert "play/vendor/bootstrap-5.3.3.min.css" in local_runtime_assets
    assert "play/vendor/react-18.3.1.production.min.js" in local_runtime_assets
    assert "play/vendor/react-dom-18.3.1.production.min.js" in local_runtime_assets
    assert "play/vendor/pako-2.1.0.min.js" in local_runtime_assets
    assert "play/questplay/background.jpg" in page
    assert "https://cdn.jsdelivr.net" not in page
    assert "https://unpkg.com" not in page

    for asset in [*local_assets, "play/questplay/background.jpg"]:
        assert (SITE_DIR / asset).exists(), asset


def test_ios_site_staging_includes_only_play_runtime_payload(tmp_path):
    destination = tmp_path / "bundle" / "site"

    subprocess.run(
        ["sh", str(STAGE_SITE_SCRIPT)],
        check=True,
        env={
            **os.environ,
            "SOURCE_SITE": str(SITE_DIR),
            "DEST_SITE": str(destination),
        },
    )

    assert (destination / "play.html").exists()
    assert (destination / "play" / "app.js").exists()
    assert (destination / "play" / "qmengine.js").exists()
    assert (destination / "play" / "quest-index.json").exists()
    assert (destination / "play" / "quests" / "Badday_eng.qm.gz").exists()
    assert (destination / "play" / "questplay" / "background.jpg").exists()
    assert (destination / "play" / "vendor" / "NOTICE.md").exists()

    assert not (destination / "index.html").exists()
    assert not (destination / "about.html").exists()
    assert not (destination / "traces.html").exists()
    assert not (destination / "traces").exists()
    assert not (destination / "play" / "app.jsx").exists()
    assert not (destination / "play" / "engine-entry.ts").exists()


def test_ios_bundled_vendor_runtime_assets_include_license_notice():
    notice = read_text(PLAY_DIR / "vendor" / "NOTICE.md")

    assert "Bootstrap 5.3.3" in notice
    assert "React 18.3.1" in notice
    assert "React DOM 18.3.1" in notice
    assert "pako 2.1.0" in notice
    assert "MIT" in notice
    assert "Zlib" in notice


def test_ios_bundled_quest_archives_cover_play_index_after_site_build():
    index = json.loads((PLAY_DIR / "quest-index.json").read_text(encoding="utf-8"))
    quest_ids = {quest["id"] for quest in index["quests"]}
    canonical_ids = {quest["canonical_id"] for quest in index["quests"] if quest.get("canonical_id")}

    assert quest_ids
    assert canonical_ids <= quest_ids

    for quest_id in quest_ids:
        archive = PLAY_QUESTS_DIR / f"{quest_id}.qm.gz"
        assert archive.exists(), quest_id
        assert archive.stat().st_size > 0, quest_id

    for canonical_id in canonical_ids:
        cohort = PLAY_DIR / f"{canonical_id}.json"
        assert cohort.exists(), canonical_id
        assert cohort.stat().st_size > 0, canonical_id


def test_ios_app_icon_files_match_declared_sizes():
    icons = json.loads((APP_ICON_SET / "Contents.json").read_text())["images"]

    for icon in icons:
        filename = icon["filename"]
        expected_size = int(float(icon["size"].split("x", 1)[0]) * int(icon["scale"].rstrip("x")))
        path = APP_ICON_SET / filename
        assert path.exists(), filename
        header = path.read_bytes()[:26]
        assert header[:8] == b"\x89PNG\r\n\x1a\n", filename
        width = int.from_bytes(header[16:20], "big")
        height = int.from_bytes(header[20:24], "big")
        color_type = header[25]
        assert width == expected_size, filename
        assert height == expected_size, filename
        assert color_type == 2, f"{filename} should be RGB PNG without alpha"


def test_ios_testflight_docs_include_archive_and_upload_commands():
    doc = read_text(TESTFLIGHT_DOC)

    assert "Full Xcode 16 or later, not Command Line Tools only." in doc
    assert "physical iPhone or iPad" in doc
    assert "ios-build" in doc
    assert "iOS Simulator" in doc
    assert "APPLE_TEAM_ID" in doc
    assert "IOS_BUNDLE_ID" in doc
    assert "App Store Connect app record" in doc
    assert "App Store Connect API" in doc
    assert "Transporter-based uploads" in doc
    assert "CURRENT_PROJECT_VERSION" in doc
    assert "MARKETING_VERSION" in doc
    assert "starts at marketing version 1.0 and build number 1" in doc
    assert "ITSAppUsesNonExemptEncryption" in doc
    assert "PrivacyInfo.xcprivacy" in doc
    assert "stages only the Play runtime payload" in doc
    assert "source-only files" in doc
    assert "site/play/vendor/" in doc
    assert "NOTICE.md" in doc
    assert "App Privacy" in doc
    assert "privacy policy URL" in doc
    assert "no tracking" in doc
    assert "no collected" in doc
    assert "Export Compliance" in doc
    assert "missing compliance" in doc
    assert "Beta App Review Information" in doc
    assert "review contact name" in doc
    assert "phone" in doc
    assert "No sign-in or demo account is required." in doc
    assert re.search(r"xcodebuild archive\s+\\", doc)
    assert "-project ios/LLMQuest.xcodeproj" in doc
    assert "-scheme LLMQuest" in doc
    assert "-destination 'generic/platform=iOS'" in doc
    assert "xcodebuild -exportArchive" in doc
    assert "-exportOptionsPlist ios/export/ExportOptions.plist.template" in doc
    assert "Test Information" in doc
    assert "Beta App Description" in doc
    assert "Feedback Email" in doc
    assert "What to Test" in doc
    assert "Review Notes" in doc
    assert "project support address" in doc
    assert "External testing requires Beta App Review." in doc
    assert "simulator-only testing is not enough" in doc


def test_ci_builds_ios_project_on_macos_for_prs():
    workflow = read_text(CI_WORKFLOW)

    assert "ios-build:" in workflow
    assert "runs-on: macos-15" in workflow
    assert "pnpm run build" in workflow
    assert "xcodebuild build" in workflow
    assert "-project ios/LLMQuest.xcodeproj" in workflow
    assert "-scheme LLMQuest" in workflow
    assert "-destination 'generic/platform=iOS Simulator'" in workflow
    assert "CODE_SIGNING_ALLOWED=NO" in workflow
