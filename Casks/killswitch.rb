cask "killswitch" do
  version "1.1.32"
  sha256 "ee2384546e07a4e1706e130894f3dddb6f8c5ed99f10e2bce4bd3628ecd98a3c"

  url "https://github.com/mbianchidev/kill-switch/releases/download/v#{version}/KillSwitch.dmg"
  name "KillSwitch"
  desc "Menu bar utility for managing processes and developer cleanup"
  homepage "https://github.com/mbianchidev/kill-switch"

  livecheck do
    url :url
    strategy :github_latest
  end

  auto_updates true
  depends_on macos: :ventura

  app "KillSwitch.app"
  binary "#{appdir}/KillSwitch.app/Contents/MacOS/KillSwitch", target: "killswitchctl"

  caveats do
    <<~EOS
      KillSwitch is ad-hoc signed, not Developer ID signed or notarized.
      macOS Gatekeeper may block the app or killswitchctl; this cask does not
      bypass that protection. Neither the app nor the CLI is started at install.

      Leave the opt-in built-in auto-installer off for Homebrew version tracking.
      To update with Homebrew:
        brew upgrade --cask --greedy mbianchidev/tap/killswitch
    EOS
  end
end
