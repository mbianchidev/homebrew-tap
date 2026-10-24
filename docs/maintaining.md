# Maintainer guide

[Documentation](README.md)

## Repository layout

| Path | Purpose |
| --- | --- |
| [`Formula/`](../Formula) | Sendbox and sql-not-so-lite package definitions |
| [`Casks/`](../Casks) | KillSwitch app and bundled CLI artifacts |
| [`scripts/ci/`](../scripts/ci) | Package lifecycle checks and verified release updates |
| [`tests/`](../tests) | Mock-data regression tests |
| [Package workflow](../.github/workflows/ci.yml) | Definition checks and native lifecycle matrix |
| [Update workflow](../.github/workflows/update-packages.yml) | Daily/manual stable-release detection and draft updates |

The tap consumes upstream release artifacts; it does not build or publish the
upstream applications. Keep their release tooling in their source repositories.

## Package changes

Keep changes focused on the affected package, its tests and its documentation.
Use published, versioned artifact URLs and verified SHA-256 checksums; never
commit placeholders for unpublished assets. Preserve supported platforms,
signed payload bytes and existing user data.

Run the relevant checks below, update the package guide, and open a draft pull
request for human review. Read and address CI failures and review feedback.
Do not push updates directly to `main` or merge automatically.

Contributor responsibility, including AI-assisted work, is described in the
[README policy](../README.md#ai-policy).

## Local checks

Use Ruby with Minitest, Python 3.11+ and Homebrew. The isolated KillSwitch lifecycle
check also needs macOS and authenticated GitHub CLI access to release metadata.
Homebrew manages its locked style and audit dependencies.

From the repository root:

```bash
ruby -c scripts/ci/test-packages.rb
ruby -c scripts/ci/killswitch.rb
ruby tests/test_killswitch_cask.rb
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py'
brew style --except-cops=FormulaAuditStrict,FormulaAudit/ComponentsOrder Formula/sendbox.rb
brew style Formula/sql-not-so-lite.rb Casks/killswitch.rb
```

Sendbox needs its explicit version before the interpolated default URL so
metadata remains loadable on unsupported Intel Macs. The CI style exception
preserves this ordering; the remaining checks stay enabled.

On macOS, the KillSwitch lifecycle check is safe to run locally:

```bash
ruby scripts/ci/killswitch.rb Casks/killswitch.rb
```

It verifies the DMG against GitHub's asset digest and the adjacent published
checksum, then uses the real Homebrew installer with disposable HOME, cache,
Caskroom, binary and custom application directories. It checks universal
architectures, the CLI link, code signature, retained quarantine, uninstall and
mocked application-data preservation. Neither the GUI nor CLI is executed.

**Do not run `scripts/ci/test-packages.rb` or the Sendbox lifecycle command on
your laptop.** Those checks require disposable GitHub-hosted runners. Do not
spoof their runner-environment guards to run them locally.

Qualified `brew` commands use the installed tap, which may differ from your
working checkout. CI explicitly points Homebrew at the checked-out event
revision and verifies that relationship before checking definitions.

## Hosted validation

CI discovers `Formula/` and `Casks/`, accepts an empty tap, checks Ruby syntax,
style and regression tests, and evaluates all platform definitions with
`brew readall --os=all --arch=all --aliases mbianchidev/tap`.

Compatible packages are installed and removed on Intel/ARM Macs and Linux
x86_64/aarch64 runners. Strict online DMG cask audits run on macOS because they
need `hdiutil`. Packages remain independent; an unavailable platform is reported
as skipped rather than blocking unrelated packages.

Sendbox checks release checksums and tag-bound provenance, a real
previous-stable-to-current `brew upgrade`, version/help/configuration/completions,
Linux linkage, signed guest-byte preservation, uninstall and mocked user/project
data preservation. No VM or agent is started. Init/policy fixture writes run
outside Homebrew's restrictive test sandbox; `brew test` uses read-only commands.

sql-not-so-lite serves its embedded GUI on localhost, creates a mock SQLite
database, stops the temporary daemon and checks uninstall/data preservation.
Its home and scan root are temporary fixtures, not the runner's actual data.
No browser is opened.

KillSwitch uses the same isolated lifecycle check available locally. Only
`token_conflicts` is excepted from its strict online audit: the explicitly
qualified cask shares a token with an unrelated core VPN formula. Normal token
syntax and all other audit checks remain enabled.

Draft pull requests run package CI. Obsolete runs are canceled, matrices fail
fast, and package downloads are cached by OS/architecture. Validation and
lifecycle jobs reuse Homebrew's locked Ruby dependencies from the same
OS/architecture/lockfile-keyed cache, including native audit and formula-test
dependencies. A cache miss still installs the locked dependencies normally.
Standard style checks run in one batch; Sendbox keeps its separate, narrowly
scoped exception. Build workers are limited to two where available; upstream
application binaries are reused rather than rebuilt. Credentials are not cached.

Linux hosted kernels can expose an older Landlock ABI than the ABI 10 required
for complete network denial. Homebrew reports that limitation and applies the
restrictions the host supports. Surface these warnings rather than claiming
full network isolation.

## Release updates

### Scheduled updates for all packages

The **Package updates** workflow checks Sendbox, sql-not-so-lite and KillSwitch
daily at **06:17 UTC**. It can also run manually from the Actions tab on `main`;
manual runs default to a dry run. Clear the dry-run option to publish updates.
Scheduled workflows become active only after the workflow is merged into the
default branch.

For each newer stable `vX.Y.Z` release, the updater verifies every supported
platform artifact against its GitHub SHA-256 digest and the adjacent published
checksum or checksum manifest. Sendbox archives also require the existing
tag-bound release-workflow attestations. Missing platform artifacts, ambiguous
assets, mismatched hashes and prereleases fail explicitly rather than producing
partial package updates. No application, service, VM or agent is launched.

The updater changes only the version, release URLs where necessary and checksums
in the affected definition. It pushes `automation/<package>-vX.Y.Z` and opens one
**draft** pull request for human review. Existing matching branches and open PRs
are reused, including recovery after interrupted PR creation or CI dispatch.
Unexpected branch edits are not overwritten; closed or merged PRs are not
duplicated. No update is pushed to `main`, and nothing is merged automatically.

The workflow uses the repository-scoped `GITHUB_TOKEN`, not a new personal token
or deploy key. Write permissions are limited to the update job. GitHub does not
run push CI for token-created commits, and token-created PR workflows can require
approval, so the updater explicitly dispatches the existing **Packages** workflow
on the exact update branch. All native lifecycle checks and strict cask audits
remain enabled. Existing failed current-head CI is reported for attention, not
silently retried or accepted. Unrelated packages are checked independently.

Preview releases locally with authenticated `gh`, without editing definitions,
creating branches or opening PRs:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m scripts.ci.package_updates --dry-run
PYTHONDONTWRITEBYTECODE=1 python3 -m scripts.ci.package_updates --package killswitch --dry-run
```

Downloads use automatically cleaned temporary directories. Actual publishing is
restricted to this tap's GitHub-hosted `main` workflow and a clean event-revision
checkout. Do not bypass that guard on a laptop. When adding a package or changing
its upstream asset layout, update the package registry and mock-data tests in
`scripts/ci/package_updates.py` and `tests/test_package_updates.py`.

### Source-driven Sendbox updates

Sendbox stable-release automation verifies published artifacts in its source
repository, changes only the formula's version and three checksums, and uses a
dedicated tap-scoped SSH deploy key to push `automation/sendbox-vX.Y.Z`.
This tap validates the branch before opening an idempotent draft pull request
with its own `GITHUB_TOKEN`.

Only strict stable versions newer than v0.2.2 may be activated; the update must
advance the version and match the latest published stable release. This floor
excludes releases affected by
[RUSTSEC-2026-0382](https://rustsec.org/advisories/RUSTSEC-2026-0382.html) and
[RUSTSEC-2026-0383](https://rustsec.org/advisories/RUSTSEC-2026-0383.html).
Prereleases cannot replace the stable package. Existing pull requests, including
closed ones, are not duplicated. Automation branches use push CI rather than
duplicate pull-request runs. Humans review and merge.

For automated draft creation, enable **Allow GitHub Actions to create and approve
pull requests** in the tap's Settings > Actions > General > Workflow permissions.
If permission is missing, automation reports a failure and leaves the validated
branch available for a manually opened draft. Do not enable auto-merge or widen
the token's repository permissions beyond those required by the update jobs.

KillSwitch also keeps GitHub latest livecheck for independent stable-release
auditing. Automated or manual updates verify the actual versioned DMG, its GitHub
digest and the published checksum before changing the cask's version and SHA-256.
Keep `auto_updates true` and the documented greedy-upgrade behavior while the
built-in updater exists.

Upstream projects retain their own release tooling and credentials. The scheduled
tap updater reads public releases and does not reuse their publishing credentials.
