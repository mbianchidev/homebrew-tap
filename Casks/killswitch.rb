cask "killswitch" do
  version "1.1.33"
  sha256 "fddbc25f454f6be0a02e94bd1c24d5a8472677e85b38e65cf187b052d3f83bc5"

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
