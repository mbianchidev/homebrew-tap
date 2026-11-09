# Maintainer guide

[Documentation](README.md)

## Repository layout

| Path | Purpose |
| --- | --- |
| [`Formula/`](../Formula) | Sendbox and sql-not-so-lite package definitions |
| [`Casks/`](../Casks) | KillSwitch, Porto and Denote desktop apps |
| [`scripts/ci/`](../scripts/ci) | Package lifecycle checks and verified release updates |
| [`tests/`](../tests) | Mock-data regression tests |
| [Package workflow](../.github/workflows/ci.yml) | Definition checks and native lifecycle matrix |
| [Update workflow](../.github/workflows/update-packages.yml) | Hourly/manual verified stable-release update batches |
| [Merge workflow](../.github/workflows/merge-package-updates.yml) | Trusted-main, CI-gated merges of release-only updates |

The tap consumes upstream release artifacts; it does not build or publish the
upstream applications. Keep their release tooling in their source repositories.

## Package changes

Keep changes focused on the affected package, its tests and its documentation.
Use published, versioned artifact URLs and verified SHA-256 checksums; never
commit placeholders for unpublished assets. Preserve supported platforms,
signed payload bytes and existing user data.

Run the relevant checks below, update the package guide, and open a draft pull
request for human review. Read and address CI failures and review feedback.
Do not push updates directly to `main` or merge implementation PRs automatically.
Only the verified release-only automation described below merges without a human.

