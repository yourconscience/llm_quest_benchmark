# iOS TestFlight Build

This repo ships the Play experience as a small native iOS app in `ios/LLMQuest.xcodeproj`.
The app uses `WKWebView` and serves the bundled `site/` directory through the local
`lqb://app/` scheme, so the same static quest UI, quest engine, AI answer panels, and
media paths are used on iOS.

## Prerequisites

- Full Xcode 16 or later, not Command Line Tools only.
- Apple Developer Program membership with App Store Connect access.
- A unique bundle id, for example `com.example.llmquest`.
- An App Store Connect app record that uses the same bundle id.
- Xcode signed in to the Apple Developer account, or App Store Connect API
  credentials available for Transporter-based uploads.
- At least one supported physical iPhone or iPad for release testing.

Apple documents App Store Connect as the distribution method for TestFlight and the
App Store:

- https://help.apple.com/xcode/mac/current/en.lproj/dev31de635e5.html
- https://developer.apple.com/help/app-store-connect/manage-builds/upload-builds/
- https://help.apple.com/xcode/mac/current/en.lproj/dev2539d985f.html

## Build Site Assets

```sh
pnpm run build
```

## Pull Request Build Gate

The `ios-build` CI job builds `ios/LLMQuest.xcodeproj` on a macOS runner for the
iOS Simulator after rebuilding the bundled static site assets. A passing PR build
proves the Xcode project compiles and can bundle the current Play payload before
manual archive/signing work starts.

## Archive for TestFlight

Set the signing values for your account:

```sh
export APPLE_TEAM_ID=YOURTEAMID
export IOS_BUNDLE_ID=com.example.llmquest
```

Before each upload, bump the Xcode build number (`CURRENT_PROJECT_VERSION`) so App
Store Connect can distinguish the new build for the same marketing version.
The app declares `ITSAppUsesNonExemptEncryption` as false because it does not
ship custom or non-exempt encryption code.
The app also bundles `PrivacyInfo.xcprivacy`, declaring no tracking, no collected
data, and the required-reason file timestamp access used while serving bundled
local quest assets.
The local browser runtime files under `site/play/vendor/` are included in the
iOS app bundle for offline TestFlight execution; keep their `NOTICE.md` file with
the vendored assets.

Archive the app:

```sh
xcodebuild archive \
  -project ios/LLMQuest.xcodeproj \
  -scheme LLMQuest \
  -configuration Release \
  -destination 'generic/platform=iOS' \
  -archivePath build/LLMQuest.xcarchive \
  DEVELOPMENT_TEAM="$APPLE_TEAM_ID" \
  PRODUCT_BUNDLE_IDENTIFIER="$IOS_BUNDLE_ID" \
  -allowProvisioningUpdates
```

Upload to App Store Connect:

```sh
xcodebuild -exportArchive \
  -archivePath build/LLMQuest.xcarchive \
  -exportPath build/LLMQuest-export \
  -exportOptionsPlist ios/export/ExportOptions.plist.template \
  -allowProvisioningUpdates
```

After Apple finishes processing the uploaded build, review the build details and
metadata in App Store Connect, then enable it for internal or external TestFlight
testing. External testing requires Beta App Review.

Apple recommends testing on the physical devices and OS versions you support before
distribution; simulator-only testing is not enough for TestFlight readiness.
