# Homebrew tap

Homebrew formulas and casks for [mbianchidev](https://github.com/mbianchidev)
projects. Packages are independent: a project does not need its first release
before other packages can be installed or tested.

```bash
brew tap mbianchidev/tap
brew search mbianchidev/tap/
```

## Sendbox

> **Activation blocked: wait for an approved patched stable release newer than
> v0.2.2.** Do not merge this draft or distribute its v0.2.2 package. The current
> verified artifacts are retained only for isolated lifecycle testing. Update the
> formula from the patched release's real, verified assets and rerun CI before
> human merge.

[Sendbox](https://github.com/mbianchidev/sendbox) is a Rust CLI for running coding
agents in policy-controlled Linux VMs. The formula installs verified published
host binaries, configuration examples, setup helper, and the matching signed
guest payload. No Rust compiler, frontend build, VM, agent, or service is started.

After that activation gate is satisfied:

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
Installation never starts the daemon or opens a browser. The commands become
available from the default tap only after human merge of this draft.

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

## Maintainers

Package definitions live in `Formula/` and `Casks/`. CI discovers both directories,
accepts an empty tap, checks syntax/style and all platform definitions, and tests
the checked-out event revision rather than the remote default branch. Compatible
packages are installed and removed on disposable Intel/ARM Mac and Linux
x86_64/aarch64 GitHub runners. Casks are not launched. Sendbox additionally checks
release checksums/provenance, real previous-stable-to-current `brew upgrade`,
CLI startup/version/configuration/completions, Linux linkage, unchanged signed
guest bytes, and preservation of mocked user/project data. No VM or agent is
started, and none of these lifecycle scripts may run on the maintainer's laptop.
Sendbox init/policy fixture writes run outside Homebrew's restrictive test
sandbox; its `brew test` uses read-only CLI commands.
sql-not-so-lite additionally verifies and serves its embedded GUI on localhost,
creates a mock SQLite database, stops the temporary daemon, and verifies package
removal preserves the configuration and database bytes. Its scan root and home
are temporary fixtures, never the runner's real home or the maintainer's data.

Draft PRs intentionally run package CI. Obsolete runs are canceled; package
downloads and Homebrew's locked style dependencies are cached by OS/architecture.
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

**Sendbox activation requires a patched stable release newer than v0.2.2**, verified
formula updates, passing lifecycle CI, and human merge of both initial PRs.
Only then, in this tap's Settings > Actions > General > Workflow permissions,
an administrator must enable **Allow GitHub
Actions to create and approve pull requests**. It is currently disabled.
Automation reports an actionable failure and leaves the validated update branch
available for a manually opened draft if that permission is missing. Do not
enable auto-merge or widen the token's repository permissions. The initial PR
must be merged by a human before the new workflow is active.

The initial verified v0.2.2 binaries predate the upstream TLS dependency fixes for
[RUSTSEC-2026-0382](https://rustsec.org/advisories/RUSTSEC-2026-0382.html) and
[RUSTSEC-2026-0383](https://rustsec.org/advisories/RUSTSEC-2026-0383.html).
Plan production activation around a human-approved patched stable release;
fixing the source lockfile cannot change already published binaries.

Other projects keep their own release tooling and dedicated deploy keys. The
existing sql-not-so-lite key and formula are independent of Sendbox.
Do not commit placeholder hashes or URLs for unpublished assets.

Tap metadata is [MIT licensed](LICENSE); packages retain their upstream licenses.
