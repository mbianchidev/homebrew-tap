cask "shipwatch" do
  version "0.0.6"
  sha256 "c9c97587d907d1476d55144b23c43fcf1b1d40dbca057eb2dc689e027a6a5e4d"

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
      macOS Gatekeeper may block first use; this cask does not bypass that
      protection. Installation does not start Shipwatch.

      Leave Shipwatch's "Install automatically" setting off for Homebrew version
      tracking. To update with Homebrew:
        brew upgrade --cask --greedy mbianchidev/tap/shipwatch
    EOS
  end
end
