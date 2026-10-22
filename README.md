# Homebrew tap

Homebrew formulas and casks for [mbianchidev](https://github.com/mbianchidev)
projects. Packages are independent: a project does not need its first release
before other packages can be installed or tested.

```bash
brew tap mbianchidev/tap
brew trust mbianchidev/tap
brew search mbianchidev/tap/
```

## Sendbox

> The formula targets verified stable **v0.2.3**, including the required TLS
> dependency fixes. The bootstrap package becomes available after human review
> and merge; no merge or runtime activation is automatic.

[Sendbox](https://github.com/mbianchidev/sendbox) is a Rust CLI for running coding
agents in policy-controlled Linux VMs. The formula installs verified published
host binaries, configuration examples, setup helper, and the matching signed
guest payload. No Rust compiler, frontend build, VM, agent, or service is started.

After the tap bootstrap PR is merged:

```bash
brew install mbianchidev/tap/sendbox
sendbox --version
sendbox --help
```

The CLI supports Apple silicon on macOS 15+ and Linux x86_64/aarch64.
There is no published Intel macOS binary. Linux native libraries and the ELF
loader are supplied by Homebrew, not assumed to be installed by `apt`.

**Installing the CLI does not configure a VM runtime.** macOS VM sessions require
Apple silicon, macOS 26+, and Apple `container` CLI 0.10.0. Linux VM sessions
require hardware/nested virtualization and a configured Kata/containerd/nerdctl
runtime. See the upstream
[installation guide](https://github.com/mbianchidev/sendbox/blob/main/docs/installation.md#homebrew)
and [runtime documentation](https://github.com/mbianchidev/sendbox#quick-start).

The complete release payload is under `$(brew --prefix sendbox)/libexec`.
Homebrew directories are user-owned: **do not pass this guest directory directly
to `sendbox run`**. Follow the upstream guide to verify and copy the matching
guest bundle and trust root to `/opt/sendbox/<version>/guest/<architecture>`,
with root-owned, non-writable ancestors, `0555` guest executables and `0444`
metadata/trust roots. Staging is an explicit administrator action, never a
formula postinstall step. Run the CLI as your normal user, not with `sudo`.

```bash
brew update
brew upgrade mbianchidev/tap/sendbox
# Explicitly stage the new matching guest payload before launching that version.
brew uninstall mbianchidev/tap/sendbox
```

Upgrades and removal preserve `~/.sendbox/`, project `.sendbox.yaml` files, and
separately staged root-owned runtime bundles. Homebrew removes only its package;
retire old runtime bundles explicitly when no longer needed. Do not run the
bundled `setup.sh` just to install or smoke-test the CLI: it performs runtime
preflight and can offer additional installation steps.

## sql-not-so-lite

[sql-not-so-lite](https://github.com/mbianchidev/sql-not-so-lite) is an independent
SQLite daemon with a gRPC API and embedded web GUI. Its actual formula is included
in this tap alongside Sendbox; it does not depend on Sendbox or its runtime.

```bash
brew install mbianchidev/tap/sql-not-so-lite
sqnsl version
sqnsl start
```

The formula installs checksummed, published v0.0.3 binaries with the React/Vite
GUI already embedded in `sqnsl`. Go and Node.js are not required at installation
or runtime, and no frontend or native source build is performed by the tap.
The formula and its GUI are checked on Intel/ARM Macs and Linux x86_64/aarch64.
Installation never starts the daemon or opens a browser.

To run the daemon as a user service instead of in the foreground:

```bash
brew services start mbianchidev/tap/sql-not-so-lite
brew services stop mbianchidev/tap/sql-not-so-lite
```

Do not use `sudo` or also run `sqnsl install`. Configuration and databases stay
under `~/.sql-not-so-lite` and are preserved when upgrading or uninstalling.
The default daemon scans your home directory. Set `SQNSL_SCAN_ROOT` before starting
to limit discovery to an explicit directory; configuration is
`~/.sql-not-so-lite/config.toml`.

```bash
brew update
brew upgrade mbianchidev/tap/sql-not-so-lite
brew services restart mbianchidev/tap/sql-not-so-lite
```

## KillSwitch

[KillSwitch](https://github.com/mbianchidev/kill-switch) is a macOS menu bar app
for process management and developer cleanup. The `killswitch` cask installs the
checksummed, published universal **v1.1.28** DMG on Intel and Apple silicon Macs
running macOS 13 Ventura or newer. No compiler or source build is required.

After this cask is reviewed and merged:

```bash
brew install --cask mbianchidev/tap/killswitch
```

Homebrew installs `KillSwitch.app` and links its bundled executable as
`killswitchctl`, the invocation name that selects headless CLI mode. The link
follows `--appdir` when using a custom application directory; no manual symlink is
needed. Installation does not launch the app, run the CLI, or register a service.
See the upstream [CLI guide](https://github.com/mbianchidev/kill-switch/blob/main/docs/cli.md)
before using cleanup or process-management commands.

**The app is ad-hoc signed, not Developer ID signed or notarized.** Gatekeeper
may block the app or CLI on first use. The cask preserves quarantine and does not
bypass macOS protections. Review the upstream
[installation guidance](https://github.com/mbianchidev/kill-switch/blob/main/docs/installation.md)
before deciding whether to allow it.

```bash
brew update
brew upgrade --cask --greedy mbianchidev/tap/killswitch
brew uninstall --cask mbianchidev/tap/killswitch
```

The app has an opt-in built-in updater, so the cask declares `auto_updates true`.
Leave its automatic installation option off when using Homebrew to keep the
installed version and Homebrew receipt aligned. `--greedy` includes auto-updating
casks in Homebrew upgrades. GitHub latest livecheck discovers new stable
releases; maintainers review version/checksum updates. The cask does not run
upstream install, update, or uninstall scripts, quit running apps, or remove
preferences, application data, or launch agents.

## Maintainers

Package definitions live in `Formula/` and `Casks/`. CI discovers both directories,
accepts an empty tap, checks syntax/style, strict online cask audits and all
platform definitions, and tests
the checked-out event revision rather than the remote default branch. Compatible
packages are installed and removed on disposable Intel/ARM Mac and Linux
x86_64/aarch64 GitHub runners. Casks are not launched. Sendbox additionally checks
release checksums/provenance, real previous-stable-to-current `brew upgrade`,
CLI startup/version/configuration/completions, Linux linkage, unchanged signed
guest bytes, and preservation of mocked user/project data. No VM or agent is
started. The Sendbox and sql-not-so-lite lifecycle checks require disposable
GitHub-hosted runners, not the maintainer's laptop.
Sendbox init/policy fixture writes run outside Homebrew's restrictive test
sandbox; its `brew test` uses read-only CLI commands.
sql-not-so-lite additionally verifies and serves its embedded GUI on localhost,
creates a mock SQLite database, stops the temporary daemon, and verifies package
removal preserves the configuration and database bytes. Its scan root and home
are temporary fixtures, never the runner's real home or the maintainer's data.

KillSwitch additionally verifies the versioned DMG against GitHub's asset digest
and the published adjacent checksum. Its lifecycle check uses the real Homebrew
cask installer with process-local disposable Caskroom, binary and custom
application directories. It checks the universal app, CLI symlink, code
signature, retained quarantine, uninstall and mocked user-data preservation.
Neither the GUI nor CLI is executed; no Gatekeeper protection is bypassed.
The isolated check can also be run locally:

```bash
ruby tests/test_killswitch_cask.rb
ruby scripts/ci/killswitch.rb Casks/killswitch.rb
```

Draft PRs intentionally run package CI. Obsolete runs are canceled; package
downloads and Homebrew's locked style/audit dependencies are cached by OS/architecture.
Builds use two workers where available. Published binaries are reused without
rebuilding Sendbox or sql-not-so-lite. Credentials are not cached. There is no historical
tap CI baseline yet, so runtime savings are not claimed.
Sendbox's updater requires an explicit version before its interpolated default
URL so metadata remains loadable on unsupported Intel Macs. Only the stanza
ordering style rule is excepted for that formula; all other style checks and
cross-platform definition validation remain enabled.

Sendbox stable-release automation verifies published artifacts in its source
repository, updates only the formula's version and three checksums, and uses its
dedicated tap-scoped SSH deploy key to push `automation/sendbox-vX.Y.Z`.
This tap validates the branch before opening an idempotent **draft** PR with its
own `GITHUB_TOKEN`. Only strict stable versions and changes to those formula
fields qualify. Prereleases cannot replace the stable package. Existing PRs,
including closed ones, are not duplicated. Humans review and merge; automation
never pushes to `main` or merges. Subsequent automation-branch pushes are
validated by push CI rather than duplicate PR runs.

**Sendbox v0.2.3 includes the upstream TLS dependency fixes for**
[RUSTSEC-2026-0382](https://rustsec.org/advisories/RUSTSEC-2026-0382.html) and
[RUSTSEC-2026-0383](https://rustsec.org/advisories/RUSTSEC-2026-0383.html).
Its published archives and tag-bound provenance have been verified. Versions at
or below v0.2.2 remain excluded from automated activation. The source update
workflow is merged, but passing lifecycle CI and human merge of the tap bootstrap
PR are still required before this package and tap-side automation become active.

For future automated draft PRs, keep **Allow GitHub Actions to create and approve
pull requests** enabled in this tap's Settings > Actions > General > Workflow
permissions. It is currently enabled. Automation reports an actionable failure
and leaves the validated update branch available for a manually opened draft if
that permission is missing. Do not enable auto-merge or widen the token's
repository permissions.

Other projects keep their own release tooling and dedicated deploy keys. The
existing sql-not-so-lite key and formula are independent of Sendbox.
Do not commit placeholder hashes or URLs for unpublished assets.

Tap metadata is [MIT licensed](LICENSE); packages retain their upstream licenses.
