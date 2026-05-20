# iOS TestFlight Build

This repo ships the Play experience as a small native iOS app in `ios/LLMQuest.xcodeproj`.
The app uses `WKWebView` and serves the bundled `site/` directory through the local
`lqb://app/` scheme, so the same static quest UI, quest engine, AI answer panels, and
media paths are used on iOS.

## Prerequisites

- Full Xcode, not Command Line Tools only.
- Apple Developer Program membership with App Store Connect access.
- A unique bundle id, for example `com.example.llmquest`.

Apple documents App Store Connect as the distribution method for TestFlight and the
App Store:

- https://help.apple.com/xcode/mac/current/en.lproj/dev31de635e5.html
- https://developer.apple.com/help/app-store-connect/manage-builds/upload-builds/

## Build Site Assets

```sh
pnpm run build
```

## Archive for TestFlight

Set the signing values for your account:

```sh
export APPLE_TEAM_ID=YOURTEAMID
export IOS_BUNDLE_ID=com.example.llmquest
```

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

After Apple finishes processing the uploaded build, enable it for internal or external
TestFlight testing in App Store Connect.
