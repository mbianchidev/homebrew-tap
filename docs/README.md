# Documentation

[Tap README](../README.md)

This tap packages independent projects using published release artifacts.
Start with the [tap quickstart](../README.md#quickstart), then choose a package
guide. Installing a package does not start its application or runtime.

## Packages

| Guide | Purpose | Supported platforms |
| --- | --- | --- |
| [Sendbox](sendbox.md) | CLI and signed payload for policy-controlled coding-agent VMs | CLI: Apple silicon, macOS 15+; Linux x86_64/aarch64. VM runtime requirements are separate. |
| [sql-not-so-lite](sql-not-so-lite.md) | SQLite daemon with gRPC and an embedded web GUI | Intel/Apple silicon Macs; Linux x86_64/aarch64. |
| [KillSwitch](killswitch.md) | Menu bar app and `killswitchctl` process-management CLI | Intel/Apple silicon Macs, macOS 13+. |

Each guide covers installation, first use, relevant configuration, upgrades,
removal and upstream documentation. Package versions and checksums are defined
in [`Formula/`](../Formula) and [`Casks/`](../Casks).

## Maintainers and contributors

The [maintainer guide](maintaining.md) covers repository layout, safe local
checks, hosted lifecycle tests, package changes and release automation.
