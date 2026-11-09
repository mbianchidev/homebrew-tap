"""Verify stable releases and automate CI-gated, release-only package updates."""

import argparse
import base64
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from . import sendbox


ROOT = Path(__file__).resolve().parents[2]
REPOSITORY = "mbianchidev/homebrew-tap"
run = sendbox.run
DIGEST = re.compile(r"[0-9a-f]{64}")
COMMIT = re.compile(r"[0-9a-f]{40}")
UPDATE_BRANCH = re.compile(r"automation/package-updates-[0-9a-f]{16}")
CI_JOBS = {
    "validate",
    "Package lifecycle (macos-15-intel)",
    "Package lifecycle (macos-latest)",
    "Package lifecycle (ubuntu-latest)",
    "Package lifecycle (ubuntu-24.04-arm)",
}


@dataclass(frozen=True)
class Package:
    name: str
    path: str
    repository: str
    templates: tuple[str, ...]
    manifest: str | tuple[str, ...] | None = None

    def asset_names(self, version):
        return tuple(template.format(version=version) for template in self.templates)

    def checksum_names(self, version):
        if isinstance(self.manifest, str):
            return (self.manifest,)
        return self.manifest or tuple(f"{name}.sha256" for name in self.asset_names(version))


PACKAGES = {
    "sendbox": Package(
        "sendbox", "Formula/sendbox.rb", sendbox.REPOSITORY,
        tuple(f"sendbox-{{version}}-{target}.tar.gz" for target in sendbox.PLATFORMS),
    ),
    "sql-not-so-lite": Package(
        "sql-not-so-lite", "Formula/sql-not-so-lite.rb", "mbianchidev/sql-not-so-lite",
        tuple(
            f"sql-not-so-lite_{{version}}_{target}.tar.gz"
            for target in ("darwin_arm64", "darwin_amd64", "linux_arm64", "linux_amd64")
        ),
        "checksums.txt",
    ),
    "killswitch": Package(
        "killswitch", "Casks/killswitch.rb", "mbianchidev/kill-switch", ("KillSwitch.dmg",),
    ),
    "porto": Package(
        "porto", "Casks/porto.rb", "mbianchidev/porto",
        tuple(f"porto-desktop_{{version}}_darwin_{arch}.dmg" for arch in ("arm64", "amd64")),
        "SHA256SUMS",
    ),
    "denote": Package(
        "denote", "Casks/denote.rb", "mbianchidev/denote",
        tuple(f"Denote_{{version}}_{arch}.dmg" for arch in ("aarch64", "x64")),
        ("denote-macos-aarch64-SHA256SUMS.txt", "denote-macos-x64-SHA256SUMS.txt"),
    ),
}


def current_version(text):
    versions = sendbox.VERSION_LINE.findall(text)
    if len(versions) != 1:
        raise ValueError("Expected exactly one stable package version.")
    sendbox.stable_version(versions[0])
    return versions[0]


def release_version(release):
    if not isinstance(release, dict):
        raise ValueError("Expected GitHub release metadata.")
    tag = release.get("tag_name")
    if (
        not isinstance(tag, str) or not tag.startswith("v")
        or release.get("draft") is not False or release.get("prerelease") is not False
    ):
        raise ValueError("Expected a published stable vX.Y.Z release.")
    version = tag.removeprefix("v")
    sendbox.stable_version(version)
    return version


def release_digests(package, release):
    version = release_version(release)
    assets = release.get("assets")
    if not isinstance(assets, list) or any(not isinstance(asset, dict) for asset in assets):
        raise ValueError("Expected published release assets.")
    digests = {}
    for name in package.asset_names(version) + package.checksum_names(version):
        matches = [asset for asset in assets if asset.get("name") == name]
        if len(matches) != 1:
            raise ValueError(f"Expected one published asset: {name}")
        asset = matches[0]
        expected_url = f"https://github.com/{package.repository}/releases/download/v{version}/{name}"
        digest = asset.get("digest")
        if asset.get("browser_download_url") != expected_url:
            raise ValueError(f"Expected a canonical versioned URL for {name}")
        if not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            raise ValueError(f"Missing GitHub SHA-256 digest for {name}")
        digests[name] = digest.removeprefix("sha256:")
    return digests


