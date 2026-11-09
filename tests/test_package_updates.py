import base64
import copy
import hashlib
import io
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
                    mock.patch.object(UPDATES, "publish_updates") as publish, \
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
                mock.patch.object(UPDATES, "publish_updates") as publish:
            UPDATES.main(["--dry-run"])
            api.assert_not_called()
            publish.assert_not_called()

    def test_hosted_publication_collects_all_pending_packages_before_one_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            releases = {}
            for package in UPDATES.PACKAGES.values():
                path = root / package.path
                path.parent.mkdir(exist_ok=True)
                path.write_text(mock_definition(package))
                releases[f"repos/{package.repository}/releases/latest"] = mock_release(package)[0]
            with mock.patch.object(UPDATES, "ROOT", root), \
                    mock.patch.object(UPDATES, "require_hosted_main"), \
                    mock.patch.object(UPDATES, "retire_updates"), \
                    mock.patch.object(UPDATES, "git", return_value="a" * 40), \
                    mock.patch.object(UPDATES.sendbox, "api", side_effect=releases.__getitem__), \
                    mock.patch.object(UPDATES, "publish_updates") as publish:
                UPDATES.main([])
                publish.assert_called_once()
                updates, base = publish.call_args.args
                self.assertEqual(base, "a" * 40)
                self.assertEqual({package.name for package, _, _ in updates}, set(UPDATES.PACKAGES))

    def test_publication_rejects_single_package_mode_and_merge_requires_hosted_main(self):
        with mock.patch.object(UPDATES, "require_hosted_main"), \
                mock.patch.object(UPDATES, "publish_updates") as publish, \
                mock.patch.object(UPDATES, "retire_updates") as retire, \
                self.assertRaisesRegex(ValueError, "batch"):
            UPDATES.main(["--package", "killswitch"])
        publish.assert_not_called()
        retire.assert_not_called()
        with mock.patch.object(UPDATES, "require_hosted_main", side_effect=ValueError("Mock non-hosted")), \
                mock.patch.object(UPDATES, "merge_update") as merge, \
                self.assertRaisesRegex(ValueError, "non-hosted"):
            UPDATES.main(["--merge-run", "123", "--dry-run"])
        merge.assert_not_called()


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
        for package in UPDATES.PACKAGES.values():
            path = self.checkout / package.path
            path.parent.mkdir(exist_ok=True)
            path.write_text(mock_definition(package))
        self.command("git", "-C", self.checkout, "add", ".")
        self.command("git", "-C", self.checkout, "commit", "--no-gpg-sign", "-m", "Mock base")
        self.command("git", "-C", self.checkout, "remote", "add", "origin", self.remote)
        self.command("git", "-C", self.checkout, "push", "origin", "main")
        self.base = self.command("git", "-C", self.checkout, "rev-parse", "HEAD")
        release, _ = mock_release(self.package)
        original = (self.checkout / self.package.path).read_text()
        self.version, self.updated = UPDATES.prepare_update(self.package, original, release)
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
                "number": 1,
                "url": "https://example.invalid/mock/pr/1",
                "state": "OPEN", "isDraft": False,
                "headRefOid": self.command("git", "-C", self.checkout, "rev-parse", "HEAD"),
            })
            return self.pull_requests[-1]["url"]
        if arguments[:3] == ("gh", "run", "list"):
            return json.dumps(self.workflow_runs)
        if arguments[:3] == ("gh", "workflow", "run"):
            return ""
        self.fail(f"Unexpected command: {arguments}")

    def publish(self):
        return UPDATES.publish_updates([(self.package, self.release, self.updated)], self.base)

    def test_creates_one_scoped_ready_pr_and_explicitly_dispatches_full_ci(self):
        self.publish()
        creates = [call for call in self.calls if call[:3] == ("gh", "pr", "create")]
        self.assertEqual(len(creates), 1)
        self.assertNotIn("--draft", creates[0])
        self.assertTrue(any(call[:4] == ("gh", "workflow", "run", "ci.yml") for call in self.calls))
        files = self.command("git", "-C", self.checkout, "diff", "--name-only", self.base, "HEAD")
        self.assertEqual(files, self.package.path)
        author = self.command("git", "-C", self.checkout, "log", "-1", "--format=%an <%ae>")
        self.assertEqual(author, "Mock maintainer <mock@example.invalid>")
        commits = [call for call in self.calls if "commit" in call]
        self.assertIn("--no-gpg-sign", commits[0])
        self.assertFalse(any("--force" in str(argument) for call in self.calls for argument in call))

    def test_batches_simultaneous_releases_into_one_pr_and_one_ci_run(self):
        package = UPDATES.PACKAGES["sendbox"]
        release, _ = mock_release(package)
        original = (self.checkout / package.path).read_text()
        _, updated = UPDATES.prepare_update(package, original, release)
        UPDATES.publish_updates([
            (self.package, self.release, self.updated), (package, release, updated),
        ], self.base)
        self.assertEqual(len(self.pull_requests), 1)
        files = self.command("git", "-C", self.checkout, "diff", "--name-only", self.base, "HEAD")
        self.assertEqual(files.splitlines(), sorted([self.package.path, package.path]))
        dispatches = [call for call in self.calls if call[:4] == ("gh", "workflow", "run", "ci.yml")]
        self.assertEqual(len(dispatches), 1)
        self.assertEqual(UPDATES.verify_release.call_count, 2)

    def test_batch_identity_is_order_independent_and_binds_base_and_definition_bytes(self):
        package = UPDATES.PACKAGES["sendbox"]
        release, _ = mock_release(package)
        _, updated = UPDATES.prepare_update(
            package, (self.checkout / package.path).read_text(), release,
        )
        updates = [(self.package, self.release, self.updated), (package, release, updated)]
        branch = UPDATES.update_branch(updates, self.base)
        self.assertEqual(branch, UPDATES.update_branch(list(reversed(updates)), self.base))
        self.assertNotEqual(branch, UPDATES.update_branch(updates, "b" * 40))
        self.assertNotEqual(
            branch, UPDATES.update_branch([(self.package, self.release, self.updated + "\n")], self.base),
        )

    def test_every_candidate_is_verified_before_any_batch_files_are_written(self):
        package = UPDATES.PACKAGES["sendbox"]
        release, _ = mock_release(package)
        original = (self.checkout / package.path).read_text()
        _, updated = UPDATES.prepare_update(package, original, release)
        with mock.patch.object(
            UPDATES, "verify_release", side_effect=[None, ValueError("Mock second artifact mismatch")],
        ), self.assertRaisesRegex(ValueError, "second artifact"):
            UPDATES.publish_updates([
                (self.package, self.release, self.updated), (package, release, updated),
            ], self.base)
        self.assertEqual(self.command("git", "-C", self.checkout, "status", "--porcelain"), "")
        self.assertFalse(any("push" in call or "commit" in call for call in self.calls))
        self.assertEqual(self.pull_requests, [])

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

    def test_duplicate_pr_identity_is_rejected_without_writes(self):
        self.pull_requests = [{"state": "OPEN"}, {"state": "OPEN"}]
        with self.assertRaisesRegex(ValueError, "Multiple PRs"):
            self.publish()
        self.assertFalse(any("commit" in call or "push" in call for call in self.calls))

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
                "databaseId": 123,
                "headSha": head, "event": "workflow_dispatch", "status": status,
                "conclusion": conclusion, "url": "https://example.invalid/mock/run/1",
            }]
            self.calls.clear()
            if conclusion == "failure":
                with self.assertRaisesRegex(ValueError, "CI"):
                    self.publish()
            else:
                self.publish()
            self.assertFalse(any(call[:4] == ("gh", "workflow", "run", "ci.yml") for call in self.calls))
            merges = [
                call for call in self.calls
                if call[:4] == ("gh", "workflow", "run", "merge-package-updates.yml")
            ]
            self.assertEqual(len(merges), 1 if conclusion == "success" else 0)


class AutomaticMergeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mock-package-merge-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.base = "a" * 40
        self.head = "b" * 40
        self.package = UPDATES.PACKAGES["killswitch"]
        self.release, _ = mock_release(self.package)
        self.responses = {}
        self.prefix = f"repos/{UPDATES.REPOSITORY}"
        for package in UPDATES.PACKAGES.values():
            path = self.root / package.path
            path.parent.mkdir(exist_ok=True)
            release, _ = mock_release(package, "1.2.3")
            path.write_text(UPDATES.update_text(
                package, mock_definition(package), "1.2.3", UPDATES.release_digests(package, release),
            ))
            self.responses[f"repos/{package.repository}/releases/latest"] = release
        original = (self.root / self.package.path).read_text()
        _, self.updated = UPDATES.prepare_update(self.package, original, self.release)
        self.branch = UPDATES.update_branch([(self.package, self.release, self.updated)], self.base)
        self.responses[f"repos/{self.package.repository}/releases/latest"] = self.release
        self.responses[f"{self.prefix}/actions/runs/123"] = {
            "id": 123, "path": ".github/workflows/ci.yml", "event": "workflow_dispatch",
            "status": "completed", "conclusion": "success",
            "head_sha": self.head, "head_branch": self.branch,
            "head_repository": {"full_name": UPDATES.REPOSITORY},
        }
        self.pull = {
            "number": 1, "state": "open", "draft": False, "changed_files": 1,
            "user": {"login": "github-actions[bot]", "type": "Bot"},
            "head": {"sha": self.head, "ref": self.branch, "repo": {"full_name": UPDATES.REPOSITORY}},
            "base": {"sha": self.base, "ref": "main", "repo": {"full_name": UPDATES.REPOSITORY}},
        }
        self.responses[f"{self.prefix}/pulls/1"] = self.pull
        self.responses[f"{self.prefix}/pulls/1/files?per_page=100"] = [
            {"filename": self.package.path, "status": "modified"},
        ]
        self.responses[f"{self.prefix}/commits/main"] = {"sha": self.base}
        self.responses[f"{self.prefix}/compare/{self.base}...{self.head}"] = {
            "merge_base_commit": {"sha": self.base}, "total_commits": 1, "status": "ahead",
        }
        self.responses[f"{self.prefix}/contents/{self.package.path}?ref={self.head}"] = {
            "encoding": "base64", "content": base64.b64encode(self.updated.encode()).decode(),
        }
        names = ["validate"] + [
            f"Package lifecycle ({runner})"
            for runner in ("macos-15-intel", "macos-latest", "ubuntu-latest", "ubuntu-24.04-arm")
        ]
        jobs = [
            {"name": name, "status": "completed", "conclusion": "success"} for name in names
        ]
        self.responses[f"{self.prefix}/actions/runs/123/jobs?per_page=100"] = {
            "total_count": len(jobs), "jobs": jobs,
        }
        self.responses[f"{self.prefix}/commits/{self.head}/check-runs?per_page=100"] = {
            "total_count": len(jobs), "check_runs": copy.deepcopy(jobs),
        }
        self.responses[f"{self.prefix}/commits/{self.head}/status"] = {
            "total_count": 0, "state": "pending", "statuses": [],
        }
        self.reviews = {
            "reviewThreads": {"nodes": [], "pageInfo": {"hasNextPage": False}},
            "reviews": {"nodes": [], "pageInfo": {"hasNextPage": False}},
        }
        self.commands = []
        self.pull_reads = 0
        self.advance_head = False
        for patcher in (
            mock.patch.object(UPDATES, "ROOT", self.root),
            mock.patch.object(UPDATES, "git", return_value=self.base),
            mock.patch.object(UPDATES.sendbox, "api", side_effect=self.api),
            mock.patch.object(UPDATES, "run", side_effect=self.run_command),
            mock.patch.object(UPDATES, "verify_release"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def api(self, path):
        self.assertIn(path, self.responses)
        if path == f"{self.prefix}/pulls/1":
            self.pull_reads += 1
            if self.advance_head and self.pull_reads > 1:
                changed = copy.deepcopy(self.pull)
                changed["head"]["sha"] = "c" * 40
                return changed
        return copy.deepcopy(self.responses[path])

    def run_command(self, *arguments, **kwargs):
        self.commands.append(arguments)
        if arguments[:3] == ("gh", "pr", "list"):
            return json.dumps([{"number": 1}])
        if arguments[:3] == ("gh", "api", "graphql"):
            return json.dumps({"data": {"repository": {"pullRequest": self.reviews}}})
        if arguments[:4] == ("gh", "api", "--method", "PUT"):
            return json.dumps({"merged": True, "sha": "c" * 40})
        if arguments[:3] == ("gh", "workflow", "run"):
            return ""
        self.fail(f"Unexpected command: {arguments}")

    def assert_no_merge(self):
        self.assertFalse(any(call[:4] == ("gh", "api", "--method", "PUT") for call in self.commands))

    def test_merges_verified_bot_release_only_after_all_native_jobs_and_reviews_pass(self):
        UPDATES.merge_update(123)
        merge = [call for call in self.commands if call[:4] == ("gh", "api", "--method", "PUT")]
        self.assertEqual(len(merge), 1)
        self.assertIn(f"sha={self.head}", merge[0])
        self.assertIn("merge_method=squash", merge[0])
        UPDATES.verify_release.assert_called_once_with(self.package, self.release)
        self.assertIn(("gh", "workflow", "run", "ci.yml", "--repo", UPDATES.REPOSITORY, "--ref", "main"),
                      self.commands)

    def test_merge_dry_run_verifies_without_merge_or_workflow_dispatch(self):
        UPDATES.merge_update(123, dry_run=True)
        self.assert_no_merge()
        self.assertFalse(any(call[:3] == ("gh", "workflow", "run") for call in self.commands))
        UPDATES.verify_release.assert_called_once()

    def test_simultaneous_updates_for_all_registered_packages_merge_as_one_batch(self):
        updates = []
        for package in UPDATES.PACKAGES.values():
            release, _ = mock_release(package)
            _, updated = UPDATES.prepare_update(
                package, (self.root / package.path).read_text(), release,
            )
            updates.append((package, release, updated))
            self.responses[f"repos/{package.repository}/releases/latest"] = release
            self.responses[f"{self.prefix}/contents/{package.path}?ref={self.head}"] = {
                "encoding": "base64", "content": base64.b64encode(updated.encode()).decode(),
            }
        self.branch = UPDATES.update_branch(updates, self.base)
        self.responses[f"{self.prefix}/actions/runs/123"]["head_branch"] = self.branch
        self.pull["head"]["ref"] = self.branch
        self.pull["changed_files"] = len(updates)
        self.responses[f"{self.prefix}/pulls/1/files?per_page=100"] = [
            {"filename": package.path, "status": "modified"} for package, _, _ in updates
        ]
        UPDATES.merge_update(123)
        self.assertEqual(UPDATES.verify_release.call_count, len(UPDATES.PACKAGES))
        self.assertEqual(sum(call[:4] == ("gh", "api", "--method", "PUT") for call in self.commands), 1)

    def test_rejects_wrong_run_repository_event_revision_branch_or_result(self):
        run = self.responses[f"{self.prefix}/actions/runs/123"]
        for change in (
            {"head_repository": {"full_name": "mock/unrelated"}},
            {"event": "pull_request"}, {"path": ".github/workflows/mock.yml"},
            {"head_branch": "feature/mock"}, {"head_sha": "not-a-commit"},
            {"status": "in_progress"}, {"conclusion": "failure"},
        ):
            with self.subTest(change=change), mock.patch.dict(run, change), self.assertRaises(ValueError):
                UPDATES.merge_update(123)
            self.assert_no_merge()

    def test_rejects_draft_foreign_nonbot_or_changed_head_pr(self):
        for change in (
            {"draft": True}, {"user": {"login": "mock-maintainer", "type": "User"}},
            {"head": self.pull["head"] | {"sha": "c" * 40}},
            {"head": self.pull["head"] | {"repo": {"full_name": "mock/unrelated"}}},
            {"base": self.pull["base"] | {"ref": "feature/mock"}},
        ):
            with self.subTest(change=change), mock.patch.dict(self.pull, change), self.assertRaises(ValueError):
                UPDATES.merge_update(123)
            self.assert_no_merge()

    def test_rejects_changed_main_or_stale_ci_integration_base(self):
        for path, change in (
            (f"{self.prefix}/commits/main", {"sha": "c" * 40}),
            (f"{self.prefix}/compare/{self.base}...{self.head}",
             {"merge_base_commit": {"sha": "c" * 40}}),
        ):
            with self.subTest(path=path), mock.patch.dict(self.responses[path], change), \
                    self.assertRaises(ValueError):
                UPDATES.merge_update(123)
            self.assert_no_merge()

    def test_rejects_non_release_changes_missing_files_and_extra_paths(self):
        path = f"{self.prefix}/pulls/1/files?per_page=100"
        for files in (
            [], [{"filename": "scripts/ci/mock.py", "status": "modified"}],
            [{"filename": self.package.path, "status": "removed"}],
        ):
            with self.subTest(files=files), mock.patch.dict(self.responses, {path: files}), \
                    self.assertRaises(ValueError):
                UPDATES.merge_update(123)
            self.assert_no_merge()
        content = self.responses[f"{self.prefix}/contents/{self.package.path}?ref={self.head}"]
        changed = self.updated.replace('skip_clean "libexec"', 'skip_clean "bin"')
        with mock.patch.dict(content, {"content": base64.b64encode(changed.encode()).decode()}), \
                self.assertRaises(ValueError):
            UPDATES.merge_update(123)
        self.assert_no_merge()

    def test_rejects_stale_changed_or_unchanged_package_release(self):
        for package in (self.package, UPDATES.PACKAGES["sendbox"]):
            release, _ = mock_release(package, "10.0.0")
            with self.subTest(package=package.name), mock.patch.dict(
                self.responses, {f"repos/{package.repository}/releases/latest": release},
            ), self.assertRaises(ValueError):
                UPDATES.merge_update(123)
            self.assert_no_merge()

    def test_rejects_unchanged_package_hashes_that_disagree_with_latest_release_metadata(self):
        package = UPDATES.PACKAGES["sql-not-so-lite"]
        path = self.root / package.path
        original = path.read_text()
        release = self.responses[f"repos/{package.repository}/releases/latest"]
        digest = UPDATES.release_digests(package, release)[package.asset_names("1.2.3")[0]]
        path.write_text(original.replace(digest, "0" * 64, 1))
        with self.assertRaisesRegex(ValueError, "latest published artifact digests"):
            UPDATES.merge_update(123)
        self.assert_no_merge()

    def test_missing_failed_cancelled_or_pending_native_coverage_cannot_merge(self):
        data = self.responses[f"{self.prefix}/actions/runs/123/jobs?per_page=100"]
        for index in range(len(data["jobs"])):
            for conclusion in ("failure", "cancelled", "skipped", None):
                changed = copy.deepcopy(data)
                changed["jobs"][index]["conclusion"] = conclusion
                with self.subTest(index=index, conclusion=conclusion), mock.patch.dict(data, changed), \
                        self.assertRaises(ValueError):
                    UPDATES.merge_update(123)
                self.assert_no_merge()
        with mock.patch.dict(data, {"jobs": data["jobs"][:-1]}), self.assertRaises(ValueError):
            UPDATES.merge_update(123)
        self.assert_no_merge()

    def test_pending_or_failed_other_head_checks_cannot_merge(self):
        data = self.responses[f"{self.prefix}/commits/{self.head}/check-runs?per_page=100"]
        for state, conclusion in (("in_progress", None), ("completed", "failure")):
            check = {"name": "Mock additional check", "status": state, "conclusion": conclusion}
            with mock.patch.dict(data, {
                "total_count": 6, "check_runs": data["check_runs"] + [check],
            }), self.assertRaises(ValueError):
                UPDATES.merge_update(123)
            self.assert_no_merge()
        status = self.responses[f"{self.prefix}/commits/{self.head}/status"]
        with mock.patch.dict(status, {"total_count": 1, "state": "failure"}), \
                self.assertRaises(ValueError):
            UPDATES.merge_update(123)
        self.assert_no_merge()

    def test_unresolved_threads_changes_requested_and_incomplete_review_data_block_merge(self):
        changes = (
            {"reviewThreads": {"nodes": [{"isResolved": False}], "pageInfo": {"hasNextPage": False}}},
            {"reviews": {"nodes": [
                {"state": "CHANGES_REQUESTED", "author": {"login": "mock-reviewer"}},
            ], "pageInfo": {"hasNextPage": False}}},
            {"reviews": {"nodes": [
                {"state": "PENDING", "author": {"login": "mock-reviewer"}},
            ], "pageInfo": {"hasNextPage": False}}},
            {"reviews": {"nodes": [], "pageInfo": {"hasNextPage": True}}},
        )
        for change in changes:
            with self.subTest(change=change), mock.patch.dict(self.reviews, change), \
                    self.assertRaises(ValueError):
                UPDATES.merge_update(123)
            self.assert_no_merge()

    def test_download_verification_failure_or_final_head_race_prevents_merge(self):
        with mock.patch.object(UPDATES, "verify_release", side_effect=ValueError("Mock digest mismatch")), \
                self.assertRaisesRegex(ValueError, "digest"):
            UPDATES.merge_update(123)
        self.assert_no_merge()
        self.pull_reads = 0
        self.advance_head = True
        with self.assertRaises(ValueError):
            UPDATES.merge_update(123)
        self.assert_no_merge()

    def test_release_publication_or_replacement_during_byte_verification_blocks_merge(self):
        path = f"repos/{self.package.repository}/releases/latest"
        for version in ("10.0.0", "9.8.7"):
            replacement, _ = mock_release(self.package, version)
            if version == "9.8.7":
                replacement["assets"][0]["digest"] = f"sha256:{'0' * 64}"
            with self.subTest(version=version), mock.patch.dict(self.responses), \
                    mock.patch.object(
                        UPDATES, "verify_release",
                        side_effect=lambda *args: self.responses.update({path: replacement}),
                    ), self.assertRaisesRegex(ValueError, "release changed"):
                UPDATES.merge_update(123)
            self.assert_no_merge()

    def test_review_feedback_arriving_during_artifact_verification_blocks_merge(self):
        def review_arrives(*arguments):
            self.reviews["reviewThreads"]["nodes"] = [{"isResolved": False}]

        with mock.patch.object(UPDATES, "verify_release", side_effect=review_arrives), \
                self.assertRaisesRegex(ValueError, "Unresolved"):
            UPDATES.merge_update(123)
        self.assert_no_merge()

    def test_current_head_check_changes_during_artifact_verification_block_merge(self):
        def check_fails(*arguments):
            data = self.responses[f"{self.prefix}/commits/{self.head}/check-runs?per_page=100"]
            data["check_runs"][0]["conclusion"] = "failure"

        with mock.patch.object(UPDATES, "verify_release", side_effect=check_fails), \
                self.assertRaisesRegex(ValueError, "checks"):
            UPDATES.merge_update(123)
        self.assert_no_merge()

    def test_resolved_review_request_and_later_approval_can_merge(self):
        self.reviews["reviews"]["nodes"] = [
            {"state": state, "author": {"login": "mock-reviewer"}}
            for state in ("CHANGES_REQUESTED", "COMMENTED", "APPROVED")
        ]
        UPDATES.merge_update(123)
        self.assertTrue(any(call[:4] == ("gh", "api", "--method", "PUT") for call in self.commands))

    def test_github_merge_refusal_is_an_error_and_cannot_dispatch_post_merge_ci(self):
        def refused(*arguments, **kwargs):
            if arguments[:4] == ("gh", "api", "--method", "PUT"):
                return json.dumps({"merged": False, "message": "Mock merge restriction"})
            return self.run_command(*arguments, **kwargs)

        with mock.patch.object(UPDATES, "run", side_effect=refused), \
                self.assertRaisesRegex(ValueError, "Mock merge restriction"):
            UPDATES.merge_update(123)
        self.assertFalse(any(call[:3] == ("gh", "workflow", "run") for call in self.commands))


class RetirementTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mock-update-retirement-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.package = UPDATES.PACKAGES["killswitch"]
        self.original = mock_definition(self.package)
        self.release, _ = mock_release(self.package, "1.2.4")
        _, self.candidate = UPDATES.prepare_update(self.package, self.original, self.release)
        main_release, _ = mock_release(self.package, "1.2.5")
        path = self.root / self.package.path
        path.parent.mkdir()
        path.write_text(UPDATES.prepare_update(self.package, self.original, main_release)[1])
        self.head, self.base, self.main = "b" * 40, "c" * 40, "a" * 40
        self.prefix = f"repos/{UPDATES.REPOSITORY}"
        self.pull = {
            "number": 1, "state": "open",
            "user": {"login": "github-actions[bot]", "type": "Bot"},
            "head": {
                "sha": self.head, "ref": "automation/killswitch-v1.2.4",
                "repo": {"full_name": UPDATES.REPOSITORY},
            },
        }
        self.pages = [[self.pull]]
        self.responses = {
            f"{self.prefix}/pulls/1": copy.deepcopy(self.pull),
            f"{self.prefix}/pulls/1/files?per_page=100": [
                {"filename": self.package.path, "status": "modified"},
            ],
            f"{self.prefix}/contents/{self.package.path}?ref={self.head}": {
                "encoding": "base64", "content": base64.b64encode(self.candidate.encode()).decode(),
            },
            f"{self.prefix}/contents/{self.package.path}?ref={self.base}": {
                "encoding": "base64", "content": base64.b64encode(self.original.encode()).decode(),
            },
            f"{self.prefix}/compare/main...{self.head}": {"merge_base_commit": {"sha": self.base}},
            f"{self.prefix}/commits/main": {"sha": self.main},
            f"repos/{self.package.repository}/releases/tags/v1.2.4": self.release,
        }
        self.commands = []
        self.stdout = io.StringIO()
        for patcher in (
            mock.patch.object(UPDATES, "ROOT", self.root),
            mock.patch.object(UPDATES, "git", return_value=self.main),
            mock.patch.object(UPDATES.sendbox, "api", side_effect=self.responses.__getitem__),
            mock.patch.object(UPDATES, "run", side_effect=self.run_command),
            mock.patch.object(UPDATES, "check_reviews"),
            mock.patch("sys.stdout", self.stdout),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_command(self, *arguments, **kwargs):
        self.commands.append(arguments)
        if arguments[:4] == ("gh", "api", "--paginate", "--slurp"):
            return json.dumps(self.pages)
        if arguments[:3] == ("gh", "pr", "close"):
            return ""
        self.fail(f"Unexpected command: {arguments}")

    def assert_no_close(self):
        self.assertFalse(any(call[:3] == ("gh", "pr", "close") for call in self.commands))

    def test_closes_only_verified_superseded_bot_update_without_merging_or_deleting_branch(self):
        UPDATES.retire_updates()
        closes = [call for call in self.commands if call[:3] == ("gh", "pr", "close")]
        self.assertEqual(len(closes), 1)
        self.assertEqual(closes[0][3], "1")
        self.assertFalse(any("merge" in call or "--delete-branch" in call for call in self.commands))
        UPDATES.check_reviews.assert_called_once_with(1)

    def test_preserves_updates_not_yet_in_main(self):
        (self.root / self.package.path).write_text(self.original)
        UPDATES.retire_updates()
        self.assert_no_close()

    def test_preserves_foreign_nonbot_and_modified_update_prs(self):
        for change in (
            {"user": {"login": "mock-maintainer", "type": "User"}},
            {"head": self.pull["head"] | {"repo": {"full_name": "mock/unrelated"}}},
        ):
            with self.subTest(change=change), mock.patch.dict(self.pull, change):
                UPDATES.retire_updates()
            self.assert_no_close()
        content = self.responses[f"{self.prefix}/contents/{self.package.path}?ref={self.head}"]
        candidate = self.candidate.replace('skip_clean "libexec"', 'skip_clean "bin"')
        content["content"] = base64.b64encode(candidate.encode()).decode()
        UPDATES.retire_updates()
        self.assert_no_close()
        self.assertIn("::warning::Keeping PR #1", self.stdout.getvalue())

    def test_preserves_changed_head_or_main_and_unresolved_review_feedback(self):
        for path, change in (
            (f"{self.prefix}/pulls/1", {"head": self.pull["head"] | {"sha": "d" * 40}}),
            (f"{self.prefix}/commits/main", {"sha": "d" * 40}),
        ):
            with self.subTest(path=path), mock.patch.dict(self.responses[path], change):
                UPDATES.retire_updates()
            self.assert_no_close()
        with mock.patch.object(UPDATES, "check_reviews", side_effect=ValueError("Mock unresolved review")):
            UPDATES.retire_updates()
        self.assert_no_close()

    def test_reads_all_pages_and_recognizes_verified_batch_updates(self):
        unrelated = copy.deepcopy(self.pull)
        unrelated["head"]["ref"] = "feature/mock"
        self.pull["head"]["ref"] = UPDATES.update_branch([
            (self.package, self.release, self.candidate),
        ], self.base)
        self.responses[f"{self.prefix}/pulls/1"]["head"]["ref"] = self.pull["head"]["ref"]
        self.pages = [[unrelated], [self.pull]]
        UPDATES.retire_updates()
        self.assertEqual(sum(call[:3] == ("gh", "pr", "close") for call in self.commands), 1)

if __name__ == "__main__":
    unittest.main()
