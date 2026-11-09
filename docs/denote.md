# Denote

[Package guides](README.md) | [Upstream](https://github.com/mbianchidev/denote)

## Install

The cask selects the published Intel or Apple silicon DMG:

```bash
brew install --cask mbianchidev/tap/denote
```

This installs `Denote.app` without launching it or changing existing notebooks.
The published 0.14.0 app declares macOS 10.13 as its minimum; Homebrew's supported
macOS versions and any upstream bundled-tool requirements still apply.

## First use and macOS security

Launch Denote yourself from Applications and follow the
[upstream guide](https://github.com/mbianchidev/denote#readme).
Existing notebooks and preferences remain outside the app bundle.

Current bundles are not Developer ID signed or notarized, and the 0.14.0 app
bundles do not pass complete macOS signature verification. Release-packaging
corrections are handled upstream. Updater signatures, published checksums and
GitHub provenance do not replace Apple app signing or notarization.
The cask retains quarantine and does not re-sign the installed app or disable
Gatekeeper. If macOS blocks first use, follow upstream security guidance rather
than removing system protections.

## Updates and removal

The tap checks stable releases hourly, verifies both DMGs and both published
macOS checksum manifests, and merges only release-field updates after native CI
and review guards pass. Denote's existing release workflow already publishes
these versioned assets automatically.

Denote supports its own updater, so use Homebrew's greedy mode for explicit
cask version tracking:

```bash
brew update
brew upgrade --cask --greedy mbianchidev/tap/denote
brew uninstall --cask mbianchidev/tap/denote
```

Uninstall removes the app without deleting notebooks, preferences or other user
data. See [release automation](maintaining.md#release-updates) for verification
and rollout details.
