# frozen_string_literal: true

require "digest"
require "fileutils"
require "json"
require "open3"
require "pathname"
require "tmpdir"

module KillSwitchCask
  def self.capture!(*command)
    puts "+ #{command.join(" ")}"
    output, errors, status = Open3.capture3(*command.map(&:to_s))
    warn errors unless errors.empty?
    raise "Command failed: #{command.join(" ")}\n#{output}" unless status.success?

    output.strip
  end

  def self.version_from(text)
    versions = text.scan(/^  version "([^"]+)"$/).flatten
    raise "Expected one stable KillSwitch cask version." unless
      versions.length == 1 && versions.first.match?(/\A(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\z/)

    versions.first
  end

  def self.release_url(version)
    "https://github.com/mbianchidev/kill-switch/releases/download/v#{version}"
  end

  def self.release_digest(release, version)
    raise "Expected a published stable KillSwitch v#{version} release." if
      release["tag_name"] != "v#{version}" || release["draft"] != false || release["prerelease"] != false

    assets = %w[KillSwitch.dmg KillSwitch.dmg.sha256].map do |name|
      matches = release.fetch("assets").select { |asset| asset["name"] == name }
      raise "Expected one published #{name} asset with a versioned URL." if
        matches.length != 1 || matches.first["browser_download_url"] != "#{release_url(version)}/#{name}"

      matches.first
    end
    digest = assets.first["digest"]
    raise "Missing GitHub SHA-256 digest for KillSwitch.dmg." unless
      digest.is_a?(String) && digest.match?(/\Asha256:[0-9a-f]{64}\z/)

    digest.delete_prefix("sha256:")
  end

  def self.verify_download!(dmg, checksum, expected)
    published = checksum.match(/\A([0-9a-f]{64})(?:[ \t]+\*?KillSwitch\.dmg)?\r?\n?\z/)
    raise "Downloaded DMG, published checksum and GitHub digest must agree." unless
      published && published[1] == expected && Digest::SHA256.file(dmg).hexdigest == expected
  end

  def self.within!(path, root)
    path = Pathname(path).expand_path
    ancestor = path
    ancestor = ancestor.parent until ancestor.exist? || ancestor.symlink?
    resolved = ancestor.realpath.join(path.relative_path_from(ancestor)).cleanpath
    raise "Refusing path outside disposable root: #{path}" unless
      resolved.to_s.start_with?("#{root.realpath}/")

    resolved
  end

  def self.snapshot(root)
    root.glob("**/*", File::FNM_DOTMATCH).select(&:file?)
        .to_h { |path| [path, Digest::SHA256.file(path).hexdigest] }
  end

  def self.install_isolated!(file, root, expected)
    require "cask/installer"

    root = Pathname(root).realpath
    appdir = root/"Custom Applications"
    binarydir = root/"bin"
    caskroom = root/"Caskroom"
    [appdir, binarydir, caskroom].each { |path| within!(path, root).mkpath }

    # These process-local test overrides also cover metadata reload during uninstall.
    Cask::Caskroom.define_singleton_method(:path) { caskroom }
    Cask::Config.prepend(Module.new { define_method(:binarydir) { binarydir } })
    config = Cask::Config.new(env: {}, explicit: { appdir: appdir })
    cask = Cask::CaskLoader.load(file, config: config)
    raise "The cask does not match the verified versioned DMG." if
      cask.token != "killswitch" || cask.sha256.to_s != expected ||
      cask.url.to_s != "#{release_url(cask.version)}/KillSwitch.dmg"

    app = appdir/"KillSwitch.app"
    executable = app/"Contents/MacOS/KillSwitch"
    binary = binarydir/"killswitchctl"
    expected_artifacts = {
      Cask::Artifact::App    => [cask.staged_path/"KillSwitch.app", app],
      Cask::Artifact::Binary => [executable, binary],
    }
    raise "Only the app and killswitchctl binary artifacts may be installed." unless
      cask.artifacts.length == expected_artifacts.length &&
      cask.artifacts.all? do |artifact|
        expected_artifacts.key?(artifact.class) &&
          expected_artifacts[artifact.class] == [artifact.source, artifact.target]
      end

    cask.artifacts.each { |artifact| [artifact.source, artifact.target].each { |path| within!(path, root) } }
    home = root/"home"
    [
      "Library/Application Support/KillSwitch/mock-state.json",
      "Library/Preferences/io.killswitch.app.plist",
      "Library/LaunchAgents/io.killswitch.app.plist",
    ].each do |relative|
      path = home/relative
      raise "Refusing to overwrite existing lifecycle fixture: #{path}" if path.exist? || path.symlink?

      path.dirname.mkpath
      path.write("mock retained application data\n")
    end
    retained = snapshot(home)
    installer = Cask::Installer.new(cask, require_sha: true)
    installed = false
    begin
      installer.install
      installed = true
      raise "The killswitchctl link does not follow the custom appdir." unless
        binary.symlink? && binary.realpath == executable.realpath
      raise "The released executable is not universal." if
        capture!("lipo", "-archs", executable).split.sort != %w[arm64 x86_64]
      raise "The installed app version does not match the cask." if
        capture!("/usr/libexec/PlistBuddy", "-c", "Print :CFBundleShortVersionString",
                 app/"Contents/Info.plist") != cask.version.to_s

      capture!("codesign", "--verify", "--deep", "--strict", app)
      [app, executable].each do |path|
        raise "Homebrew did not preserve quarantine on #{path}." if
          capture!("xattr", "-p", "com.apple.quarantine", path).empty?
      end
    ensure
      installer.uninstall if installed
    end
    raise "Cask uninstall left an app, binary link or installed receipt." if
      app.exist? || app.symlink? || binary.exist? || binary.symlink? || installer.cask.installed?
    raise "Cask installation or removal changed mock application data." unless
      retained.all? { |path, digest| path.file? && Digest::SHA256.file(path).hexdigest == digest }
  end

  def self.lifecycle!(file)
    raise "KillSwitch cask lifecycle validation requires macOS." unless RUBY_PLATFORM.include?("darwin")

    file = Pathname(file).realpath
    version = version_from(file.read)
    release = JSON.parse(capture!("gh", "api", "repos/mbianchidev/kill-switch/releases/tags/v#{version}"))
    expected = release_digest(release, version)
    Dir.mktmpdir("killswitch-cask-") do |directory|
      root = Pathname(directory)
      downloads = root/"downloads"
      downloads.mkpath
      capture!("gh", "release", "download", "v#{version}", "--repo", "mbianchidev/kill-switch",
               "--pattern", "KillSwitch.dmg", "--pattern", "KillSwitch.dmg.sha256", "--dir", downloads)
      verify_download!(downloads/"KillSwitch.dmg", (downloads/"KillSwitch.dmg.sha256").read, expected)
      environment = {
        "HOME"                        => (root/"home").to_s,
        "HOMEBREW_CACHE"              => (root/"cache").to_s,
        "HOMEBREW_LOGS"               => (root/"logs").to_s,
        "HOMEBREW_TEMP"               => (root/"tmp").to_s,
        "HOMEBREW_CASK_OPTS"          => "",
        "HOMEBREW_DEVELOPER"          => "1",
        "HOMEBREW_NO_AUTO_UPDATE"     => "1",
        "HOMEBREW_NO_ANALYTICS"       => "1",
        "HOMEBREW_NO_AUTOREMOVE"      => "1",
        "HOMEBREW_NO_INSTALL_CLEANUP" => "1",
        "GH_TOKEN"                    => nil,
        "GITHUB_TOKEN"                => nil,
        "HOMEBREW_GITHUB_API_TOKEN"   => nil,
      }
      %w[home cache logs tmp].each { |path| (root/path).mkpath }
      raise "Isolated Homebrew cask installation failed." unless
        system(environment, "brew", "ruby", "--", __FILE__, "--install", file.to_s, root.to_s, expected)
    end
    message = "Passed killswitch: published DMG/checksums, universal app, custom appdir/CLI link, " \
              "code signature, quarantine, uninstall and mock data preservation; no app or CLI launched."
    puts message
    File.open(ENV["GITHUB_STEP_SUMMARY"], "a") { |summary| summary.puts message } if ENV["GITHUB_STEP_SUMMARY"]
  end
end

if $PROGRAM_NAME == __FILE__
  begin
    if ARGV.length == 4 && ARGV.first == "--install"
      KillSwitchCask.install_isolated!(*ARGV.drop(1))
    elsif ARGV.length == 1
      KillSwitchCask.lifecycle!(ARGV.first)
    else
      raise "Usage: ruby scripts/ci/killswitch.rb Casks/killswitch.rb"
    end
  rescue RuntimeError, SystemCallError, JSON::ParserError => e
    warn "::error::#{e.message}"
    exit 1
  end
end
