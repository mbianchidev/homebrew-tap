require "fileutils"
require "open3"
require "formula"
require "cask/cask_loader"
require "cask/installer"

abort "Package lifecycle checks require a disposable GitHub-hosted runner." unless
  ENV["GITHUB_ACTIONS"] == "true" && ENV["RUNNER_ENVIRONMENT"] == "github-hosted"

def run!(*command)
  abort "Command failed: #{command.join(" ")}" unless system(*command)
end

def capture!(*command)
  output, status = Open3.capture2e(*command)
  abort "Command failed: #{command.join(" ")}\n#{output}" unless status.success?
  output.strip
end

def summary(message)
  puts message
  File.open(ENV.fetch("GITHUB_STEP_SUMMARY"), "a") { |file| file.puts message }
end

root = File.realpath(ENV.fetch("GITHUB_WORKSPACE"))
tap = "mbianchidev/tap"
tap_root = capture!("brew", "--repository", tap)
abort "Homebrew is not using the checked-out tap." unless File.realpath(tap_root) == root
abort "Homebrew is not testing the event revision." unless
  capture!("git", "-C", tap_root, "rev-parse", "HEAD") == ENV.fetch("GITHUB_SHA")

packages = Dir.glob("#{root}/{Formula,Casks}/**/*.rb").sort
summary("No formulas or casks to install.") if packages.empty?

packages.each do |path|
  token = File.basename(path, ".rb")
  qualified = "#{tap}/#{token}"

  if path.start_with?("#{root}/Formula/")
    formula = Formulary.factory(qualified)
    platform_requirements = formula.requirements.select do |requirement|
      %w[ArchRequirement LinuxRequirement MacOSRequirement MaximumMacOSRequirement].include?(requirement.class.name)
    end
    unsupported = platform_requirements.reject(&:satisfied?)
    unless unsupported.empty?
      summary("Skipped #{qualified}: #{unsupported.map(&:message).join(" ")}")
      next
    end

    if token == "sendbox"
      run!("python3", "#{root}/scripts/ci/sendbox.py", "lifecycle", path)
    else
      run!("brew", "install", "--formula", qualified)
      run!("brew", "test", qualified)
      run!("brew", "uninstall", "--formula", qualified)
      summary("Passed #{qualified}: install, formula test, uninstall.")
    end
  elsif OS.mac?
    cask = Cask::CaskLoader.load(qualified)
    begin
      Cask::Installer.new(cask).check_requirements
    rescue Cask::CaskError => e
      summary("Skipped #{qualified}: #{e.message}")
      next
    end

    sentinel = File.join(ENV.fetch("HOME"), "Library", "Application Support", token, "tap-ci-retained.txt")
    abort "Refusing to overwrite existing cask fixture #{sentinel}." if File.exist?(sentinel)
    FileUtils.mkdir_p(File.dirname(sentinel))
    File.write(sentinel, "mock application data\n")
    run!("brew", "install", "--cask", qualified)
    abort "Cask was not installed: #{qualified}" if capture!("brew", "list", "--cask", "--versions", qualified).empty?
    run!("brew", "uninstall", "--cask", qualified)
    abort "Uninstall removed cask user data: #{qualified}" unless File.read(sentinel) == "mock application data\n"
    FileUtils.rm_f(sentinel)
    summary("Passed #{qualified}: cask install, artifact listing, uninstall, data preservation; no app launched.")
  else
    summary("Skipped #{qualified}: cask installation is checked on macOS.")
  end
end
