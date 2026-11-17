# Agent instructions

This is the `mbianchidev/tap` Homebrew tap. It packages published upstream
release artifacts; it never builds or publishes the upstream applications.
Read the [maintainer guide](docs/maintaining.md) before changing anything.

## Ground rules

- Work on a branch and open a draft pull request. Never push to `main` or merge
  implementation PRs; only the verified release-only automation merges by itself.
- Never commit placeholder, guessed or locally rebuilt checksums, or
  `sha256 :no_check`.
- Never strip quarantine from definitions or CI (`xattr` in
  `postflight_steps` `run` steps or any other route), re-sign apps, or launch
  apps, services, VMs or agents. Removing quarantine skips Gatekeeper and
  XProtect's first-launch checks, and Homebrew deliberately dropped
  `--no-quarantine`, so that choice belongs to each user. Caveats give them the
  exact command to run themselves (see [Cask layout](#cask-layout)).
- Do not run `scripts/ci/test-packages.rb` or the Sendbox lifecycle locally, and
  do not spoof their GitHub-hosted runner guards.
- Tests use mock data only.

## Refer to packages by name, never by file path

Homebrew refuses to load formulae and casks from file paths, URLs or Ruby
source ("Loading formulae from paths or URLs is not supported" and "Loading
casks from paths, URLs or Ruby source is not supported"). Code that passes a
`Formula/*.rb` or `Casks/*.rb` path fails with "No available formula" or
"No Cask with this name exists".

- Use the qualified name `mbianchidev/tap/<name>` with every `brew` command
  (`install`, `test`, `audit`, `info`, `fetch`, `--cache`, `uninstall`) and in
  `brew ruby` code (`Formulary.factory`, `Cask::CaskLoader.load`).
- CI links the checkout as the tap and verifies it is the event revision. A
  script that receives a definition path must load the qualified name and check
  the loaded source matches that file, as `scripts/ci/killswitch.rb` does.
- `brew style` is the exception: it accepts file paths.
- Prefer the public `brew` CLI. Homebrew's internal Ruby APIs change without
  notice; when one is unavoidable, keep it in a single script with a regression
  test.

## Tap trust

Non-official taps need explicit trust. Fully qualified `brew install` commands
trust only that package. Anything else that loads a package (`brew ruby`,
`Formulary`, `CaskLoader`) needs prior per-package trust:
`brew trust --formula mbianchidev/tap/<name>` or `--cask`.

`Homebrew/actions/setup-homebrew` trusts the checked-out tap in the disposable
runner's own configuration, so CI `brew` commands can load the revision under
test. Do not add further trust in workflows or scripts. When a check isolates
`HOME`, also isolate `XDG_CONFIG_HOME` and trust only the package under test in
that disposable configuration. Never trust the tap on a maintainer's machine on
their behalf, and never set `HOMEBREW_NO_REQUIRE_TAP_TRUST`.

## Adding or changing a package

Every package, formula or cask, needs all of the following in one PR:

1. **Definition.** `Formula/<name>.rb` or `Casks/<token>.rb`. Check
   `brew info --formula <name>` and `brew info --cask <name>` for official
   conflicts and document any shared name (KillSwitch shares one with a core
   formula and is only installed by its qualified name).
2. **Artifacts.** Immutable versioned GitHub release assets:
   `https://github.com/mbianchidev/<repo>/releases/download/vX.Y.Z/<asset>`.
   Never `releases/latest/download`, branch archives or CI artifacts. Each
   `sha256` must match the asset's GitHub digest and the published checksum
   file or manifest.
3. **Updater registration.** Add a `Package` entry to `PACKAGES` in
   `scripts/ci/package_updates.py` with the repository, asset name templates and
   checksum manifest (or `single_dmg=True`), plus mock-data cases in
   `tests/test_package_updates.py`. The updater rewrites definitions with exact
   patterns, so keep the layouts below.
4. **Lifecycle coverage.** `scripts/ci/test-packages.rb` discovers packages and
   runs install, test and uninstall on ARM macOS and Linux x86_64/aarch64. Add
   a package-specific check under `scripts/ci/` only when the default is not
   enough, using disposable directories, mock data and qualified names.
5. **Docs.** Add `docs/<name>.md` and rows in the [README](README.md) and
   [docs index](docs/README.md) package tables, and update the package lists in
   the [maintainer guide](docs/maintaining.md). Non-notarized apps link the
   [first launch guide](docs/macos-security.md). Install commands are fully
   qualified: `brew install mbianchidev/tap/<name>` or
   `brew install --cask mbianchidev/tap/<name>`.

### Formula layout

- Literal versioned `url` immediately followed by its `sha256`, inside
  `on_macos`/`on_linux` and `on_arm`/`on_intel` blocks per platform artifact
  (see `Formula/sql-not-so-lite.rb`). One stable `version "X.Y.Z"` line.
- Declare platform limits (`depends_on arch:`, `depends_on macos:`) and cover
  only platforms with real artifacts. Do not add new Intel-only macOS builds.
- A `test do` block that exercises real behavior without network access or
  user data; use `service do` for daemons. Put post-install work in
  `post_install_steps`, not `post_install`.

### Cask layout

- `version` first. A single universal DMG uses a top-level `sha256` and a URL
  interpolating `#{version}`, with an adjacent bare-digest `<asset>.sha256`
  (`single_dmg`). Per-architecture DMGs use `on_arm`/`on_intel` blocks with
  `sha256`, a blank line, then the interpolated `url` (see `Casks/porto.rb`).
- `livecheck` with `strategy :github_latest`, `depends_on macos:`, and a `zap`
  only for verified app data paths.
- `auto_updates true` only for apps with a working built-in updater, with a
  caveat recommending `brew upgrade --cask --greedy mbianchidev/tap/<token>`.
- Apps that are not Developer ID signed and notarized keep quarantine, and
  their caveats give the first launch, as in `Casks/killswitch.rb`: state the
  real signing status (ad-hoc is not Developer ID or notarization); the
  click-by-click path (double-click the app and click Done, open System
  Settings > Privacy & Security, click Open Anyway, then Open); then the exact
  per-app command `xattr -d -r com.apple.quarantine "#{appdir}/<App>.app"`,
  saying it skips the first-launch malware check and must be repeated after
  each upgrade. Interpolate `#{appdir}` so custom `--appdir` installs print the
  right path. Never suggest `xattr -c`/`-cr` or disabling Gatekeeper globally.
  Also say installation launches nothing and link
  [docs/macos-security.md](docs/macos-security.md); add new apps to that
  guide's command table. Use `preflight_steps`/`postflight_steps`, never Ruby
  flight blocks.

## Validation

Run the [local checks](docs/maintaining.md#local-checks), then let PR CI run
`brew style`, `brew readall --os=all --arch=all --aliases mbianchidev/tap`,
strict online audits and the native lifecycle matrix. Read and fix every CI
failure and warning before asking for review. Cask audits skip only
`livecheck_version`, so a pending upstream release is a warning, not a failure;
do not re-enable it or treat that warning as a reason to bump versions by hand,
since the updater owns releases.
