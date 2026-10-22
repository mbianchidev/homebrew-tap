# KillSwitch

[Documentation](README.md)

[KillSwitch](https://github.com/mbianchidev/kill-switch) is a macOS menu bar app
for process management and developer cleanup. The cask installs a checksummed,
published universal DMG on Intel and Apple silicon Macs running macOS 13 Ventura
or newer. No compiler or source build is required.

## Install and verify

```bash
brew install --cask mbianchidev/tap/killswitch
brew list --cask --versions mbianchidev/tap/killswitch
```

The second command lists the installed cask version without launching the app.
Use the fully qualified `--cask` command: Homebrew/core also has an unrelated VPN
formula named `killswitch`.

Homebrew installs `KillSwitch.app` and links its bundled executable as
`killswitchctl`, the invocation name that selects headless CLI mode. The link
follows a custom application directory without a manual symlink:

```bash
brew install --cask --appdir="$HOME/Applications" mbianchidev/tap/killswitch
```

Choose the default or custom-directory installation, not both. Installation
does not launch the app, run the CLI or register a service.

## macOS security

**KillSwitch is ad-hoc signed, not Developer ID signed or notarized.** Gatekeeper
may block the app or its CLI on first use. The cask preserves quarantine and
does not change macOS security settings.

For a download you have verified and decided to trust, Apple's
[safe app-opening guidance](https://support.apple.com/en-us/102445)
describes a per-app exception: after trying to open the app, go to
**System Settings > Privacy & Security > Open Anyway**, then confirm only if you
are certain of its source and integrity. Managed devices may not allow this.
Do not override malware warnings, disable Gatekeeper globally or remove
quarantine to make the app run.

After macOS permits the app, open it from your chosen Applications directory.
Review the upstream [CLI guide](https://github.com/mbianchidev/kill-switch/blob/main/docs/cli.md)
before using cleanup or process-management commands. The bundled CLI remains
subject to macOS security checks.

## Upgrades and removal

```bash
brew update
brew upgrade --cask --greedy mbianchidev/tap/killswitch
brew uninstall --cask mbianchidev/tap/killswitch
```

The app has an opt-in built-in updater, so the cask declares `auto_updates true`.
Leave automatic installation off when using Homebrew to keep the installed
version and Homebrew receipt aligned. `--greedy` includes auto-updating casks in
Homebrew upgrades.

The cask does not run upstream install, update or uninstall scripts, quit
running apps, or remove preferences, application data or launch agents.
See the upstream [installation guide](https://github.com/mbianchidev/kill-switch/blob/main/docs/installation.md)
for application-specific setup and troubleshooting.