def definition_pattern(package, version, name):
    if package.name == "killswitch":
        return re.compile(r'^  sha256 "(?P<digest>[0-9a-f]{64})"$', re.MULTILINE)
    url = f"https://github.com/{package.repository}/releases/download/v{version}/{name}"
    if package.path.startswith("Casks/"):
        return re.compile(
            r'^(?P<indent>[ \t]*)sha256 "(?P<digest>[0-9a-f]{64})"\n\n[ \t]*url "'
            + re.escape(url) + r'"$', re.MULTILINE,
        )
    return re.compile(
        r'^(?P<indent>[ \t]*)url "' + re.escape(url)
        + r'"\n[ \t]*sha256 "(?P<digest>[0-9a-f]{64})"$',
        re.MULTILINE,
    )


def update_text(package, text, version, digests):
    current = current_version(text)
    sendbox.stable_version(version)
    if package.name == "sendbox":
        return sendbox.with_release(text, version, {
            target: digests[f"sendbox-{version}-{target}.tar.gz"]
            for target in sendbox.PLATFORMS
        })
    if package.name == "killswitch":
        expected = f"https://github.com/{package.repository}/releases/download/v#{{version}}/KillSwitch.dmg"
        if re.findall(r'^  url "([^"]+)"$', text, re.MULTILINE) != [expected]:
            raise ValueError("Expected one canonical versioned KillSwitch cask URL.")
    for old_name, name in zip(package.asset_names(current), package.asset_names(version)):
        pattern = definition_pattern(package, current, old_name)
        if len(list(pattern.finditer(text))) != 1:
            raise ValueError(f"Expected one canonical package URL/checksum for {old_name}")
        digest = digests[name]
        if not DIGEST.fullmatch(digest):
            raise ValueError(f"Invalid digest for {name}")
        if package.name == "killswitch":
            replacement = f'  sha256 "{digest}"'
        else:
            url = f"https://github.com/{package.repository}/releases/download/v{version}/{name}"
            indent = pattern.search(text).group("indent")
            replacement = (
                f'{indent}sha256 "{digest}"\n\n{indent}url "{url}"'
                if package.path.startswith("Casks/")
                else f'{indent}url "{url}"\n{indent}sha256 "{digest}"'
            )
        text = pattern.sub(lambda match: replacement, text)
    return sendbox.VERSION_LINE.sub(f'  version "{version}"', text)


def prepare_update(package, original, release):
    version = release_version(release)
    current = current_version(original)
    if sendbox.stable_version(version) <= sendbox.stable_version(current):
        print(f"{package.name}: latest {version} is not newer than {current}; no update.")
        return None
    updated = update_text(package, original, version, release_digests(package, release))
    if package.name == "sendbox":
        sendbox.validate_update(
            original, updated, f"automation/sendbox-v{version}", [package.path]
        )
    return version, updated


def published_checksums(text, single_asset=None):
    lines = text.splitlines()
    if single_asset and len(lines) == 1 and DIGEST.fullmatch(lines[0]):
        return {single_asset: lines[0]}
    checksums = {}
    for line in lines:
        fields = line.split()
        if len(fields) != 2 or not DIGEST.fullmatch(fields[0]):
            raise ValueError("Invalid published checksum entry.")
        name = fields[1].removeprefix("*")
        if name in checksums:
            raise ValueError(f"Duplicate published checksum for {name}")
        checksums[name] = fields[0]
    return checksums


