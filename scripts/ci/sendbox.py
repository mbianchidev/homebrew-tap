#!/usr/bin/env python3
"""Verify Sendbox packaging on disposable runners and prepare stable update PRs."""

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import subprocess
import sys
import tarfile
import tempfile


REPOSITORY = "mbianchidev/sendbox"
TAP = "mbianchidev/tap/sendbox"
PLATFORMS = ("macos-arm64", "linux-x86_64", "linux-aarch64")
VERSION_LINE = re.compile(r'^  version "([^"]+)"$', re.MULTILINE)
STABLE = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")


def stable_version(version):
    if not STABLE.fullmatch(version):
        raise ValueError(f"Not a stable semantic version: {version}")
    return tuple(map(int, version.split(".")))


def checksum_pattern(target):
    url = (
        "https://github.com/mbianchidev/sendbox/releases/download/"
        f"v#{{version}}/sendbox-#{{version}}-{target}.tar.gz"
    )
    return re.compile(
        r'(^[ \t]*url "' + re.escape(url)
        + r'"\n[ \t]*sha256 ")([0-9a-f]{64})(")$',
        re.MULTILINE,
    )


def formula_fields(text):
    versions = VERSION_LINE.findall(text)
    if len(versions) != 1:
        raise ValueError("Expected exactly one top-level formula version.")
    stable_version(versions[0])
    digests = {}
    for target in PLATFORMS:
        matches = list(checksum_pattern(target).finditer(text))
        if len(matches) != 1:
            raise ValueError(f"Expected one canonical URL followed by its checksum: {target}")
        digests[target] = matches[0].group(2)
    return versions[0], digests


def with_release(text, version, digests):
    formula_fields(text)
    stable_version(version)
    text = VERSION_LINE.sub(f'  version "{version}"', text)
    for target in PLATFORMS:
        digest = digests[target]
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"Invalid release digest for {target}")
        text = checksum_pattern(target).sub(
            lambda match: match[1] + digest + match[3], text
        )
    return text


def validate_update(base, head, branch, changed_paths):
    prefix = "automation/sendbox-v"
    if not branch.startswith(prefix):
        raise ValueError("Only automation/sendbox-vX.Y.Z branches may create package PRs.")
    version = branch[len(prefix):]
    stable_version(version)
    if stable_version(version) <= (0, 2, 2):
        raise ValueError("Activation requires an approved patched stable release newer than v0.2.2.")
    if changed_paths != ["Formula/sendbox.rb"]:
        raise ValueError("An automated Sendbox update must change only Formula/sendbox.rb.")
    if formula_fields(head)[0] != version:
        raise ValueError("Branch version does not match Formula/sendbox.rb.")

    def without_release(text):
        formula_fields(text)
        text = VERSION_LINE.sub("", text)
        for target in PLATFORMS:
            text = checksum_pattern(target).sub(lambda match: match[1] + match[3], text)
        return text

    if without_release(base) != without_release(head):
        raise ValueError("Automated updates may change only the version and three checksums.")
    if stable_version(version) <= stable_version(formula_fields(base)[0]):
        raise ValueError("An automated package update must advance the stable version.")
    return version


def run(*arguments, capture=False, env=None):
    print("+ " + " ".join(map(str, arguments)), flush=True)
    result = subprocess.run(
        list(map(str, arguments)), check=True, text=True,
        stdout=subprocess.PIPE if capture else None, env=env,
    )
    return result.stdout.strip() if capture else None


def api(path):
    return json.loads(run("gh", "api", path, capture=True))


def release_digests(release):
    if not release["tag_name"].startswith("v"):
        raise ValueError("Packaged stable release tags must start with v.")
    version = release["tag_name"].removeprefix("v")
    stable_version(version)
    if release["draft"] or release["prerelease"]:
        raise ValueError(f"Release v{version} is not a published stable release.")
    assets = {asset["name"]: asset for asset in release["assets"]}
    digests = {}
    for target in PLATFORMS:
        name = f"sendbox-{version}-{target}.tar.gz"
        if name not in assets:
            raise ValueError(f"Missing published release artifact: {name}")
        digest = assets[name].get("digest", "")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            raise ValueError(f"Missing GitHub SHA-256 digest for {name}")
        digests[target] = digest.removeprefix("sha256:")
    return digests


def verify_archive(version, target, expected, temporary):
    release = api(f"repos/{REPOSITORY}/releases/tags/v{version}")
    if release_digests(release)[target] != expected:
        raise ValueError(f"Formula and GitHub asset digests disagree for v{version}/{target}.")
    run("brew", "fetch", "--formula", TAP)
    archive = Path(run("brew", "--cache", "--formula", TAP, capture=True))
    actual = hashlib.sha256(archive.read_bytes()).hexdigest()
    name = f"sendbox-{version}-{target}.tar.gz"
    checksum = temporary / f"{name}.sha256"
    run(
        "gh", "release", "download", f"v{version}", "--repo", REPOSITORY,
        "--pattern", f"{name}.sha256", "--output", checksum,
    )
    fields = checksum.read_text().split()
    if fields != [expected, name] or actual != expected:
        raise ValueError(f"Downloaded bytes or adjacent checksum disagree for {name}")
    run(
        "gh", "attestation", "verify", archive, "--repo", REPOSITORY,
        "--signer-workflow", f"{REPOSITORY}/.github/workflows/release.yaml",
        "--source-ref", f"refs/tags/v{version}", "--deny-self-hosted-runners",
    )
    return archive


