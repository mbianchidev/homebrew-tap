cask "porto" do
  version "1.11.6"

  on_arm do
    sha256 "bad6fd8666240b68f84046c9ffc69606a260b557dafb20b01d6146efe2cc72fc"

    url "https://github.com/porto-containers/porto/releases/download/v#{version}/porto-desktop_#{version}_darwin_arm64.dmg"
  end
  on_intel do
    sha256 "5b29b3d820ed95d1daf5db74e2e5298fdf62b140c2e9fc0be27bad236634d3cf"

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