def verify_release(package, release):
    version = release_version(release)
    digests = release_digests(package, release)
    with tempfile.TemporaryDirectory(prefix="tap-release-verification-") as directory:
        root = Path(directory)
        for name, expected in digests.items():
            path = root / name
            run(
                "gh", "release", "download", f"v{version}", "--repo", package.repository,
                "--pattern", name, "--output", path,
            )
            with path.open("rb") as artifact:
                actual = hashlib.file_digest(artifact, "sha256").hexdigest()
            if actual != expected:
                raise ValueError(f"Downloaded bytes disagree with GitHub digest for {name}")
        published = {}
        for name in package.checksum_names(version):
            single = package.asset_names(version)[0] if package.name == "killswitch" else None
            checksums = published_checksums((root / name).read_text(), single)
            if not package.manifest and set(checksums) != {name.removesuffix(".sha256")}:
                raise ValueError(f"Unexpected published checksum names in {name}")
            if any(published[name] != checksums[name] for name in published.keys() & checksums.keys()):
                raise ValueError("Conflicting checksums across published manifests.")
            published.update(checksums)
        for name in package.asset_names(version):
            if published.get(name) != digests[name]:
                raise ValueError(f"Published checksum and GitHub digest disagree for {name}")
            if package.name == "sendbox":
                sendbox.verify_attestation(root / name, version)
    print(f"Verified all {package.name} {version} artifacts and published checksums.")


def git(*arguments):
    return run("git", "-C", ROOT, *arguments, capture=True)


def require_hosted_main():
    if (
        os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("TAP_CI_RUNNER_ENVIRONMENT") != "github-hosted"
        or os.environ.get("GITHUB_REPOSITORY") != REPOSITORY
        or os.environ.get("GITHUB_REF") != "refs/heads/main"
    ):
        raise ValueError("Publishing updates requires this tap's GitHub-hosted main workflow.")
    if git("rev-parse", "HEAD") != os.environ.get("GITHUB_SHA"):
        raise ValueError("The update checkout must match the workflow event revision.")
    if git("status", "--porcelain"):
        raise ValueError("Package updates require a clean checkout.")


def ensure_ci(branch, head):
    runs = json.loads(run(
        "gh", "run", "list", "--repo", REPOSITORY, "--workflow", "ci.yml",
        "--branch", branch, "--limit", "100",
        "--json", "databaseId,headSha,event,status,conclusion,url", capture=True,
    ))
    matching = [
        item for item in runs
        if item["headSha"] == head and item["event"] == "workflow_dispatch"
    ]
    if matching:
        latest = matching[0]
        if latest["status"] == "completed" and latest["conclusion"] != "success":
            raise ValueError(f"Existing current-head package CI needs attention: {latest['url']}")
        print(f"Existing current-head package CI: {latest['url']}")
        if latest["status"] == "completed":
            run(
                "gh", "workflow", "run", "merge-package-updates.yml",
                "--repo", REPOSITORY, "--ref", "main",
                "-f", f"run-id={latest['databaseId']}", "-f", "dry-run=false",
            )
        return
    run("gh", "workflow", "run", "ci.yml", "--repo", REPOSITORY, "--ref", branch)
    print(f"Dispatched full package CI for {branch} at {head}.")


def update_branch(updates, base):
    definitions = {package.path: updated for package, _, updated in updates}
    if not updates or len(definitions) != len(updates) or not COMMIT.fullmatch(base):
        raise ValueError("An update batch requires unique package definitions and an exact base commit.")
    identity = json.dumps({"base": base, "definitions": definitions}, sort_keys=True).encode()
    return f"automation/package-updates-{hashlib.sha256(identity).hexdigest()[:16]}"


