cask "denote" do
  version "0.14.3"

  on_arm do
    sha256 "c2a992f97f336bd107af78286617b4f0e0be963230979283b0091704f865ae43"

    url "https://github.com/denote-io/denote/releases/download/v#{version}/Denote_#{version}_aarch64.dmg"
  end
  on_intel do
    sha256 "d2f3c6a3957d4aa1faffc575a1e5fcdd94c0cdfd75080c07f7b798b730e38645"

    url "https://github.com/denote-io/denote/releases/download/v#{version}/Denote_#{version}_x64.dmg"
  end

  name "Denote"
  desc "Native desktop notebook with Markdown and extensible tools"
  homepage "https://github.com/denote-io/denote"

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
