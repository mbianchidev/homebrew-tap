# Porto

[Package guides](README.md) | [Upstream](https://github.com/mbianchidev/porto)

## Install

Porto supports Intel and Apple silicon Macs with macOS 13 or later. The cask
selects the matching published desktop DMG:

```bash
brew install --cask mbianchidev/tap/porto
```

This installs `Porto.app`, including its published bundled runtime. It does not
launch the app, start VMs or containers, register a daemon, or stop existing
Porto processes. The separately published standalone CLI is not installed by
this desktop cask.

## First use and macOS security

Launch Porto yourself from Applications and follow the
[upstream setup guidance](https://github.com/mbianchidev/porto#readme).
Runtime initialization and VM/container startup remain explicit user actions.

Current release bundles are not Developer ID signed or notarized, and the
1.8.1 app bundles do not pass complete macOS signature verification.
Release-packaging corrections are handled upstream; do not treat a matching
download checksum as proof of Developer ID signing or notarization.
The cask retains quarantine and does not re-sign downloaded apps, remove
Gatekeeper protections, or start a privileged helper. If macOS blocks first
use, follow upstream security guidance rather than disabling system protection.

## Updates and removal

The tap checks new stable releases hourly and verifies both architecture-specific
DMGs against GitHub asset digests and `SHA256SUMS` before publishing a CI-gated
update. See [release automation](maintaining.md#release-updates).

```bash
brew update
brew upgrade --cask mbianchidev/tap/porto
brew uninstall --cask mbianchidev/tap/porto
```

Uninstall removes the app, not existing configuration, VM disks or container
data. It does not stop existing runtime processes. Do not remove runtime data
or terminate a running environment as part of a package update.
