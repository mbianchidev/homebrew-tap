cask "killswitch" do
  version "1.1.34"
  sha256 "4909a5718e6e20513ce23bdf1c785a655c2b4e731d51d21b28fd04b752520cb2"

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
