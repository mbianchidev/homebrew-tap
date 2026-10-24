"""Verify upstream releases and prepare idempotent draft package updates."""

import argparse
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


@dataclass(frozen=True)
class Package:
    name: str
    path: str
    repository: str
    templates: tuple[str, ...]
    manifest: str | None = None

    def asset_names(self, version):
        return tuple(template.format(version=version) for template in self.templates)

    def checksum_names(self, version):
        return (self.manifest,) if self.manifest else tuple(
            f"{name}.sha256" for name in self.asset_names(version)
        )


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
            replacement = f'{indent}url "{url}"\n{indent}sha256 "{digest}"'
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
            if published.keys() & checksums.keys():
                raise ValueError("Duplicate published artifact checksums.")
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
        "--json", "headSha,event,status,conclusion,url", capture=True,
    ))
    matching = [
        item for item in runs
        if item["headSha"] == head and item["event"] in ("push", "workflow_dispatch")
    ]
    if matching:
        latest = matching[0]
        if latest["status"] == "completed" and latest["conclusion"] != "success":
            raise ValueError(f"Existing current-head package CI needs attention: {latest['url']}")
        print(f"Existing current-head package CI: {latest['url']}")
        return
    run("gh", "workflow", "run", "ci.yml", "--repo", REPOSITORY, "--ref", branch)
    print(f"Dispatched full package CI for {branch} at {head}.")


def publish_update(package, release, updated, base):
    version = release_version(release)
    branch = f"automation/{package.name}-v{version}"
    existing = json.loads(run(
        "gh", "pr", "list", "--repo", REPOSITORY, "--head", branch, "--base", "main",
        "--state", "all", "--limit", "100", "--json", "url,state,isDraft,headRefOid",
        capture=True,
    ))
    if existing and existing[0]["state"] != "OPEN":
        print(f"Existing {existing[0]['state']} PR: {existing[0]['url']}; not duplicating.")
        return
    remote = git("ls-remote", "--heads", "origin", f"refs/heads/{branch}")
    if remote:
        git("fetch", "--no-tags", "origin", f"refs/heads/{branch}")
        head = git("rev-parse", "FETCH_HEAD")
        paths = git("diff", "--name-only", f"{base}...{head}").splitlines()
        if (
            remote.split()[0] != head or paths != [package.path]
            or git("show", f"{head}:{package.path}") != updated.strip()
        ):
            raise ValueError(f"Refusing to overwrite unexpected changes on existing branch {branch}")
    else:
        if existing:
            raise ValueError(f"Existing PR has no update branch: {branch}")
        name = os.environ.get("UPDATE_GIT_NAME")
        email = os.environ.get("UPDATE_GIT_EMAIL")
        if not name or not email or any("\n" in value or "\r" in value for value in (name, email)):
            raise ValueError("Package updates require an explicit commit author name and email.")
        verify_release(package, release)
        git("switch", "--detach", base)
        git("switch", "--create", branch)
        (ROOT / package.path).write_text(updated)
        git("add", "--", package.path)
        git(
            "-c", f"user.name={name}", "-c", f"user.email={email}",
            "commit", "--no-gpg-sign", "-m", f"Update {package.name} to {version}",
        )
        git("push", "origin", f"HEAD:refs/heads/{branch}")
        head = git("rev-parse", "HEAD")
    if existing:
        if existing[0]["headRefOid"] != head:
            raise ValueError("Existing update PR head changed; review it before continuing.")
        print(f"Existing draft/update PR: {existing[0]['url']}")
    else:
        if remote:
            verify_release(package, release)
        url = run(
            "gh", "pr", "create", "--repo", REPOSITORY, "--head", branch,
            "--base", "main", "--draft", "--title", f"{package.name} {version}",
            "--body", (
                f"Update only {package.path} to published stable {package.name} {version}.\n\n"
                "All supported release artifacts match GitHub asset digests and published "
                "checksums. Full native package CI is explicitly dispatched for this revision. "
                "Human review and merge are required; no automatic merge is enabled."
            ),
            capture=True,
        )
        print(url)
    ensure_ci(branch, head)


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", choices=PACKAGES)
    parser.add_argument("--dry-run", action="store_true", help="Verify without writing files, branches or PRs.")
    arguments = parser.parse_args(arguments)
    if not arguments.dry_run:
        require_hosted_main()
        if not arguments.package:
            raise ValueError("Publishing requires one explicit --package per job.")
    base = git("rev-parse", "HEAD") if not arguments.dry_run else None
    packages = [PACKAGES[arguments.package]] if arguments.package else PACKAGES.values()
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
            publish_update(package, release, updated, base)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"::error::{error}", file=sys.stderr)
        raise SystemExit(1) from error
