cask "porto" do
  version "1.8.1"

  on_arm do
    sha256 "edf6587ffa6568d8b0ffa62d4729c657802c06560bc3792307056de73b67c6b7"

    url "https://github.com/mbianchidev/porto/releases/download/v1.8.1/porto-desktop_1.8.1_darwin_arm64.dmg"
  end
  on_intel do
    sha256 "7044bd4d51633515e21540a1fd3105576ae9990ade11ba611df01767d547795e"

    url "https://github.com/mbianchidev/porto/releases/download/v1.8.1/porto-desktop_1.8.1_darwin_amd64.dmg"
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
