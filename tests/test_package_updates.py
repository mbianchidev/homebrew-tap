import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from scripts.ci import package_updates as UPDATES


def mock_definition(package, version="1.2.3"):
    lines = ['class MockPackage', f'  version "{version}"']
    if package.name == "killswitch":
        lines.extend([
            f'  sha256 "{"a" * 64}"',
            f'  url "https://github.com/{package.repository}/releases/download/v#{{version}}/KillSwitch.dmg"',
        ])
    else:
        url_version = "#{version}" if package.name == "sendbox" else version
        for name in package.asset_names(url_version):
            lines.extend([
                f'    url "https://github.com/{package.repository}/releases/download/v{url_version}/{name}"',
                f'    sha256 "{"a" * 64}"',
            ])
    lines.extend(['  # Mock non-release logic must remain byte-identical.', '  skip_clean "libexec"', "end"])
    return "\n".join(lines) + "\n"


def mock_release(package, version="9.8.7"):
    contents = {
        name: f"mock artifact {name}\n".encode()
        for name in package.asset_names(version)
    }
    if package.manifest:
        contents[package.manifest] = "".join(
            f"{hashlib.sha256(data).hexdigest()}  {name}\n"
            for name, data in contents.items()
        ).encode()
    else:
        for name, data in list(contents.items()):
            checksum = hashlib.sha256(data).hexdigest()
            contents[f"{name}.sha256"] = (
                f"{checksum}\n" if package.name == "killswitch"
                else f"{checksum}  {name}\n"
            ).encode()
    release = {
        "tag_name": f"v{version}",
        "draft": False,
        "prerelease": False,
        "assets": [
            {
                "name": name,
                "digest": f"sha256:{hashlib.sha256(data).hexdigest()}",
                "browser_download_url":
                    f"https://github.com/{package.repository}/releases/download/v{version}/{name}",
            }
            for name, data in contents.items()
        ],
    }
    return release, contents


