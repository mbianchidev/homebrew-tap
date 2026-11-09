cask "denote" do
  version "0.14.0"

  on_arm do
    sha256 "9ab426f1f341b4aeb29f2b406588b073c83293f795e93302f6f473fadfbec1a3"

    url "https://github.com/mbianchidev/denote/releases/download/v#{version}/Denote_#{version}_aarch64.dmg"
  end
  on_intel do
    sha256 "555337fb34f7e109a1a4ae6b45264c3b0e68c0a5a1d833242f519c9a54c2ca3e"

    url "https://github.com/mbianchidev/denote/releases/download/v#{version}/Denote_#{version}_x64.dmg"
  end

  name "Denote"
  desc "Native desktop notebook with Markdown and extensible tools"
  homepage "https://github.com/mbianchidev/denote"

  livecheck do
    url :url
    strategy :github_latest
  end

  auto_updates true
  depends_on :macos

  app "Denote.app"

  caveats do
    <<~EOS
      Denote is not Developer ID signed or notarized. macOS Gatekeeper may
      block first use; this cask preserves quarantine and does not bypass it.
      Installation does not start Denote or modify existing notebooks.
    EOS
  end
end
