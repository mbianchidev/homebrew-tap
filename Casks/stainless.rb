cask "stainless" do
  version "0.1.0-preview.4"
  sha256 "53e158a6bc133929eacb6ce65729ebaf3ac2d1bb55173d5c0e10432ac90b1c51"

  url "https://github.com/mbianchidev/stainless/releases/download/stainless-preview-v#{version}/Stainless-#{version}-macos-arm64.dmg"
  name "Stainless"
  desc "Privacy-focused Chromium browser with Google's built-in services removed"
  homepage "https://github.com/mbianchidev/stainless"

  # Stainless publishes only GitHub prereleases, which `:github_latest` skips.
  livecheck do
    url :url
    regex(/^stainless-preview-v(\d+(?:\.\d+)+-preview\.\d+)$/i)
    strategy :github_releases do |json, regex|
      json.map do |release|
        next if release["draft"] || !release["prerelease"]

        match = release["tag_name"]&.match(regex)
        next if match.blank?

        match[1]
      end
    end
  end

  depends_on arch: :arm64
  depends_on macos: :ventura

  app "Stainless.app"

  zap trash: [
    "#{appdir}/.Stainless.previous-*.app",
    "~/Library/Application Support/.Stainless.failed-profile-*",
    "~/Library/Application Support/Stainless Profiles",
    "~/Library/Application Support/Stainless Updater",
    "~/Library/Application Support/Stainless",
    "~/Library/Caches/Stainless",
  ]

  caveats do
    <<~EOS
      Stainless is ad-hoc signed, not Developer ID signed or notarized.
      This cask keeps quarantine, so macOS blocks the first launch.
      If you trust this tap, open Stainless once:
        1. Double-click Stainless in Applications, then click Done.
        2. Open System Settings > Privacy & Security.
        3. Under Security, click Open Anyway, then click Open.
      Or run this once in Terminal. It removes quarantine from this app
      only and skips macOS's first-launch malware check:
        xattr -d -r com.apple.quarantine "#{appdir}/Stainless.app"
      Repeat after each upgrade.
      Installation does not start Stainless or change existing profiles. Guide:
        https://github.com/mbianchidev/homebrew-tap/blob/main/docs/macos-security.md

      Stainless is a preview. Google Safe Browsing, phishing and download
      reputation, and password-leak checks are removed with no replacement:
        https://github.com/mbianchidev/homebrew-tap/blob/main/docs/stainless.md

      Leave the opt-in built-in updater unauthorized for Homebrew version
      tracking. Quit Stainless, then update with Homebrew:
        brew upgrade --cask mbianchidev/tap/stainless
    EOS
  end
end