def publish_updates(updates, base):
    branch = update_branch(updates, base)
    definitions = {package.path: updated for package, _, updated in updates}
    existing = json.loads(run(
        "gh", "pr", "list", "--repo", REPOSITORY, "--head", branch, "--base", "main",
        "--state", "all", "--limit", "100", "--json", "url,state,isDraft,headRefOid",
        capture=True,
    ))
    if len(existing) > 1:
        raise ValueError("Multiple PRs use this generated update branch; inspect them before publishing.")
    if existing and existing[0]["state"] != "OPEN":
        print(f"Existing {existing[0]['state']} PR: {existing[0]['url']}; not duplicating.")
        return
    remote = git("ls-remote", "--heads", "origin", f"refs/heads/{branch}")
    if remote:
        git("fetch", "--no-tags", "origin", f"refs/heads/{branch}")
        head = git("rev-parse", "FETCH_HEAD")
        paths = git("diff", "--name-only", f"{base}...{head}").splitlines()
        if remote.split()[0] != head or paths != sorted(definitions) or any(
            git("show", f"{head}:{path}") != updated.strip()
            for path, updated in definitions.items()
        ):
            raise ValueError(f"Refusing to overwrite unexpected changes on existing branch {branch}")
    else:
        if existing:
            raise ValueError(f"Existing PR has no update branch: {branch}")
        name = os.environ.get("UPDATE_GIT_NAME")
        email = os.environ.get("UPDATE_GIT_EMAIL")
        if not name or not email or any("\n" in value or "\r" in value for value in (name, email)):
            raise ValueError("Package updates require an explicit commit author name and email.")
        for package, release, _ in updates:
            verify_release(package, release)
        git("switch", "--detach", base)
        git("switch", "--create", branch)
        for path, updated in definitions.items():
            (ROOT / path).write_text(updated)
        git("add", "--", *sorted(definitions))
        git(
            "-c", f"user.name={name}", "-c", f"user.email={email}",
            "commit", "--no-gpg-sign", "-m", "Update verified package releases",
        )
        git("push", "origin", f"HEAD:refs/heads/{branch}")
        head = git("rev-parse", "HEAD")
    if existing:
        if existing[0]["headRefOid"] != head:
            raise ValueError("Existing update PR head changed; review it before continuing.")
        print(f"Existing package update PR: {existing[0]['url']}")
    else:
        if remote:
            for package, release, _ in updates:
                verify_release(package, release)
        versions = ", ".join(
            f"{package.name} {release_version(release)}" for package, release, _ in updates
        )
        url = run(
            "gh", "pr", "create", "--repo", REPOSITORY, "--head", branch,
            "--base", "main", "--title", f"Update packages: {versions}",
            "--body", (
                f"Update published stable releases: {versions}.\n\n"
                "All supported release artifacts match GitHub asset digests and published "
                "checksums. Full native package CI is explicitly dispatched for this revision. "
                "A trusted main-branch workflow merges only verified release-field changes "
                "after all native checks pass, with no unresolved review feedback."
            ),
            capture=True,
        )
        print(url)
    ensure_ci(branch, head)


def definition_at(path, head):
    if not COMMIT.fullmatch(head):
        raise ValueError("Package definitions must be read at an exact commit.")
    content = sendbox.api(f"repos/{REPOSITORY}/contents/{path}?ref={head}")
    if content.get("encoding") != "base64" or not isinstance(content.get("content"), str):
        raise ValueError(f"Expected a base64-encoded package definition: {path}")
    return base64.b64decode(content["content"].replace("\n", ""), validate=True).decode()


def check_reviews(number):
    query = """
      query($number: Int!) {
        repository(owner: "mbianchidev", name: "homebrew-tap") {
          pullRequest(number: $number) {
            reviewThreads(first: 100) {
              nodes { isResolved }
              pageInfo { hasNextPage }
            }
            reviews(first: 100) {
              nodes { state author { login } }
              pageInfo { hasNextPage }
            }
          }
        }
      }
    """
    response = json.loads(run(
        "gh", "api", "graphql", "-f", f"query={query}", "-F", f"number={number}", capture=True,
    ))
    if response.get("errors"):
        raise ValueError(f"Could not read PR review state: {response['errors']}")
    reviews = response["data"]["repository"]["pullRequest"]
    if any(reviews[key]["pageInfo"]["hasNextPage"] for key in ("reviewThreads", "reviews")):
        raise ValueError("Incomplete review data requires human review before merging.")
    if any(not thread["isResolved"] for thread in reviews["reviewThreads"]["nodes"]):
        raise ValueError("Unresolved review threads prevent automatic merging.")
    states = {}
    for review in reviews["reviews"]["nodes"]:
        if review["state"] == "PENDING":
            raise ValueError("A pending review prevents automatic merging.")
        if review["state"] != "COMMENTED":
            author = review["author"]
            states[author["login"] if author else None] = review["state"]
    if "CHANGES_REQUESTED" in states.values():
        raise ValueError("Requested review changes prevent automatic merging.")