def verify_guest_bytes(archive, libexec):
    expected = {}
    with tarfile.open(archive, "r:gz") as payload:
        for member in payload.getmembers():
            parts = PurePosixPath(member.name).parts
            if PurePosixPath(member.name).is_absolute() or ".." in parts:
                raise ValueError(f"Unsafe release archive path: {member.name}")
            if len(parts) < 3 or parts[1] != "guest" or member.isdir():
                continue
            relative = PurePosixPath(*parts[1:])
            if ".." in relative.parts or not member.isfile():
                raise ValueError(f"Unexpected signed guest archive entry: {member.name}")
            installed = libexec / relative
            if installed.is_symlink() or not installed.is_file():
                raise ValueError(f"Missing or replaced signed guest file: {relative}")
            expected[str(relative)] = hashlib.sha256(payload.extractfile(member).read()).hexdigest()
            if hashlib.sha256(installed.read_bytes()).hexdigest() != expected[str(relative)]:
                raise ValueError(f"Homebrew altered signed guest bytes: {relative}")
    installed_files = {
        str(path.relative_to(libexec)) for path in (libexec / "guest").rglob("*")
        if not path.is_dir()
    }
    if not expected or installed_files != set(expected):
        raise ValueError("Installed guest payload has missing or unexpected files.")


def verify_linkage(libexec):
    if sys.platform != "linux":
        return
    prefix = Path(run("brew", "--prefix", capture=True)).resolve()
    output = run("ldd", libexec / "sendbox", capture=True)
    print(output)
    if "not found" in output:
        raise ValueError("The installed Linux CLI has unresolved runtime libraries.")
    paths = re.findall(r"(?:=>\s+|^\s*)(/[^\s]+)", output, re.MULTILINE)
    if not paths or any(not Path(path).resolve().is_relative_to(prefix) for path in paths):
        raise ValueError("Linux CLI linkage escaped Homebrew and used host distribution libraries.")
    run("brew", "linkage", "--test", TAP)


def snapshot(*roots):
    return {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for root in roots for path in root.rglob("*") if path.is_file()
    }


def smoke(binary, version, home, project):
    environment = os.environ | {
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "XDG_DATA_HOME": str(home / ".local/share"),
    }
    if version not in run(binary, "--version", capture=True, env=environment).split():
        raise ValueError(f"The installed CLI did not report {version}.")
    if "Usage:" not in run(binary, "--help", capture=True, env=environment):
        raise ValueError("CLI startup/help smoke check failed.")
    configuration = project / ".sendbox.yaml"
    if not configuration.exists():
        run(binary, "init", "--project", project, "--agent", "custom", env=environment)
    run(binary, "policy", "validate", "--config", configuration, env=environment)
    completions = run(
        binary, "completions", "print", "--shell", "bash", capture=True, env=environment
    )
    if "sendbox" not in completions:
        raise ValueError("CLI completion generation failed.")


