class SqlNotSoLite < Formula
  desc "Lightweight SQLite-as-a-service daemon with an embedded web GUI"
  homepage "https://github.com/mbianchidev/sql-not-so-lite"
  version "0.0.3"
  license "MIT"

  on_macos do
    on_arm do
      url "https://github.com/mbianchidev/sql-not-so-lite/releases/download/v0.0.3/sql-not-so-lite_0.0.3_darwin_arm64.tar.gz"
      sha256 "609e000c7351808310a8559d4ea37262dafcec96bf3214ae04b9c0d0e4bb75fa"
    end

    on_intel do
      url "https://github.com/mbianchidev/sql-not-so-lite/releases/download/v0.0.3/sql-not-so-lite_0.0.3_darwin_amd64.tar.gz"
      sha256 "b98f34786b7b38879a0bf123da59cbd4e846c323ae1436e009d0f09553ed1d1e"
    end
  end

  on_linux do
    on_arm do
      url "https://github.com/mbianchidev/sql-not-so-lite/releases/download/v0.0.3/sql-not-so-lite_0.0.3_linux_arm64.tar.gz"
      sha256 "14bd5d15045a8a72a55845298a53656d671fc86461a78f1fed991ecf274f0780"
    end

    on_intel do
      url "https://github.com/mbianchidev/sql-not-so-lite/releases/download/v0.0.3/sql-not-so-lite_0.0.3_linux_amd64.tar.gz"
      sha256 "5d03353372f9d77f5b30f5d99ee0bf129fd3d2ef844609ca34715f47022e37bd"
    end
  end

  def install
    bin.install "sqnsl"
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
    working_dir Dir.home
    log_path var/"log/sqnsl.log"
    error_log_path var/"log/sqnsl.log"
  end

  test do
    assert_match "sql-not-so-lite #{version}", shell_output("#{bin}/sqnsl version")
    assert_match "Start the daemon", shell_output("#{bin}/sqnsl --help")
    system bin/"sqnsl", "config", "init"
    assert_path_exists testpath/".sql-not-so-lite/config.toml"
    assert_match "[server]", shell_output("#{bin}/sqnsl config")
  end
end