def validate_pull_request(pull, branch, head, base):
    head_repository = pull["head"].get("repo")
    base_repository = pull["base"].get("repo")
    if (
        pull["state"] != "open" or pull["draft"] is not False
        or pull["user"].get("login") != "github-actions[bot]" or pull["user"].get("type") != "Bot"
        or pull["head"]["ref"] != branch or pull["head"]["sha"] != head
        or not head_repository or head_repository.get("full_name") != REPOSITORY
        or not base_repository or base_repository.get("full_name") != REPOSITORY
        or pull["base"]["ref"] != "main" or pull["base"]["sha"] != base
    ):
        raise ValueError("Automatic merges require an unchanged, ready, same-repository bot update PR.")


def check_ci(run_id, head):
    prefix = f"repos/{REPOSITORY}"
    jobs = sendbox.api(f"{prefix}/actions/runs/{run_id}/jobs?per_page=100")
    results = {job["name"]: job for job in jobs["jobs"]}
    if (
        len(results) != jobs["total_count"] or not CI_JOBS <= results.keys()
        or any(
            results[name]["status"] != "completed" or results[name]["conclusion"] != "success"
            for name in CI_JOBS
        )
    ):
        raise ValueError("All definition checks and all four native lifecycle jobs must pass.")
    checks = sendbox.api(f"{prefix}/commits/{head}/check-runs?per_page=100")
    if len(checks["check_runs"]) != checks["total_count"] or any(
        check["status"] != "completed" or check["conclusion"] not in ("success", "neutral", "skipped")
        for check in checks["check_runs"]
    ):
        raise ValueError("Incomplete, pending or failed current-head checks prevent automatic merging.")
    statuses = sendbox.api(f"{prefix}/commits/{head}/status")
    if statuses["total_count"] and statuses["state"] != "success":
        raise ValueError("Pending or failed current-head commit statuses prevent automatic merging.")


