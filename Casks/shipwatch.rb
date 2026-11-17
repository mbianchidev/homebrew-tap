cask "shipwatch" do
  version "0.0.13"
  sha256 "19c9dcf207ad04b4cd4d6030e75f5a154c273a40e732698fc5db97a318104c49"

  url "https://github.com/mbianchidev/shipwatch/releases/download/v#{version}/Shipwatch.dmg"
  name "Shipwatch"
  desc "Menu bar app for GitHub releases, Actions status, issues and pull requests"
  homepage "https://github.com/mbianchidev/shipwatch"

  livecheck do
    url :url
    strategy :github_latest
  end

  auto_updates true
  depends_on macos: :sonoma

  app "Shipwatch.app"

  caveats do
    <<~EOS
      Shipwatch is ad-hoc signed, not Developer ID signed or notarized.
      This cask keeps quarantine, so macOS blocks the first launch.
      If you trust this tap, open Shipwatch once:
        1. Double-click Shipwatch in Applications, then click Done.
        2. Open System Settings > Privacy & Security.
        3. Under Security, click Open Anyway, then click Open.
      Or run this once in Terminal. It removes quarantine from this app
      only and skips macOS's first-launch malware check:
        xattr -d -r com.apple.quarantine "#{appdir}/Shipwatch.app"
      Repeat after each upgrade.
      Installation does not start Shipwatch. Guide:
        https://github.com/mbianchidev/homebrew-tap/blob/main/docs/macos-security.md

      Leave Shipwatch's "Install automatically" setting off for Homebrew version
      tracking. To update with Homebrew:
        brew upgrade --cask --greedy mbianchidev/tap/shipwatch
    EOS
  end
end
