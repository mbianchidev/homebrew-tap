cask "porto" do
  version "1.8.2"

  on_arm do
    sha256 "4ba7d38ec8a85fcc29f66b5feaebdae5a07e6e92a410095eeb28e11990d58c0b"

    url "https://github.com/mbianchidev/porto/releases/download/v#{version}/porto-desktop_#{version}_darwin_arm64.dmg"
  end
  on_intel do
    sha256 "29dfbf5ab0da52971aa68069ba1d6fc4334316edc365a345bf671517ecfe83a7"

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
      Porto is not Developer ID signed or notarized. macOS Gatekeeper may
      block first use; this cask preserves quarantine and does not bypass it.
      Installation does not start Porto, containers, VMs, or daemons.
    EOS
  end
end