def merge_update(run_id, dry_run=False):
    if not str(run_id).isdigit() or int(run_id) <= 0:
        raise ValueError("An exact successful package workflow run ID is required.")
    prefix = f"repos/{REPOSITORY}"
    workflow = sendbox.api(f"{prefix}/actions/runs/{run_id}")
    branch = workflow["head_branch"]
    head = workflow["head_sha"]
    repository = workflow.get("head_repository") or {}
    if (
        workflow["id"] != int(run_id) or workflow["path"].split("@")[0] != ".github/workflows/ci.yml"
        or workflow["event"] != "workflow_dispatch" or workflow["status"] != "completed"
        or workflow["conclusion"] != "success"
        or repository.get("full_name") != REPOSITORY
        or not isinstance(branch, str) or not UPDATE_BRANCH.fullmatch(branch)
        or not isinstance(head, str) or not COMMIT.fullmatch(head)
    ):
        raise ValueError("Only successful, exact-head native package CI for generated update branches may merge.")
    pulls = json.loads(run(
        "gh", "pr", "list", "--repo", REPOSITORY, "--head", branch, "--base", "main",
        "--state", "open", "--json", "number", capture=True,
    ))
    if not pulls:
        print(f"No open update PR for {branch}; nothing to merge.")
        return
    if len(pulls) != 1:
        raise ValueError("Expected exactly one open generated update PR.")
    number = pulls[0]["number"]
    if type(number) is not int or number <= 0:
        raise ValueError("Expected a valid GitHub pull request number.")
    pull = sendbox.api(f"{prefix}/pulls/{number}")
    base = git("rev-parse", "HEAD")
    validate_pull_request(pull, branch, head, base)
    if sendbox.api(f"{prefix}/commits/main")["sha"] != base:
        raise ValueError("Main changed; generate and validate a fresh update batch.")
    comparison = sendbox.api(f"{prefix}/compare/{base}...{head}")
    if (
        comparison["merge_base_commit"]["sha"] != base
        or comparison["total_commits"] != 1 or comparison["status"] != "ahead"
    ):
        raise ValueError("Package CI must cover one generated update commit on the current main revision.")
    files = sendbox.api(f"{prefix}/pulls/{number}/files?per_page=100")
    paths = [file["filename"] for file in files]
    known = {package.path: package for package in PACKAGES.values()}
    if (
        not paths or len(paths) != pull["changed_files"] or len(paths) != len(set(paths))
        or not set(paths) <= known.keys()
        or any(file["status"] != "modified" for file in files)
    ):
        raise ValueError("Automatic updates may modify only existing registered package definitions.")
    updates, releases = [], []
    for package in PACKAGES.values():
        path = ROOT / package.path
        if not path.is_file():
            if package.path in paths:
                raise ValueError("Automatic release updates cannot introduce new packages.")
            continue
        original = path.read_text()
        latest = sendbox.api(f"repos/{package.repository}/releases/latest")
        releases.append((package, latest))
        candidate = definition_at(package.path, head) if package.path in paths else original
        if current_version(candidate) != release_version(latest):
            raise ValueError(f"{package.name} no longer matches its latest stable release; prepare a fresh batch.")
        if update_text(
            package, candidate, release_version(latest), release_digests(package, latest),
        ) != candidate:
            raise ValueError(f"{package.path} no longer matches the latest published artifact digests.")
        if package.path in paths:
            update = prepare_update(package, original, latest)
            if update is None or update[1] != candidate:
                raise ValueError(f"{package.path} contains changes beyond verified release fields.")
            updates.append((package, latest, candidate))
    if update_branch(updates, base) != branch:
        raise ValueError("The update branch identity does not match its verified definitions and base.")
    check_ci(run_id, head)
    check_reviews(number)
    for package, release, _ in updates:
        verify_release(package, release)
    validate_pull_request(sendbox.api(f"{prefix}/pulls/{number}"), branch, head, base)
    if sendbox.api(f"{prefix}/commits/main")["sha"] != base:
        raise ValueError("Main changed during verification; no merge performed.")
    for package, release in releases:
        latest = sendbox.api(f"repos/{package.repository}/releases/latest")
        if release_version(latest) != release_version(release) or (
            release_digests(package, latest) != release_digests(package, release)
        ):
            raise ValueError(f"{package.name} release changed during verification; no merge performed.")
    check_ci(run_id, head)
    check_reviews(number)
    if dry_run:
        print(f"Would merge verified package update PR #{number} at {head}; no writes.")
        return
    response = json.loads(run(
        "gh", "api", "--method", "PUT", f"{prefix}/pulls/{number}/merge",
        "-f", f"sha={head}", "-f", "merge_method=squash",
        "-f", "commit_title=Update verified package releases", capture=True,
    ))
    if response.get("merged") is not True:
        raise ValueError(f"GitHub refused the package update merge: {response.get('message')}")
    print(f"Merged verified package update PR #{number}: {response['sha']}")
    run("gh", "workflow", "run", "ci.yml", "--repo", REPOSITORY, "--ref", "main")


