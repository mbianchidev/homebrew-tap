cask "porto" do
  version "1.10.0"

  on_arm do
    sha256 "4b5fefea4e0bf8f75dab96b671102402b1886844a07de8ff5b1320ead35babcd"

    url "https://github.com/mbianchidev/porto/releases/download/v#{version}/porto-desktop_#{version}_darwin_arm64.dmg"
  end
  on_intel do
    sha256 "b64b274acc53cb02e3001f107599633a0d329aacab11c134185c9aa8368af267"

    url "https://github.com/mbianchidev/porto/releases/download/v#{version}/porto-desktop_#{version}_darwin_amd64.dmg"
  end

  name "Porto"
  desc "Desktop orchestrator for local containers, apps, and homelabs"
  homepage "https://github.com/mbianchidev/porto"

  livecheck do
    url :url
    strategy :github_latest
  end

  depends_on macos: :ventura

  app "Porto.app"

  caveats do
    <<~EOS
      Porto is not Developer ID signed or notarized. macOS Gatekeeper may
      block first use; this cask preserves quarantine and does not bypass it.
      Installation does not start Porto, containers, VMs, or daemons.
    EOS
  end
end
