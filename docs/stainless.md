# Stainless

[Package guides](README.md) | [Upstream](https://github.com/mbianchidev/stainless)

[Stainless](https://github.com/mbianchidev/stainless) is a Chromium-based
browser with Google's built-in services removed, for developers and
privacy-conscious people. Upstream publishes only preview prereleases. The cask
installs the newest checksummed `Stainless-<version>-macos-arm64.dmg` on Apple
silicon Macs. macOS 13 Ventura is the build's deployment target, not a tested
support matrix: upstream records the macOS versions each preview was verified on.
Intel and universal builds are not published.

## Install

```bash
brew install --cask mbianchidev/tap/stainless
```

This installs `Stainless.app` without launching it. Installation does not change
existing Stainless profiles, and Stainless never imports Chrome or Chromium data
implicitly.

## Preview limitations

Stainless is a preview. **Google Safe Browsing, phishing and download
reputation, and password-leak checks are removed with no replacement.**
Translation, cloud push and other Google-backed features are unavailable.
Read the upstream
[feature availability notes](https://github.com/mbianchidev/stainless/blob/main/docs/degoogling.md)
and [installation guide](https://github.com/mbianchidev/stainless/blob/main/docs/install-macos.md)
before browsing with it.

## macOS security

**Stainless is ad-hoc signed, not Developer ID signed or notarized.** Gatekeeper
blocks the first launch. The cask preserves quarantine and does not change macOS
security settings. Follow the [first launch steps](macos-security.md)
(System Settings or one Terminal command); do not disable Gatekeeper globally.

## Updates

The tap checks Stainless preview prereleases hourly and verifies the DMG against
its GitHub asset digest and the release's `SHA256SUMS` before publishing a
CI-gated update. See [release automation](maintaining.md#release-updates).

Quit Stainless before upgrading, since Homebrew replaces the app bundle:

```bash
brew update
brew upgrade --cask mbianchidev/tap/stainless
```

Stainless also has an opt-in built-in updater that needs a read-only GitHub
token (**Stainless Updates > Authorize Private Updates**). It replaces the app
outside Homebrew and its complete installed update path is still being verified
upstream, so the cask leaves updates to Homebrew and does not declare
`auto_updates`. Leave that updater unauthorized to keep the installed version
and Homebrew's record aligned. Homebrew upgrades do not take the built-in
updater's profile snapshots; back up `~/Library/Application Support/Stainless`
first if you want a rollback point.

## Removal

If you authorized the built-in updater, choose **Forget Update Authorization**
in the Stainless Updates menu first. Then:

```bash
brew uninstall --cask mbianchidev/tap/stainless
```

Uninstall removes the app and keeps your profiles, caches, updater backups and
Keychain items. To also move the Stainless data named in the upstream
[removal guide](https://github.com/mbianchidev/stainless/blob/main/docs/install-macos.md#remove-stainless)
to the Trash, use `--zap`:

```bash
brew uninstall --cask --zap mbianchidev/tap/stainless
```

| Path | Contents |
| --- | --- |
| `~/Library/Application Support/Stainless` | Default profile |
| `~/Library/Application Support/Stainless Profiles` | Managed profiles and their backups |
| `~/Library/Application Support/Stainless Updater` | Update lock and profile snapshots |
| `~/Library/Application Support/.Stainless.failed-profile-*` | Profiles kept after a failed update |
| `~/Library/Caches/Stainless` | Browser caches |
| `.Stainless.previous-*.app` in the app folder | Previous apps kept by the built-in updater |

Profiles, backups and snapshots hold plaintext browsing data. `--zap` does not
touch Chrome or Chromium data, and it does not delete the `Stainless Safe Storage`
Keychain item; remove that in Keychain Access once you no longer need the
encrypted cookies and passwords of a retained profile.
