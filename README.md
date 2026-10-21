# Homebrew tap

Homebrew formulas for mbianchidev tools.

## sql-not-so-lite

```bash
brew install mbianchidev/tap/sql-not-so-lite
sqnsl start
```

The formula is added automatically by the first packaged stable release of
[sql-not-so-lite](https://github.com/mbianchidev/sql-not-so-lite). Earlier
source-only releases do not provide an installable formula.

The formula supports macOS and Linux on ARM64 and AMD64. It installs a
precompiled binary with the web GUI embedded; Go and Node.js are not required.

To run the daemon as a user service instead of in the foreground:

```bash
brew services start mbianchidev/tap/sql-not-so-lite
brew services stop mbianchidev/tap/sql-not-so-lite
```

Do not use `sudo` or also run `sqnsl install`. Configuration and databases stay
under `~/.sql-not-so-lite` and are preserved when upgrading or uninstalling.

```bash
brew update
brew upgrade mbianchidev/tap/sql-not-so-lite
brew services restart mbianchidev/tap/sql-not-so-lite
```

## Maintainers

Stable version tags in the source repository generate `Formula/sql-not-so-lite.rb`
from published release checksums. A write-scoped deploy key updates this tap;
no account-wide personal access token is required. Do not commit placeholder
hashes or links to unpublished artifacts. Prereleases do not replace the stable
formula.

The formula workflow installs and tests releases on Intel and ARM Macs.
