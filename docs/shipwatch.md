# Shipwatch

[Package guides](README.md) | [Upstream](https://github.com/mbianchidev/shipwatch)

[Shipwatch](https://github.com/mbianchidev/shipwatch) is a menu bar app that
shows, for the GitHub repositories you pick, the latest release, Actions status,
last activity and open issues and pull requests. The cask installs the
checksummed, published universal DMG on Intel and Apple silicon Macs running
macOS 14 Sonoma or newer.

## Install

```bash
brew install --cask mbianchidev/tap/shipwatch
```

This installs `Shipwatch.app` without launching it. On first launch from the
app bundle, Shipwatch turns on its own launch at login, which you can switch
off in its Settings > General. Installation does not change GitHub, your
repositories or local clones.

## macOS security

**Shipwatch is ad-hoc signed, not Developer ID signed or notarized.** Gatekeeper
blocks the first launch. The cask preserves quarantine and does not change macOS
security settings. Follow the click-by-click [first launch steps](macos-security.md)
and the upstream
[installation guide](https://github.com/mbianchidev/shipwatch/blob/main/docs/installation.md);
do not disable Gatekeeper or remove quarantine.

## Updates and removal

The tap checks new stable releases hourly and verifies `Shipwatch.dmg` against
its GitHub asset digest and the published `Shipwatch.dmg.sha256` before
publishing a CI-gated update. See [release automation](maintaining.md#release-updates).

```bash
brew update
brew upgrade --cask --greedy mbianchidev/tap/shipwatch
brew uninstall --cask mbianchidev/tap/shipwatch
```

Shipwatch also has a signed built-in updater, so the cask declares
`auto_updates true` and `--greedy` is needed to upgrade it with Homebrew. Leave
**Install automatically** off in Shipwatch's Settings > General to keep the
installed version and Homebrew's record aligned.

Uninstall removes the app, not its preferences, the Keychain sign-in or update
state in `~/Library/Application Support/Shipwatch`. See the upstream
[uninstall steps](https://github.com/mbianchidev/shipwatch/blob/main/docs/installation.md#uninstall)
for a full removal.