class ReleaseUpdateTests(unittest.TestCase):
    def test_updates_only_release_fields_for_every_package(self):
        for package in UPDATES.PACKAGES.values():
            with self.subTest(package=package.name):
                original = mock_definition(package)
                current = UPDATES.current_version(original)
                release, _ = mock_release(package)
                version, updated = UPDATES.prepare_update(package, original, release)
                self.assertEqual(version, "9.8.7")
                self.assertNotEqual(original, updated)
                self.assertEqual(UPDATES.current_version(updated), version)
                old_digests = {}
                for name in package.asset_names(current):
                    if package.name == "sendbox":
                        target = name.removeprefix(f"sendbox-{current}-").removesuffix(".tar.gz")
                        old_digests[name] = UPDATES.sendbox.formula_fields(original)[1][target]
                    else:
                        pattern = UPDATES.definition_pattern(package, current, name)
                        old_digests[name] = pattern.search(original).group("digest")
                restored = UPDATES.update_text(package, updated, current, old_digests)
                self.assertEqual(restored, original)

    def test_same_or_older_releases_do_not_update(self):
        for package in UPDATES.PACKAGES.values():
            original = mock_definition(package)
            for version in (UPDATES.current_version(original), "0.0.0"):
                with self.subTest(package=package.name, version=version):
                    release, _ = mock_release(package, version)
                    self.assertIsNone(UPDATES.prepare_update(package, original, release))

    def test_rejects_nonstable_or_unpublished_releases(self):
        release, _ = mock_release(UPDATES.PACKAGES["killswitch"])
        for change in (
            {"draft": True}, {"prerelease": True}, {"tag_name": "v9.8.7-rc.1"},
            {"tag_name": "9.8.7"}, {"tag_name": "v09.8.7"},
            {"tag_name": "v9.8.7+build"}, {"draft": None},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                UPDATES.release_version(release | change)

    def test_rejects_missing_duplicate_unpinned_and_invalid_assets(self):
        for package in UPDATES.PACKAGES.values():
            release, _ = mock_release(package)
            malformed = []
            for key, value in (
                ("digest", None), ("digest", "sha256:not-a-digest"),
                ("browser_download_url", "https://example.invalid/unversioned"),
            ):
                changed = copy.deepcopy(release)
                changed["assets"][0][key] = value
                malformed.append(changed)
            malformed.extend([
                release | {"assets": release["assets"][1:]},
                release | {"assets": release["assets"] + [release["assets"][0]]},
            ])
            for changed in malformed:
                with self.subTest(package=package.name, changed=changed), self.assertRaises(ValueError):
                    UPDATES.release_digests(package, changed)

    def test_rejects_missing_or_duplicate_definition_fields(self):
        for package in UPDATES.PACKAGES.values():
            original = mock_definition(package)
            release, _ = mock_release(package)
            for text in (
                original.replace('sha256 "', 'checksum "', 1),
                original + '\n  version "8.0.0"\n',
            ):
                with self.subTest(package=package.name), self.assertRaises(ValueError):
                    UPDATES.prepare_update(package, text, release)

    def test_preserves_sendbox_activation_floor(self):
        package = UPDATES.PACKAGES["sendbox"]
        original = mock_definition(package)
        original = UPDATES.sendbox.with_release(
            original, "0.1.0", dict.fromkeys(UPDATES.sendbox.PLATFORMS, "a" * 64)
        )
        release, _ = mock_release(package, "0.2.2")
        with self.assertRaisesRegex(ValueError, "patched stable"):
            UPDATES.prepare_update(package, original, release)

    def verify(self, package, release, contents):
        def download(*arguments, **kwargs):
            self.assertEqual(arguments[:3], ("gh", "release", "download"))
            name = arguments[arguments.index("--pattern") + 1]
            output = Path(arguments[arguments.index("--output") + 1])
            output.write_bytes(contents[name])

        with mock.patch.object(UPDATES, "run", side_effect=download), \
                mock.patch.object(UPDATES.sendbox, "verify_attestation") as attestation:
            UPDATES.verify_release(package, release)
            self.assertEqual(
                attestation.call_count,
                len(package.asset_names(UPDATES.release_version(release)))
                if package.name == "sendbox" else 0,
            )

    def test_verifies_actual_artifact_and_checksum_bytes_and_sendbox_provenance(self):
        for package in UPDATES.PACKAGES.values():
            with self.subTest(package=package.name):
                self.verify(package, *mock_release(package))

    def test_rejects_changed_download_bytes(self):
        for package in UPDATES.PACKAGES.values():
            release, contents = mock_release(package)
            contents[package.asset_names("9.8.7")[0]] = b"altered mock bytes"
            with self.subTest(package=package.name), self.assertRaisesRegex(ValueError, "digest"):
                self.verify(package, release, contents)

    def test_rejects_published_checksum_disagreement_or_duplicate_entries(self):
        for package in UPDATES.PACKAGES.values():
            for duplicate in (False, True):
                release, contents = mock_release(package)
                name = package.checksum_names("9.8.7")[0]
                contents[name] = (
                    contents[name] * 2 if duplicate
                    else contents[name].replace(contents[name][:64], b"0" * 64, 1)
                )
                for asset in release["assets"]:
                    if asset["name"] == name:
                        asset["digest"] = f"sha256:{hashlib.sha256(contents[name]).hexdigest()}"
                with self.subTest(package=package.name, duplicate=duplicate), self.assertRaises(ValueError):
                    self.verify(package, release, contents)

    def test_apply_requires_hosted_main_revision_and_clean_worktree(self):
        environment = {
            "GITHUB_ACTIONS": "true",
            "TAP_CI_RUNNER_ENVIRONMENT": "github-hosted",
            "GITHUB_REPOSITORY": UPDATES.REPOSITORY,
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_SHA": "a" * 40,
        }
        cases = [
            {"GITHUB_ACTIONS": "false"},
            {"TAP_CI_RUNNER_ENVIRONMENT": "self-hosted"},
            {"GITHUB_REPOSITORY": "mock/unrelated"},
            {"GITHUB_REF": "refs/heads/feature/mock"},
            {"GITHUB_SHA": "b" * 40},
        ]
        for change in cases:
            with self.subTest(change=change), mock.patch.dict(os.environ, environment | change, clear=True), \
                    mock.patch.object(UPDATES, "git", return_value="a" * 40), \
                    self.assertRaises(ValueError):
                UPDATES.require_hosted_main()
        with mock.patch.dict(os.environ, environment, clear=True), \
                mock.patch.object(UPDATES, "git", side_effect=["a" * 40, " M mock.rb\n"]), \
                self.assertRaisesRegex(ValueError, "clean"):
            UPDATES.require_hosted_main()

    def test_rejects_noncanonical_cask_url(self):
        package = UPDATES.PACKAGES["killswitch"]
        original = mock_definition(package).replace("v#{version}/KillSwitch.dmg", "latest/KillSwitch.dmg")
        release, _ = mock_release(package)
        with self.assertRaisesRegex(ValueError, "canonical"):
            UPDATES.prepare_update(package, original, release)

    def test_dry_run_verifies_without_modifying_files_or_publishing(self):
        package = UPDATES.PACKAGES["killswitch"]
        release, _ = mock_release(package)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / package.path
            path.parent.mkdir()
            original = mock_definition(package)
            path.write_text(original)
            with mock.patch.object(UPDATES, "ROOT", root), \
                    mock.patch.object(UPDATES.sendbox, "api", return_value=release), \
                    mock.patch.object(UPDATES, "verify_release") as verify, \
                    mock.patch.object(UPDATES, "publish_update") as publish, \
                    mock.patch.object(UPDATES, "git") as git:
                UPDATES.main(["--package", package.name, "--dry-run"])
                verify.assert_called_once_with(package, release)
                publish.assert_not_called()
                git.assert_not_called()
            self.assertEqual(path.read_text(), original)

    def test_empty_tap_skips_absent_packages_without_network_or_writes(self):
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(UPDATES, "ROOT", Path(directory)), \
                mock.patch.object(UPDATES.sendbox, "api") as api, \
                mock.patch.object(UPDATES, "publish_update") as publish:
            UPDATES.main(["--dry-run"])
            api.assert_not_called()
            publish.assert_not_called()


class PublishingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mock-package-updates-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.checkout = root / "checkout"
        self.remote = root / "remote.git"
        self.environment = os.environ | {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "UPDATE_GIT_NAME": "Mock maintainer",
            "UPDATE_GIT_EMAIL": "mock@example.invalid",
        }
        self.command("git", "init", "--bare", self.remote)
        self.command("git", "init", "--initial-branch=main", self.checkout)
        self.command("git", "-C", self.checkout, "config", "user.name", "Mock maintainer")
        self.command("git", "-C", self.checkout, "config", "user.email", "mock@example.invalid")
        self.command("git", "-C", self.checkout, "config", "core.hooksPath", os.devnull)
        self.package = UPDATES.PACKAGES["killswitch"]
        path = self.checkout / self.package.path
        path.parent.mkdir()
        path.write_text(mock_definition(self.package))
        self.command("git", "-C", self.checkout, "add", ".")
        self.command("git", "-C", self.checkout, "commit", "--no-gpg-sign", "-m", "Mock base")
        self.command("git", "-C", self.checkout, "remote", "add", "origin", self.remote)
        self.command("git", "-C", self.checkout, "push", "origin", "main")
        self.base = self.command("git", "-C", self.checkout, "rev-parse", "HEAD")
        release, _ = mock_release(self.package)
        self.version, self.updated = UPDATES.prepare_update(self.package, path.read_text(), release)
        self.release = release
        self.pull_requests = []
        self.workflow_runs = []
        self.calls = []
        for patcher in (
            mock.patch.object(UPDATES, "ROOT", self.checkout),
            mock.patch.object(UPDATES, "run", side_effect=self.run_command),
            mock.patch.object(UPDATES, "verify_release"),
            mock.patch.dict(os.environ, self.environment, clear=True),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def command(self, *arguments):
        return subprocess.run(
            list(map(str, arguments)), check=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.environment,
        ).stdout.strip()

    def run_command(self, *arguments, **kwargs):
        self.calls.append(arguments)
        if arguments[0] == "git":
            return self.command(*arguments)
        if arguments[:3] == ("gh", "pr", "list"):
            return json.dumps(self.pull_requests)
        if arguments[:3] == ("gh", "pr", "create"):
            self.pull_requests.append({
                "url": "https://example.invalid/mock/pr/1",
                "state": "OPEN", "isDraft": True,
                "headRefOid": self.command("git", "-C", self.checkout, "rev-parse", "HEAD"),
            })
            return self.pull_requests[-1]["url"]
        if arguments[:3] == ("gh", "run", "list"):
            return json.dumps(self.workflow_runs)
        if arguments[:3] == ("gh", "workflow", "run"):
            return ""
        self.fail(f"Unexpected command: {arguments}")

    def publish(self):
        return UPDATES.publish_update(self.package, self.release, self.updated, self.base)

    def test_creates_one_scoped_draft_and_explicitly_dispatches_full_ci(self):
        self.publish()
        creates = [call for call in self.calls if call[:3] == ("gh", "pr", "create")]
        self.assertEqual(len(creates), 1)
        self.assertIn("--draft", creates[0])
        self.assertTrue(any(call[:4] == ("gh", "workflow", "run", "ci.yml") for call in self.calls))
        files = self.command("git", "-C", self.checkout, "diff", "--name-only", self.base, "HEAD")
        self.assertEqual(files, self.package.path)
        author = self.command("git", "-C", self.checkout, "log", "-1", "--format=%an <%ae>")
        self.assertEqual(author, "Mock maintainer <mock@example.invalid>")
        commits = [call for call in self.calls if "commit" in call]
        self.assertIn("--no-gpg-sign", commits[0])
        self.assertFalse(any("--force" in str(argument) for call in self.calls for argument in call))

    def test_existing_open_pr_recovers_missing_ci_without_duplicate_or_rewrite(self):
        self.publish()
        self.calls.clear()
        self.publish()
        self.assertFalse(any("commit" in call or "push" in call for call in self.calls))
        self.assertFalse(any(call[:3] == ("gh", "pr", "create") for call in self.calls))
        self.assertTrue(any(call[:3] == ("gh", "workflow", "run") for call in self.calls))

    def test_existing_closed_pr_is_not_reopened_or_duplicated(self):
        for state in ("CLOSED", "MERGED"):
            with self.subTest(state=state):
                self.calls.clear()
                self.pull_requests = [{"state": state, "url": "https://example.invalid/mock/pr/1"}]
                self.publish()
                self.assertEqual(len(self.calls), 1)

    def test_verification_failure_cannot_push_a_branch_or_create_a_pr(self):
        with mock.patch.object(UPDATES, "verify_release", side_effect=ValueError("Mock digest mismatch")), \
                self.assertRaisesRegex(ValueError, "digest"):
            self.publish()
        self.assertFalse(any("push" in call or "commit" in call for call in self.calls))
        self.assertFalse(any(call[:3] == ("gh", "pr", "create") for call in self.calls))

    def test_reuses_matching_existing_branch_after_interrupted_pr_creation(self):
        self.publish()
        self.pull_requests.clear()
        self.calls.clear()
        self.publish()
        self.assertFalse(any("commit" in call or "push" in call for call in self.calls))
        self.assertTrue(any(call[:3] == ("gh", "pr", "create") for call in self.calls))

    def test_refuses_to_overwrite_unrelated_changes_on_existing_branch(self):
        self.publish()
        (self.checkout / "mock-unrelated.txt").write_text("mock unrelated change\n")
        self.command("git", "-C", self.checkout, "add", ".")
        self.command("git", "-C", self.checkout, "commit", "--no-gpg-sign", "-m", "Mock unrelated")
        self.command("git", "-C", self.checkout, "push", "origin", "HEAD")
        self.calls.clear()
        with self.assertRaisesRegex(ValueError, "existing branch"):
            self.publish()
        self.assertFalse(any("push" in call for call in self.calls))

    def test_reuses_matching_ci_and_reports_existing_failure(self):
        self.publish()
        head = self.pull_requests[0]["headRefOid"]
        for status, conclusion in (("in_progress", ""), ("completed", "success"), ("completed", "failure")):
            self.workflow_runs = [{
                "headSha": head, "event": "workflow_dispatch", "status": status,
                "conclusion": conclusion, "url": "https://example.invalid/mock/run/1",
            }]
            self.calls.clear()
            if conclusion == "failure":
                with self.assertRaisesRegex(ValueError, "CI"):
                    self.publish()
            else:
                self.publish()
            self.assertFalse(any(call[:3] == ("gh", "workflow", "run") for call in self.calls))


if __name__ == "__main__":
    unittest.main()