Contributor responsibility, including AI-assisted work, is described in the
[README policy](../README.md#ai-policy).

## Local checks

Use Ruby with Minitest, Python 3.11+ and Homebrew. The isolated KillSwitch lifecycle
check also needs macOS and authenticated GitHub CLI access to release metadata.
Homebrew manages its locked style and audit dependencies.

CI explicitly selects [Python 3.15.1](https://www.python.org/downloads/release/python-3151/)
for regression tests, Sendbox lifecycle checks and both package-update workflows.
Use that interpreter as `python3` to match CI locally; Python 3.11+ remains supported
for local checks. The Python tools use only the standard library, with no Python
packages to install.
Hosted jobs preload that exact interpreter through GitHub's release-asset API
using pinned official archive IDs and SHA-256 digests, then let `setup-python`
select the verified tool-cache entry. This avoids the browser download route's
observed HTTP 504 failures without changing the interpreter or weakening checks.
The bootstrap refuses non-hosted environments. Update its pinned asset map when
changing Python or supported Ubuntu runner releases.

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

Ubuntu x86_64 jobs follow `ubuntu-latest`. GitHub provides only versioned
[Ubuntu ARM runner labels](https://docs.github.com/en/actions/reference/runners/github-hosted-runners),
so native ARM coverage uses `ubuntu-24.04-arm`, not an unsupported
`ubuntu-latest-arm` alias.

ARM macOS follows `macos-latest`. That alias selects ARM hardware, not Intel,
so `macos-15-intel` remains pinned to preserve native Intel coverage and existing
check names. GitHub provides no standard Intel latest alias; no larger or paid
runner is substituted.

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

The **Package updates** workflow checks Sendbox, sql-not-so-lite, KillSwitch,
Porto and Denote
hourly at **17 minutes past the hour UTC**. It can also run manually from the
Actions tab on `main`; manual runs default to a dry run. Clear the dry-run option
to publish updates.
Scheduled and merge workflows become active only after the implementation PR is
merged into the default branch. GitHub schedules can be delayed; publication is
not guaranteed to finish within an hour.

For each newer stable `vX.Y.Z` release, the updater verifies every supported
platform artifact against its GitHub SHA-256 digest and the adjacent published
checksum or checksum manifest. Sendbox archives also require the existing
tag-bound release-workflow attestations. Missing platform artifacts, ambiguous
assets, mismatched hashes and prereleases fail explicitly rather than producing
partial package updates. No application, service, VM or agent is launched.
Porto uses its `SHA256SUMS` manifest; Denote uses both macOS architecture
manifests. Identical shared entries across separate manifests are accepted;
duplicate entries within a manifest or conflicting shared digests fail.
Both architecture-specific DMGs must be present and verified before a cask
update is published.

The updater changes only versions, versioned release URLs where necessary and
checksums. All pending releases are verified before any definition is written and
published together in one ready PR on `automation/package-updates-<digest>`.
Batching prevents simultaneous releases from blocking each other's strict
full-tap audits. An incomplete or invalid candidate fails the batch explicitly.
The branch identity binds the exact main revision and definition bytes. Matching
branches and PRs are reused after interrupted publication or CI dispatch; closed
or merged PRs are not duplicated, and unexpected branch edits are never replaced
or force-pushed. Old bot-generated, release-only PRs are closed without merging
once their versions are already incorporated into `main`. Modified or unrelated
PRs are preserved with an explicit warning.

The workflow uses the repository-scoped `GITHUB_TOKEN`, not a new personal token
or deploy key. Write permissions are limited to the update job. GitHub does not
run push CI for token-created commits, and token-created PR workflows can require
approval, so the updater explicitly dispatches the existing **Packages** workflow
on the exact update branch. All native lifecycle checks and strict cask audits
remain enabled. Existing failed current-head CI is reported for attention, not
silently retried or accepted. The full tap keeps its Intel/ARM macOS and Linux
lifecycle coverage.

The **Merge verified package updates** workflow runs separately after successful
native CI and uses only code from its trusted main-branch event revision. It
never checks out PR code or consumes PR-produced executable artifacts with its
write token. It requires one unchanged, ready, same-repository GitHub Actions bot
PR whose single update commit is based on current `main`. Every candidate byte
must match an independently reconstructed latest-stable update; artifacts,
checksums and Sendbox's tag-bound attestations are reverified before merging.
All five definition/native jobs must pass; additional head checks must be
successful or report a completed neutral/no-work result. Unresolved threads,
pending reviews or requested changes block the merge. The exact head SHA guards
the squash merge. Main, the PR, release metadata, checks and reviews are rechecked
immediately beforehand. GitHub enforces repository
merge restrictions. No branch protection or repository-wide auto-merge setting
is weakened or enabled.

Token-created merges do not trigger normal push CI, so the merger explicitly
dispatches full post-merge package CI on `main`. A successful existing update CI
run can redispatch the trusted merger on the next hourly update check, allowing
review/check completion or interrupted merge recovery without repeating native
CI. Maintainers can also run the merge workflow manually on `main` with its
successful native CI run ID; manual merge validation defaults to a dry run.

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

### Upstream integration and permissions

This tap owns Homebrew publication for all registered upstream projects.
Sendbox and sql-not-so-lite source workflows should publish release artifacts,
not push competing formula branches or write directly to this tap's `main`.
Their separate migration PRs remove those writers and tap-write credential
requirements. Retire obsolete source-repository tap deploy keys only after this
central automation and the upstream migration PRs are merged and verified.
KillSwitch already publishes versioned artifacts without writing to the tap and
needs no additional source-repository integration.
Porto and Denote already publish versioned Intel/ARM DMGs and checksum manifests
from their release workflows, so the central updater needs no new tap-write
credentials or source-driven tap branches. Their separate macOS packaging PRs
correct app sealing while preserving release checksums and provenance.
Ad-hoc signatures are not Developer ID signing or notarization; casks retain
quarantine and never re-sign downloaded apps or start runtimes.

Only Sendbox stable versions newer than v0.2.2 may be activated; the update must
advance the version and match the latest published stable release. This floor
excludes releases affected by
[RUSTSEC-2026-0382](https://rustsec.org/advisories/RUSTSEC-2026-0382.html) and
[RUSTSEC-2026-0383](https://rustsec.org/advisories/RUSTSEC-2026-0383.html).
Prereleases cannot replace the stable package. Sendbox's three supported archives
retain their checksum and tag-bound, GitHub-hosted-runner provenance checks.

For automated PR creation, enable **Allow GitHub Actions to create and approve
pull requests** in the tap's Settings > Actions > General > Workflow permissions.
If permission is missing, automation fails explicitly rather than publishing
without validation. Write permissions are job-scoped: `contents: write`,
`pull-requests: write` and `actions: write`. Both jobs have `attestations: read`;
the trusted merger also needs `checks: read` and `statuses: read` to inspect all
head checks. Ordinary PR validation remains read-only, and repository-wide
auto-merge is not required.

KillSwitch also keeps GitHub latest livecheck for independent stable-release
auditing. Automated or manual updates verify the actual versioned DMG, its GitHub
digest and the published checksum before changing the cask's version and SHA-256.
Keep `auto_updates true` and the documented greedy-upgrade behavior while the
built-in updater exists.

Upstream projects retain their own release tooling and credentials. The scheduled
tap updater reads public releases and does not reuse their publishing credentials.
