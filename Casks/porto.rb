cask "porto" do
  version "1.10.1"

  on_arm do
    sha256 "14c16d6bc581064fba2388c09b677810f778baa56425b22d67986d57d18992d8"

    url "https://github.com/mbianchidev/porto/releases/download/v#{version}/porto-desktop_#{version}_darwin_arm64.dmg"
  end
  on_intel do
    sha256 "bfd36c1fb6a84793e619495f51aa786354e31ca6c43dda014dc88a5ea623f51c"

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
    EOS
  end
end
