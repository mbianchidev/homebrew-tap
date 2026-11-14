cask "shipwatch" do
  version "0.0.2"
  sha256 "63d411f3af15d77d515ec0f8f62ed2701aebd7bd696396acdc8ae7466b1520ca"

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