def retire_updates():
    pages = json.loads(run(
        "gh", "api", "--paginate", "--slurp",
        f"repos/{REPOSITORY}/pulls?state=open&base=main&per_page=100", capture=True,
    ))
    if not isinstance(pages, list) or any(not isinstance(page, list) for page in pages):
        raise ValueError("Expected complete paginated pull request data.")
    pulls = [pull for page in pages for pull in page]
    for pull in pulls:
        branch = pull["head"]["ref"]
        legacy = next((
            package for package in PACKAGES.values()
            if branch.startswith(f"automation/{package.name}-v")
            and sendbox.STABLE.fullmatch(branch.removeprefix(f"automation/{package.name}-v"))
        ), None)
        if (
            not (legacy or UPDATE_BRANCH.fullmatch(branch))
            or pull["user"].get("login") != "github-actions[bot]" or pull["user"].get("type") != "Bot"
            or not pull["head"].get("repo") or pull["head"]["repo"].get("full_name") != REPOSITORY
        ):
            continue
        number, head = pull["number"], pull["head"]["sha"]
        files = sendbox.api(f"repos/{REPOSITORY}/pulls/{number}/files?per_page=100")
        known = {package.path: package for package in PACKAGES.values()}
        paths = [file["filename"] for file in files]
        if (
            not paths or len(paths) > len(known) or len(paths) != len(set(paths))
            or not set(paths) <= known.keys() or any(file["status"] != "modified" for file in files)
            or (legacy and paths != [legacy.path])
        ):
            print(f"::warning::Keeping PR #{number}: it is not a release-only generated update.")
            continue
        candidates = {path: definition_at(path, head) for path in paths}
        if any(
            not (ROOT / path).is_file()
            or sendbox.stable_version(current_version((ROOT / path).read_text()))
            < sendbox.stable_version(current_version(candidate))
            for path, candidate in candidates.items()
        ):
            continue
        comparison = sendbox.api(f"repos/{REPOSITORY}/compare/main...{head}")
        base = comparison["merge_base_commit"]["sha"]
        updates = []
        for path, candidate in candidates.items():
            package = known[path]
            version = current_version(candidate)
            original = definition_at(path, base)
            release = sendbox.api(f"repos/{package.repository}/releases/tags/v{version}")
            expected = prepare_update(package, original, release)
            if expected is None or expected[1] != candidate:
                print(f"::warning::Keeping PR #{number}: {path} has unexpected changes.")
                break
            updates.append((package, release, candidate))
        else:
            if (
                (legacy and branch != f"automation/{legacy.name}-v{current_version(candidates[legacy.path])}")
                or (not legacy and update_branch(updates, base) != branch)
            ):
                print(f"::warning::Keeping PR #{number}: its generated update identity does not match.")
                continue
            current = sendbox.api(f"repos/{REPOSITORY}/pulls/{number}")
            if (
                current["state"] != "open" or current["head"]["sha"] != head
                or current["head"]["ref"] != branch
                or sendbox.api(f"repos/{REPOSITORY}/commits/main")["sha"] != git("rev-parse", "HEAD")
            ):
                print(f"::warning::Keeping PR #{number}: its head or main changed during inspection.")
                continue
            try:
                check_reviews(number)
            except ValueError as error:
                print(f"::warning::Keeping superseded PR #{number}: {error}")
                continue
            run(
                "gh", "pr", "close", str(number), "--repo", REPOSITORY,
                "--comment", "Superseded by verified package releases already on main. "
                "Closing this release-only update without merging it.",
            )


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", choices=PACKAGES)
    parser.add_argument("--dry-run", action="store_true", help="Verify without writing files, branches or PRs.")
    parser.add_argument("--merge-run", help="Verify and merge the update covered by this native CI run.")
    arguments = parser.parse_args(arguments)
    if arguments.merge_run:
        if arguments.package:
            raise ValueError("Merge validation always covers every registered package.")
        require_hosted_main()
        merge_update(arguments.merge_run, dry_run=arguments.dry_run)
        return
    if not arguments.dry_run:
        require_hosted_main()
        if arguments.package:
            raise ValueError("Publishing must batch all packages; --package is for dry runs only.")
        retire_updates()
    base = git("rev-parse", "HEAD") if not arguments.dry_run else None
    packages = [PACKAGES[arguments.package]] if arguments.package else PACKAGES.values()
    updates = []
    for package in packages:
        path = ROOT / package.path
        if not path.is_file():
            print(f"{package.path} is absent; skipping {package.name}.")
            continue
        release = sendbox.api(f"repos/{package.repository}/releases/latest")
        original = path.read_text()
        update = prepare_update(package, original, release)
        if not update:
            continue
        version, updated = update
        if arguments.dry_run:
            verify_release(package, release)
            print(f"Would update {package.path}: {current_version(original)} -> {version}; no writes.")
        else:
            updates.append((package, release, updated))
    if updates:
        publish_updates(updates, base)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"::error::{error}", file=sys.stderr)
        raise SystemExit(1) from error
