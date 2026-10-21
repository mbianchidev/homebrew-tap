require "fileutils"
require "open3"

hosted_runner = ENV["TAP_CI_RUNNER_ENVIRONMENT"]
abort "Package lifecycle checks require a GitHub-hosted runner; received #{hosted_runner.inspect}." unless
  ENV["GITHUB_ACTIONS"] == "true" && hosted_runner == "github-hosted"

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

def compatible?(kind, qualified)
  # Homebrew intentionally filters Actions context; only metadata evaluation belongs in its Ruby process.
  check = if kind == :formula
    <<~RUBY
      formula = Formulary.factory(ARGV.fetch(0))
      requirements = formula.requirements.select do |requirement|
        %w[ArchRequirement LinuxRequirement MacOSRequirement MaximumMacOSRequirement].include?(requirement.class.name)
      end
      unsupported = requirements.reject(&:satisfied?)
      unless unsupported.empty?
        warn unsupported.map(&:message).join(" ")
        exit 3
      end
    RUBY
  else
    <<~RUBY
      require "cask/installer"
      cask = Cask::CaskLoader.load(ARGV.fetch(0))
      begin
        Cask::Installer.new(cask).check_requirements
      rescue Cask::CaskError => error
        warn error.message
        exit 3
      end
    RUBY
  end
  output, status = Open3.capture2e("brew", "ruby", "-e", check, qualified)
  puts output unless output.empty?
  return true if status.success?
  abort "Could not evaluate #{qualified} requirements:\n#{output}" unless status.exitstatus == 3

  summary("Skipped #{qualified}: #{output.strip}")
  false
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
    next unless compatible?(:formula, qualified)

    if token == "sendbox"
      run!("python3", "#{root}/scripts/ci/sendbox.py", "lifecycle", path)
    else
      run!("brew", "install", "--formula", qualified)
      run!("brew", "test", qualified)
      run!("brew", "uninstall", "--formula", qualified)
      summary("Passed #{qualified}: install, formula test, uninstall.")
    end
  elsif RUBY_PLATFORM.include?("darwin")
    next unless compatible?(:cask, qualified)

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
