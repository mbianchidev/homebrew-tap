# frozen_string_literal: true

require "minitest/autorun"
require "tmpdir"
require_relative "../scripts/ci/killswitch"

class KillSwitchCaskTest < Minitest::Test
  def setup
    @version = "1.2.3"
    @digest = Digest::SHA256.hexdigest("mock DMG bytes")
    @release = {
      "tag_name"   => "v#{@version}",
      "draft"      => false,
      "prerelease" => false,
      "assets"     => %w[KillSwitch.dmg KillSwitch.dmg.sha256].map do |name|
        {
          "name"                 => name,
          "browser_download_url" => "#{KillSwitchCask.release_url(@version)}/#{name}",
          "digest"               => "sha256:#{@digest}",
        }
      end,
    }
  end

  def test_accepts_only_one_stable_cask_version
    assert_equal @version, KillSwitchCask.version_from("  version \"#{@version}\"\n")
    ["1.2.3-rc.1", "01.2.3", "v1.2.3", "1.2", "1.2.3+build"].each do |version|
      assert_raises(RuntimeError) { KillSwitchCask.version_from("  version \"#{version}\"\n") }
    end
    assert_raises(RuntimeError) { KillSwitchCask.version_from("") }
    assert_raises(RuntimeError) do
      KillSwitchCask.version_from("  version \"1.2.3\"\n  version \"2.0.0\"\n")
    end
  end

  def test_verifies_published_stable_release_identity
    assert_equal @digest, KillSwitchCask.release_digest(@release, @version)
    ["draft", "prerelease"].each do |field|
      assert_raises(RuntimeError) do
        KillSwitchCask.release_digest(@release.merge(field => true), @version)
      end
    end
    assert_raises(RuntimeError) { KillSwitchCask.release_digest(@release, "2.0.0") }
  end

  def test_rejects_missing_or_duplicate_assets
    [[], @release["assets"].drop(1), @release["assets"] + [@release["assets"].first]].each do |assets|
      assert_raises(RuntimeError) do
        KillSwitchCask.release_digest(@release.merge("assets" => assets), @version)
      end
    end
  end

  def test_rejects_unpinned_urls_and_invalid_github_digests
    [nil, "", "a" * 64, "sha256:not-a-checksum"].each do |digest|
      release = Marshal.load(Marshal.dump(@release))
      release["assets"].first["digest"] = digest
      assert_raises(RuntimeError) { KillSwitchCask.release_digest(release, @version) }
    end
    release = Marshal.load(Marshal.dump(@release))
    release["assets"].first["browser_download_url"] =
      "https://github.com/mbianchidev/kill-switch/releases/latest/download/KillSwitch.dmg"
    assert_raises(RuntimeError) { KillSwitchCask.release_digest(release, @version) }
  end

  def test_checks_actual_dmg_bytes_against_github_and_adjacent_checksum
    Dir.mktmpdir do |directory|
      dmg = Pathname(directory)/"KillSwitch.dmg"
      dmg.write("mock DMG bytes")
      ["#{@digest}\n", "#{@digest}  KillSwitch.dmg\n", "#{@digest} *KillSwitch.dmg\n"].each do |checksum|
        KillSwitchCask.verify_download!(dmg, checksum, @digest)
      end
      ["#{"0" * 64}\n", "#{@digest}  another.dmg\n", "#{@digest}\n#{@digest}\n", ""].each do |checksum|
        assert_raises(RuntimeError) { KillSwitchCask.verify_download!(dmg, checksum, @digest) }
      end
      dmg.write("modified mock DMG bytes")
      assert_raises(RuntimeError) { KillSwitchCask.verify_download!(dmg, "#{@digest}\n", @digest) }
    end
  end

  def test_disposable_paths_cannot_escape_through_parent_paths_or_symlinks
    Dir.mktmpdir do |directory|
      root = Pathname(directory).realpath
      assert_equal root/"Custom Applications/KillSwitch.app",
                   KillSwitchCask.within!(root/"Custom Applications/KillSwitch.app", root)
      [root, root.parent/"outside", root/"../outside"].each do |path|
        assert_raises(RuntimeError) { KillSwitchCask.within!(path, root) }
      end
      File.symlink(root.parent, root/"escaped")
      assert_raises(RuntimeError) { KillSwitchCask.within!(root/"escaped/KillSwitch.app", root) }
      File.symlink(root/"missing", root/"dangling")
      assert_raises(Errno::ENOENT) { KillSwitchCask.within!(root/"dangling/file", root) }
    end
  end

  def test_snapshot_detects_modified_and_removed_mock_preferences
    Dir.mktmpdir do |directory|
      root = Pathname(directory)
      fixture = root/"mock-preferences.plist"
      fixture.write("mock preferences\n")
      before = KillSwitchCask.snapshot(root)
      fixture.write("changed mock preferences\n")
      refute_equal before, KillSwitchCask.snapshot(root)
      fixture.unlink
      refute_equal before, KillSwitchCask.snapshot(root)
    end
  end
end
