cask "denote" do
  version "1.1.0"

  on_arm do
    sha256 "70c3607e5d6f2edd251aa40b27a998f6b22811ddc215ae6d8fc02c00be88f83a"

    url "https://github.com/denote-io/denote/releases/download/v#{version}/Denote_#{version}_aarch64.dmg"
  end
  on_intel do
    sha256 "8bd7963a8386949b69ad9e1c75912f064907b86ebf264375080b4c45f6029481"

    url "https://github.com/denote-io/denote/releases/download/v#{version}/Denote_#{version}_x64.dmg"
  end

  name "Denote"
  desc "Native desktop notebook with Markdown and extensible tools"
  homepage "https://denote.synctune.it/"

  livecheck do
    url :url
    strategy :github_latest
  end

  auto_updates true
  depends_on :macos

  app "Denote.app"

  caveats do
    <<~EOS
      Denote is not Developer ID signed or notarized.
      This cask keeps quarantine, so macOS blocks the first launch.
      If you trust this tap, open Denote once:
        1. Double-click Denote in Applications, then click Done.
        2. Open System Settings > Privacy & Security.
        3. Under Security, click Open Anyway, then click Open.
      Or run this once in Terminal. It removes quarantine from this app
      only and skips macOS's first-launch malware check:
        xattr -d -r com.apple.quarantine "#{appdir}/Denote.app"
      Repeat after each upgrade.
      Installation does not start Denote or modify existing notebooks. Guide:
        https://github.com/mbianchidev/homebrew-tap/blob/main/docs/macos-security.md
    EOS
  end
end
