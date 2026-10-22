# sql-not-so-lite

[Documentation](README.md)

[sql-not-so-lite](https://github.com/mbianchidev/sql-not-so-lite) is a SQLite
daemon with a gRPC API and an embedded web GUI. The formula installs published
binaries with the React/Vite GUI already embedded in `sqnsl`. Go, Node.js and
source builds are not required.

## Install and verify

The package supports Intel and Apple silicon Macs and Linux x86_64/aarch64.
It is independent of Sendbox and its VM runtime.

```bash
brew install mbianchidev/tap/sql-not-so-lite
sqnsl version
sqnsl --help
```

These commands print the version and available commands. Installation never
starts the daemon or opens a browser.

## Configure and run

Configuration and databases live under `~/.sql-not-so-lite`; configuration is
`~/.sql-not-so-lite/config.toml`. The daemon scans your home directory by default.
Before starting, choose an explicit scan root if you want narrower discovery.

For a foreground daemon, set `SQNSL_SCAN_ROOT` to that directory when running
`sqnsl start`. For a Homebrew service, set `scan_root` in the configuration's
`[scanner]` section; do not assume your interactive shell's variables reach the
background service.

If no configuration exists, generate it without starting the daemon:

```bash
sqnsl config init
```

After reviewing the configuration, start in the foreground with `sqnsl start`,
or manage a user service:

```bash
brew services start mbianchidev/tap/sql-not-so-lite
brew services stop mbianchidev/tap/sql-not-so-lite
```

Run as your normal user, not with `sudo`. Do not also run `sqnsl install` when
using `brew services`. See the
[upstream documentation](https://github.com/mbianchidev/sql-not-so-lite#readme)
for API, GUI and configuration usage.

## Upgrades and removal

```bash
brew update
brew upgrade mbianchidev/tap/sql-not-so-lite
```

If running as a Homebrew service, restart it after upgrading:

```bash
brew services restart mbianchidev/tap/sql-not-so-lite
```

Stop a running user service before removing the package:

```bash
brew services stop mbianchidev/tap/sql-not-so-lite
brew uninstall mbianchidev/tap/sql-not-so-lite
```

Upgrading or uninstalling preserves configuration and databases under
`~/.sql-not-so-lite`.
