import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("sendbox_ci", ROOT / "scripts/ci/sendbox.py")
CI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CI)


@unittest.skipUnless((ROOT / "Formula/sendbox.rb").is_file(), "No Sendbox formula is present.")
class FormulaUpdateTests(unittest.TestCase):
    def setUp(self):
        self.formula = (ROOT / "Formula/sendbox.rb").read_text()
        self.version, self.digests = CI.formula_fields(self.formula)
        self.next_version = f"{int(self.version.split('.')[0]) + 1}.0.0"
        self.updated = CI.with_release(
            self.formula, self.next_version, dict.fromkeys(CI.PLATFORMS, "a" * 64)
        )
        self.branch = f"automation/sendbox-v{self.next_version}"

    def test_update_preserves_every_other_formula_byte(self):
        restored = CI.with_release(self.updated, self.version, self.digests)
        self.assertEqual(restored, self.formula)
        self.assertEqual(
            CI.validate_update(self.formula, self.updated, self.branch, ["Formula/sendbox.rb"]),
            self.next_version,
        )

    def test_rejects_prereleases_and_noncanonical_versions(self):
        for version in ("1.2.3-rc.1", "01.2.3", "1.2", "v1.2.3", "1.2.3+build"):
            with self.subTest(version=version), self.assertRaises(ValueError):
                CI.stable_version(version)

    def test_rejects_unrelated_branch_and_paths(self):
        for branch, paths in (
            ("feature/sendbox-v1.2.3", ["Formula/sendbox.rb"]),
            (self.branch, ["Formula/sendbox.rb", "Formula/another-package.rb"]),
            (self.branch + "-rc.1", ["Formula/sendbox.rb"]),
        ):
            with self.subTest(branch=branch, paths=paths), self.assertRaises(ValueError):
                CI.validate_update(self.formula, self.updated, branch, paths)

    def test_rejects_logic_changes_and_mismatched_version(self):
        for text in (
            self.updated.replace('skip_clean "libexec"', 'skip_clean "bin"'),
            self.updated.replace(f'version "{self.next_version}"', 'version "999.0.0"'),
        ):
            with self.subTest(text=text), self.assertRaises(ValueError):
                CI.validate_update(self.formula, text, self.branch, ["Formula/sendbox.rb"])

    def test_rejects_duplicate_or_missing_update_fields(self):
        for text in (
            self.formula + f'\n  version "{self.version}"\n',
            self.formula.replace('sha256 "', 'checksum "', 1),
        ):
            with self.subTest(text=text), self.assertRaises(ValueError):
                CI.formula_fields(text)

    def test_rejects_downgrade_and_unchanged_version(self):
        for version in ("0.0.0", self.version):
            updated = CI.with_release(self.formula, version, self.digests)
            with self.subTest(version=version), self.assertRaises(ValueError):
                CI.validate_update(
                    self.formula, updated, f"automation/sendbox-v{version}", ["Formula/sendbox.rb"]
                )

    def test_snapshot_detects_modified_and_removed_mock_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "mock-data.txt"
            fixture.write_text("mock data\n")
            before = CI.snapshot(root)
            fixture.write_text("changed mock data\n")
            self.assertNotEqual(before, CI.snapshot(root))
            fixture.unlink()
            self.assertNotEqual(before, CI.snapshot(root))

    def test_signed_guest_payload_must_remain_byte_identical(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "mock-release.tar.gz"
            relative = Path("guest/aarch64/bundle/manifest.sig")
            contents = b"mock signature bytes"
            with tarfile.open(archive, "w:gz") as payload:
                member = tarfile.TarInfo(f"sendbox-mock/{relative}")
                member.size = len(contents)
                payload.addfile(member, io.BytesIO(contents))
            installed = root / "libexec" / relative
            installed.parent.mkdir(parents=True)
            installed.write_bytes(contents)
            CI.verify_guest_bytes(archive, root / "libexec")
            installed.write_bytes(b"altered mock signature")
            with self.assertRaisesRegex(ValueError, "altered signed guest bytes"):
                CI.verify_guest_bytes(archive, root / "libexec")
            installed.unlink()
            with self.assertRaisesRegex(ValueError, "Missing or replaced"):
                CI.verify_guest_bytes(archive, root / "libexec")

    def test_guest_archive_cannot_escape_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "mock-release.tar.gz"
            with tarfile.open(archive, "w:gz") as payload:
                member = tarfile.TarInfo("sendbox-mock/guest/../../escape")
                member.size = 4
                payload.addfile(member, io.BytesIO(b"mock"))
            with self.assertRaisesRegex(ValueError, "Unsafe release archive path"):
                CI.verify_guest_bytes(archive, root / "libexec")


if __name__ == "__main__":
    unittest.main()
