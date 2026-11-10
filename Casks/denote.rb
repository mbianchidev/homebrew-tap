cask "denote" do
  version "0.14.1"

  on_arm do
    sha256 "cf8b7a42afdf0ed19f1e34d07765289d3df8ff11a47a5a8f2b4ef907642863f0"

    url "https://github.com/mbianchidev/denote/releases/download/v#{version}/Denote_#{version}_aarch64.dmg"
  end
  on_intel do
    sha256 "4d96c8423756a677a8b376cdbf2b185b192a1d1048f712e4fa8f10ebfd995dc3"

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
      Denote is not Developer ID signed or notarized. macOS Gatekeeper may
      block first use; this cask preserves quarantine and does not bypass it.
      Installation does not start Denote or modify existing notebooks.
    EOS
  end
end
