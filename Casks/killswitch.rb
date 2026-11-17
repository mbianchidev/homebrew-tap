cask "killswitch" do
  version "1.1.40"
  sha256 "622f916dfefd63e840208cdb25818832fd3b78d5d29ac371eac05140f7ad0491"

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
      This cask keeps quarantine, so macOS blocks the first launch.
      If you trust this tap, open KillSwitch once:
        1. Double-click KillSwitch in Applications, then click Done.
        2. Open System Settings > Privacy & Security.
        3. Under Security, click Open Anyway, then click Open.
      Or run this once in Terminal. It removes quarantine from this app
      only and skips macOS's first-launch malware check:
        xattr -d -r com.apple.quarantine "#{appdir}/KillSwitch.app"
      Repeat after each upgrade.
      Approve the app before using killswitchctl. Neither the app nor the
      CLI is started at install. Guide:
        https://github.com/mbianchidev/homebrew-tap/blob/main/docs/macos-security.md

      Leave the opt-in built-in auto-installer off for Homebrew version tracking.
      To update with Homebrew:
        brew upgrade --cask --greedy mbianchidev/tap/killswitch
    EOS
  end
end
