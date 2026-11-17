# First launch on macOS

[Documentation](README.md)

KillSwitch, Porto, Denote and Shipwatch are not Developer ID signed or notarized
by Apple. Homebrew checks each download against its published checksum and keeps
the macOS quarantine flag, so the first launch is blocked with a warning such as
"Apple could not verify the app is free of malware".

The tap does not remove quarantine for you. Removing it would also skip the
Gatekeeper check and the XProtect malware scan that macOS runs on first launch,
for everyone who installs from this tap.

## Open the app the first time

Only continue if you trust this tap and the upstream project.

1. In Finder, open **Applications** (or the folder you passed to `--appdir`)
   and double-click the app.
2. macOS shows a warning. Click **Done**. Do not click **Move to Trash**.
3. Open **System Settings** from the Apple menu and click
   **Privacy & Security**.
4. Scroll down to **Security**. Next to the message that the app was blocked,
   click **Open Anyway**.
5. Enter your password or use Touch ID if macOS asks.
6. The warning appears again. Click **Open**.

macOS saves the app as an exception, so later launches work normally. A Homebrew
upgrade installs a new quarantined copy; repeat these steps if macOS blocks the
new version.

KillSwitch's `killswitchctl` command runs the same executable as the app.
Approve the app first; if macOS still blocks the command, approve it the same
way from **Privacy & Security**.

Apple describes these steps in
[Safely open apps on your Mac](https://support.apple.com/en-us/102445).

## When not to continue

- If macOS says the app is damaged or contains malware, click
  **Move to Trash** and report it to the upstream project.
- If **Open Anyway** is missing, your Mac may be managed by an organization;
  ask your administrator.
- Do not disable Gatekeeper or remove quarantine with `xattr`.
