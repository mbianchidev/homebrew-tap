cask "shipwatch" do
  version "0.0.10"
  sha256 "95b3d469529be8077983ea3c84a674330772c03dd2298d35d79fa7debeffe31d"

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
