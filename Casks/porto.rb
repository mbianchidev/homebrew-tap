cask "porto" do
  version "1.11.7"

  on_arm do
    sha256 "3c175fbb71b73311d872c24accf25e740e7a0ffcaa5d836392cb4fd6f1732e04"

    url "https://github.com/porto-containers/porto/releases/download/v#{version}/porto-desktop_#{version}_darwin_arm64.dmg"
  end
  on_intel do
    sha256 "72902a43e161e9dc22821d2e2cffdf7cd67f6d0e1f2ae3e21628af2774f92361"

    url "https://github.com/porto-containers/porto/releases/download/v#{version}/porto-desktop_#{version}_darwin_amd64.dmg"
  end

  name "Porto"
  desc "Desktop orchestrator for local containers, apps, and homelabs"
  homepage "https://porto.synctune.it/"

  livecheck do
    url :url
    strategy :github_latest
  end

  auto_updates true
  depends_on macos: :ventura

  app "Porto.app"

  caveats do
    <<~EOS
      Porto is not Developer ID signed or notarized.
      This cask keeps quarantine, so macOS blocks the first launch.
      If you trust this tap, open Porto once:
        1. Double-click Porto in Applications, then click Done.
        2. Open System Settings > Privacy & Security.
        3. Under Security, click Open Anyway, then click Open.
      Or run this once in Terminal. It removes quarantine from this app
      only and skips macOS's first-launch malware check:
        xattr -d -r com.apple.quarantine "#{appdir}/Porto.app"
      Repeat after each upgrade.
      Installation does not start Porto, containers, VMs, or daemons. Guide:
        https://github.com/mbianchidev/homebrew-tap/blob/main/docs/macos-security.md

      Leave Porto's "Automatically download new Porto versions" setting off
      for Homebrew version tracking. To update with Homebrew:
        brew upgrade --cask --greedy mbianchidev/tap/porto
    EOS
  end
end
