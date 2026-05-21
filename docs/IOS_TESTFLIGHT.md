# iOS TestFlight Build

This repo ships the Play experience as a small native iOS app in `ios/LLMQuest.xcodeproj`.
The app uses `WKWebView` and serves a staged `site/` bundle through the local
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
- https://developer.apple.com/help/app-store-connect/test-a-beta-version/provide-test-information/
- https://developer.apple.com/help/app-store-connect/manage-app-information/manage-app-privacy/
- https://developer.apple.com/help/app-store-connect/test-a-beta-version/invite-external-testers/

## Build Site Assets

```sh
pnpm run build
```

The Xcode target then stages only the Play runtime payload into the app bundle:
`play.html`, compiled JavaScript, quest archives, generated cohort JSON, frame
media, and vendored runtime files. It does not bundle benchmark trace pages,
ignored local trace artifacts, or source-only files such as `app.jsx` and
`engine-entry.ts`. The staging script copies from
`ios/LLMQuest/StageSiteInputs.xcfilelist`, which declares the exact inputs for
Xcode's script-phase dependency tracking and sandboxed file access.

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

The project starts at marketing version 1.0 and build number 1. Before each
upload, bump the Xcode build number (`CURRENT_PROJECT_VERSION`) so App Store
Connect can distinguish the new build for the same `MARKETING_VERSION`.
The app declares `ITSAppUsesNonExemptEncryption` as false because it does not
ship custom or non-exempt encryption code.
The app also bundles `PrivacyInfo.xcprivacy`, declaring no tracking, no collected
data, and the required-reason file timestamp access used while serving bundled
local quest assets.
The local browser runtime files under `site/play/vendor/` are included in the
iOS app bundle for offline TestFlight execution; keep their `NOTICE.md` file with
the vendored assets.

Before inviting testers, complete the App Store Connect metadata that is not stored
in the Xcode project:

- App Privacy: set the privacy policy URL for the iOS app. Apple requires a
  privacy policy URL for all apps. The current app-side privacy manifest declares
  no tracking and no collected data; keep the App Store Connect privacy responses
  aligned with that behavior unless the app starts collecting data.
- Export Compliance: the app declares `ITSAppUsesNonExemptEncryption=false` in
  `Info.plist`, which should prevent each TestFlight build from being marked as
  missing compliance. If App Store Connect still prompts for export compliance,
  answer that the app does not use encryption or is exempt from documentation.
- Beta App Review Information: provide the required review contact name, phone
  number, and email address in App Store Connect. This app does not require
  sign-in or a demo account; mention that in the review notes if the field is
  available.

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

For external TestFlight testing, fill in App Store Connect > TestFlight >
Test Information before inviting testers:

- Beta App Description: `LLM Quest is a beta iOS wrapper for the LLM Quest
  Benchmark Play experience. Please load the quest list, start a quest, make at
  least two choices, and confirm the AI answer panels, quest text, and media load
  correctly.`
- Feedback Email: use the project support address for TestFlight replies. Do not
  commit personal App Store Connect contact details to the repo.
- What to Test: `Open the quest list, start Bad Day or another short quest, make
  at least two choices, and report whether quest text, images, audio, and AI
  answer panels load correctly on your device.`
- Review Notes: `No sign-in or demo account is required. The app is a bundled
  WKWebView wrapper around the static LLM Quest Benchmark Play experience. Start
  from the quest list, choose Bad Day, and make two choices to reach the AI answer
  comparison panel.`

Apple recommends testing on the physical devices and OS versions you support before
distribution; simulator-only testing is not enough for TestFlight readiness.