def lifecycle(formula):
    original = formula.read_text()
    current, current_digests = formula_fields(original)
    target = (
        "macos-arm64" if sys.platform == "darwin"
        else "linux-aarch64" if platform.machine() in ("aarch64", "arm64")
        else "linux-x86_64"
    )
    releases = api(f"repos/{REPOSITORY}/releases?per_page=100")
    earlier = [
        release for release in releases
        if not release["draft"] and not release["prerelease"]
        and release["tag_name"].startswith("v")
        and STABLE.fullmatch(release["tag_name"].removeprefix("v"))
        and stable_version(release["tag_name"].removeprefix("v")) < stable_version(current)
        and all(
            any(asset["name"] == f'sendbox-{release["tag_name"][1:]}-{item}.tar.gz'
                for asset in release["assets"])
            for item in PLATFORMS
        )
    ]
    if not earlier:
        raise ValueError("No earlier packaged stable release is available for a real brew upgrade.")
    previous = max(earlier, key=lambda item: stable_version(item["tag_name"][1:]))
    old_version = previous["tag_name"][1:]
    old_formula = with_release(original, old_version, release_digests(previous))
    prefix = Path(run("brew", "--prefix", capture=True))
    binary = prefix / "bin/sendbox"
    installed_names = run("brew", "list", "--formula", capture=True).splitlines()
    if binary.exists() or binary.is_symlink() or "sendbox" in installed_names or TAP in installed_names:
        raise ValueError("Refusing to replace an existing Sendbox installation.")

    with tempfile.TemporaryDirectory(prefix="sendbox-lifecycle-", dir=os.environ["RUNNER_TEMP"]) as directory:
        temporary = Path(directory)
        home, project = temporary / "home", temporary / "project"
        (home / ".sendbox").mkdir(parents=True)
        project.mkdir()
        (home / ".sendbox/retained.json").write_text('{"fixture": "mock user data"}\n')
        (project / "retained.txt").write_text("mock project data\n")
        current_archive = verify_archive(current, target, current_digests[target], temporary)
        installed = False
        try:
            formula.write_text(old_formula)
            old_archive = verify_archive(
                old_version, target, release_digests(previous)[target], temporary
            )
            run("brew", "install", "--formula", TAP)
            installed = True
            libexec = Path(run("brew", "--prefix", TAP, capture=True)) / "libexec"
            verify_guest_bytes(old_archive, libexec)
            verify_linkage(libexec)
            smoke(binary, old_version, home, project)
            retained = snapshot(home, project)
            formula.write_text(original)
            run("brew", "upgrade", "--formula", TAP)
            libexec = Path(run("brew", "--prefix", TAP, capture=True)) / "libexec"
            verify_guest_bytes(current_archive, libexec)
            verify_linkage(libexec)
            smoke(binary, current, home, project)
            if snapshot(home, project) != retained:
                raise ValueError("Upgrade changed mock user or project data.")
            run("brew", "test", TAP)
            run("brew", "cleanup", TAP)
            run("brew", "uninstall", "--formula", TAP)
            installed = False
            installed_names = run("brew", "list", "--formula", capture=True).splitlines()
            if binary.exists() or binary.is_symlink() or "sendbox" in installed_names or TAP in installed_names:
                raise ValueError("Homebrew did not remove the Sendbox installation.")
            if snapshot(home, project) != retained:
                raise ValueError("Uninstall changed mock user or project data.")
        finally:
            formula.write_text(original)
            if installed:
                run("brew", "uninstall", "--force", "--formula", TAP)

    message = (
        f"Passed Sendbox ({target}): verified install {old_version}, real brew upgrade "
        f"to {current}, version/help/init/policy/completions, signed guest byte preservation, "
        "uninstall and mock user/project data preservation. No VM or agent launched."
    )
    print(message)
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as summary:
        summary.write(message + "\n")


def open_pr():
    branch = os.environ["GITHUB_REF_NAME"]
    if os.environ["GITHUB_EVENT_NAME"] != "push" or os.environ["GITHUB_REF"] != f"refs/heads/{branch}":
        raise ValueError("Automated draft PR creation requires a branch push.")
    repository = os.environ["GITHUB_REPOSITORY"]
    if repository != "mbianchidev/homebrew-tap":
        raise ValueError("Unexpected repository for Sendbox tap automation.")
    paths = run("git", "diff", "--name-only", "origin/main...HEAD", capture=True).splitlines()
    base = run("git", "show", "origin/main:Formula/sendbox.rb", capture=True)
    head = Path("Formula/sendbox.rb").read_text().strip()
    version = validate_update(base, head, branch, paths)
    latest = api(f"repos/{REPOSITORY}/releases/latest")
    release_digests(latest)
    if latest["tag_name"] != f"v{version}":
        raise ValueError("Only the latest published stable Sendbox release may open an update PR.")
    if formula_fields(head)[1] != release_digests(latest):
        raise ValueError("The update formula does not match the published GitHub asset digests.")
    existing = json.loads(run(
        "gh", "pr", "list", "--repo", repository, "--head", branch, "--base", "main",
        "--state", "all", "--json", "url,state,isDraft", capture=True,
    ))
    if existing:
        for pull_request in existing:
            print(f'Existing {pull_request["state"]} PR: {pull_request["url"]}; not creating a duplicate.')
        return
    result = subprocess.run([
        "gh", "pr", "create", "--repo", repository, "--head", branch, "--base", "main",
        "--draft", "--title", f"sendbox {version}",
        "--body", (
            f"Update only Formula/sendbox.rb to the verified stable Sendbox v{version} artifacts.\n\n"
            "Tap validation and isolated package lifecycle checks passed on this branch. "
            "This is a draft for human review; no merge or publication is automatic."
        ),
    ], check=False)
    if result.returncode:
        print(
            "::error::Draft PR creation failed. In this tap's Settings > Actions > General > "
            "Workflow permissions, enable 'Allow GitHub Actions to create and approve pull requests', "
            "or create the draft manually from the validated automation branch. "
            "No repository settings were changed.",
            file=sys.stderr,
        )
        raise SystemExit(result.returncode)


def main():
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("TAP_CI_RUNNER_ENVIRONMENT") != "github-hosted":
        raise ValueError("These operations require a disposable GitHub-hosted runner.")
    if sys.argv[1:] == ["open-pr"]:
        open_pr()
    elif len(sys.argv) == 3 and sys.argv[1] == "lifecycle":
        lifecycle(Path(sys.argv[2]))
    else:
        raise ValueError("Usage: sendbox.py lifecycle FORMULA | open-pr")


if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        print(f"::error::{error}", file=sys.stderr)
        raise SystemExit(1) from error
