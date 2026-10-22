# Homebrew tap

[Documentation](docs/README.md) | [Maintainer guide](docs/maintaining.md)

Homebrew formulas and casks for [mbianchidev](https://github.com/mbianchidev)
projects.

[Quickstart](#quickstart) | [Packages](#packages) | [Documentation](#documentation) |
[AI policy](#ai-policy) | [Contributing](#contributing) | [License](#license)

## Quickstart

With [Homebrew](https://brew.sh) installed:

```bash
brew tap mbianchidev/tap
brew trust mbianchidev/tap
brew search mbianchidev/tap/
```

Packages use checksummed upstream releases, without building their applications
from source. Installation does not launch apps, services, VMs, or agents.
Check each package guide for supported platforms and any separate runtime setup.

## Packages

| Package | Purpose | Install |
| --- | --- | --- |
| [Sendbox](docs/sendbox.md) | CLI for policy-controlled coding-agent VMs | `brew install mbianchidev/tap/sendbox` |
| [sql-not-so-lite](docs/sql-not-so-lite.md) | SQLite daemon with an embedded web GUI | `brew install mbianchidev/tap/sql-not-so-lite` |
| [KillSwitch](docs/killswitch.md) | macOS process-management app and CLI | `brew install --cask mbianchidev/tap/killswitch` |

KillSwitch is not notarized. Read its [macOS security guidance](docs/killswitch.md#macos-security)
before first use; the cask preserves quarantine and Gatekeeper protections.

## Documentation

- [Package guides](docs/README.md): platforms, configuration, upgrades and removal.
- [Maintainer guide](docs/maintaining.md): package definitions, checks and release updates.

## AI policy

You are responsible for everything you contribute, including AI-assisted work.
Review and test it, and be able to explain what it does and why it is needed.

## Contributing

See the [package change workflow](docs/maintaining.md#package-changes).

## License

Tap metadata is [MIT licensed](LICENSE). Packages retain their upstream licenses.
