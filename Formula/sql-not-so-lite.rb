class SqlNotSoLite < Formula
  desc "SQLite daemon with a gRPC API and embedded web GUI"
  homepage "https://github.com/mbianchidev/sql-not-so-lite"
  url "https://github.com/mbianchidev/sql-not-so-lite/archive/refs/tags/v0.0.2.tar.gz"
  sha256 "2ab5f4d5e6c03cb398bacee019c10c33670bab55793a6425ec191e28b000dcba"
  license "MIT"

  on_macos do
    on_arm do
      depends_on "go" => :build
      depends_on "node@24" => :build
    end

    on_intel do
      # Current Homebrew Go/Node bottles do not cover Intel Macs.
      resource "go-build" do
        url "https://go.dev/dl/go1.27.3.darwin-amd64.tar.gz"
        sha256 "b6f8e931e4ab497fcde6da8ae4499a58f9d258e55c8a80824a516eae5950a750"
      end

      resource "node-build" do
        url "https://nodejs.org/dist/v24.22.1/node-v24.22.1-darwin-x64.tar.xz"
        sha256 "65e450f90a6eaacd5000f611861c4ce65fadc87f813795dc4ed0c0e5f2fca2d4"
      end
    end
  end

  on_linux do
    depends_on "go" => :build
    depends_on "node@24" => :build
  end

  def install
    if OS.mac? && Hardware::CPU.intel?
      resource("go-build").stage(buildpath/"build-go")
      resource("node-build").stage(buildpath/"build-node")
      ENV["GOROOT"] = (buildpath/"build-go").to_s
      ENV.prepend_path "PATH", buildpath/"build-go/bin"
      ENV.prepend_path "PATH", buildpath/"build-node/bin"
    end

    ENV["CGO_ENABLED"] = "0"
    ENV["GOTOOLCHAIN"] = "local"
    ENV["GOMAXPROCS"] = ENV.make_jobs.to_s
    ENV["GOMODCACHE"] = (HOMEBREW_CACHE/"sql-not-so-lite-go-mod").to_s
    ENV["npm_config_cache"] = (HOMEBREW_CACHE/"sql-not-so-lite-npm").to_s

    cd "web" do
      system "npm", "ci", "--no-fund"
      system "npm", "audit", "--audit-level=low"
      system "npm", "run", "build"
    end
    odie "The frontend build did not produce embedded assets" if
      (buildpath/"internal/server/static/assets").glob("*.js").empty?

    # The published tag still contains the unrelated development version 0.1.0.
    inreplace "internal/server/grpc.go", /^const Version = "[^"]+"$/, "const Version = \"#{version}\""
    system "go", "build", "-p", ENV.make_jobs.to_s,
           *std_go_args(output: bin/"sqnsl", ldflags: "-s -w"), "./cmd/sqnsl"
  end

  def caveats
    <<~EOS
      Configuration and databases stay in ~/.sql-not-so-lite.
      The daemon scans your home directory by default; set SQNSL_SCAN_ROOT to
      an explicit directory before starting if you want a narrower scan.
      Run as your normal user. Do not also use `sqnsl install` with brew services.
      No daemon, service, or browser is started during installation.
    EOS
  end

  service do
    run [opt_bin/"sqnsl", "start"]
    keep_alive true
    log_path var/"log/sql-not-so-lite.log"
    error_log_path var/"log/sql-not-so-lite.error.log"
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/sqnsl version")
    assert_match "Start the daemon", shell_output("#{bin}/sqnsl --help")
    system bin/"sqnsl", "config", "init"
    assert_path_exists testpath/".sql-not-so-lite/config.toml"
    assert_match "[server]", shell_output("#{bin}/sqnsl config")
  end
end
