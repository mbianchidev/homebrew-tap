require "fileutils"
require "digest"
require "json"
require "open3"
require "socket"
require "tmpdir"
require "timeout"

hosted_runner = ENV["TAP_CI_RUNNER_ENVIRONMENT"]
abort "Package lifecycle checks require a GitHub-hosted runner; received #{hosted_runner.inspect}." unless
  ENV["GITHUB_ACTIONS"] == "true" && hosted_runner == "github-hosted"

def run!(*command)
  abort "Command failed: #{command.join(" ")}" unless system(*command)
end

def capture!(*command)
  output, errors, status = Open3.capture3(*command)
  warn errors unless errors.empty?
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

def exercise_sql!(qualified)
  binary = File.join(capture!("brew", "--prefix"), "bin", "sqnsl")
  version = JSON.parse(capture!("brew", "info", "--json=v2", "--formula", qualified))
                .fetch("formulae").first.fetch("versions").fetch("stable")

  Dir.mktmpdir("sql-not-so-lite-lifecycle-", ENV.fetch("RUNNER_TEMP")) do |directory|
    home = File.join(directory, "home")
    state = File.join(home, ".sql-not-so-lite")
    fixtures = File.join(directory, "mock-project")
    FileUtils.mkdir_p([state, fixtures])
    port = TCPServer.open("127.0.0.1", 0) { |server| server.addr[1] }
    File.write(File.join(state, "config.toml"), <<~TOML)
      [server]
      grpc_port = 0
      http_port = #{port}
      data_dir = "#{state}/databases"
      [logging]
      file = "#{state}/sqnsl.log"
      [scanner]
      scan_root = "#{fixtures}"
      scan_interval = "24h"
      [replicator]
      enabled = false
    TOML
    environment = {
      "HOME" => home,
      "SQNSL_SCAN_ROOT" => fixtures,
      "SQNSL_DATA_DIR" => File.join(state, "databases"),
      "GH_TOKEN" => nil,
      "GITHUB_TOKEN" => nil,
      "HOMEBREW_GITHUB_API_TOKEN" => nil,
    }
    log = File.join(directory, "daemon.log")
    pid = Process.spawn(environment, binary, "start", out: log, err: [:child, :out])
    url = "http://127.0.0.1:#{port}"
    curl = ["curl", "--fail", "--silent", "--show-error", "--max-time", "5"]
    begin
      health = JSON.parse(capture!(*curl, "--retry", "10", "--retry-connrefused", "--retry-delay", "1",
                                  "#{url}/api/health"))
      abort "SQL health/version mismatch: #{health.inspect}" unless
        health["status"] == "ok" && health["version"] == version
      html = capture!(*curl, "#{url}/")
      asset = html[/src=["']([^"']+\.js)["']/, 1]
      abort "The installed SQL binary has no bundled frontend JavaScript." unless asset
      headers = capture!(*curl, "--head", "#{url}#{asset}")
      abort "Bundled SQL JavaScript was not served as JavaScript." unless headers.downcase.include?("javascript")
      abort "Bundled SQL JavaScript is empty." if capture!(*curl, "#{url}#{asset}").empty?
      capture!(*curl, "--header", "Content-Type: application/json", "--data",
               JSON.generate(name: "packaging"), "#{url}/api/databases")
      [
        "CREATE TABLE packaging_fixture (id INTEGER PRIMARY KEY, value TEXT NOT NULL)",
        "INSERT INTO packaging_fixture VALUES (1, 'mock retained data')",
      ].each do |sql|
        capture!(*curl, "--header", "Content-Type: application/json", "--data",
                 JSON.generate(sql: sql), "#{url}/api/databases/packaging/query")
      end
    ensure
      if pid && !Process.waitpid(pid, Process::WNOHANG)
        Process.kill("TERM", pid)
        begin
          Timeout.timeout(15) { Process.wait(pid) }
        rescue Timeout::Error
          Process.kill("KILL", pid)
          Process.wait(pid)
          abort "SQL daemon did not stop gracefully:\n#{File.read(log)}"
        end
      end
      puts File.read(log)
    end
    database = File.join(state, "databases", "packaging.sqlite")
    abort "SQL smoke test did not create a real SQLite database." unless
      File.binread(database, 16) == "SQLite format 3\0"
    retained = Dir.glob("#{home}/**/*", File::FNM_DOTMATCH).select { |file| File.file?(file) }
                  .to_h { |file| [file, Digest::SHA256.file(file).hexdigest] }
    run!("brew", "uninstall", "--formula", qualified)
    abort "The SQL executable is still linked after uninstall." if File.exist?(binary) || File.symlink?(binary)
    abort "SQL uninstall changed retained user configuration or databases." unless
      retained.all? { |file, digest| File.file?(file) && Digest::SHA256.file(file).hexdigest == digest }
    summary("Passed #{qualified}: published binary/embedded-GUI install, version/config test, HTTP startup/assets, " \
            "mock SQLite data creation, graceful shutdown, uninstall and data preservation; no browser launched.")
  end
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
      if token == "sql-not-so-lite"
        exercise_sql!(qualified)
      else
        run!("brew", "uninstall", "--formula", qualified)
        summary("Passed #{qualified}: install, formula test, uninstall.")
      end
    end
  elsif RUBY_PLATFORM.include?("darwin")
    next unless compatible?(:cask, qualified)

    if token == "killswitch"
      # An unrelated core VPN formula shares this explicitly qualified cask's token.
      run!("brew", "audit", "--cask", "--strict", "--online", "--except=token_conflicts", qualified)
      run!("ruby", "#{root}/scripts/ci/killswitch.rb", path)
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
