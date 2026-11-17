cask "denote" do
  version "0.14.2"

  on_arm do
    sha256 "5bc8c882bee14171e92bf60ffb3fc086b27d43a95ac6391eec28bdcb28b6d0d8"

    url "https://github.com/mbianchidev/denote/releases/download/v#{version}/Denote_#{version}_aarch64.dmg"
  end
  on_intel do
    sha256 "e2399c5a451d584df761376d2c6db99fa670a90ba1a3ad0e183c55161ae907d4"

    url "https://github.com/mbianchidev/denote/releases/download/v#{version}/Denote_#{version}_x64.dmg"
  end

  name "Denote"
  desc "Native desktop notebook with Markdown and extensible tools"
  homepage "https://denote.mbianchi.dev/"

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
