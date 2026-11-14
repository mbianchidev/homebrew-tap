cask "porto" do
  version "1.9.0"

  on_arm do
    sha256 "5e1a1597decacd8063904d86dbf8489936fe6283b8bfcc3cf8549044f50c1794"

    url "https://github.com/mbianchidev/porto/releases/download/v#{version}/porto-desktop_#{version}_darwin_arm64.dmg"
  end
  on_intel do
    sha256 "47ac756a28345ac69c7d4bab3229caa89492d359afcce7645e6b5e2609ef2fa5"

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
