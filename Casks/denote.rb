cask "denote" do
  version "1.1.1"

  on_arm do
    sha256 "6a30104ba234b381d077ec790c0eb6ced19f68739b8ecd1ae34d37b2b1cb8e91"

    url "https://github.com/denote-io/denote/releases/download/v#{version}/Denote_#{version}_aarch64.dmg"
  end
  on_intel do
    sha256 "c7b99ee8598ebb700781c699ecac21406749fa0de5fdb329cc8ca88d0e042485"

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
