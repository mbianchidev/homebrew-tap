class SqlNotSoLite < Formula
  desc "Lightweight SQLite-as-a-service daemon with an embedded web GUI"
  homepage "https://github.com/mbianchidev/sql-not-so-lite"
  version "0.1.1"
  license "MIT"

  on_macos do
    on_arm do
      url "https://github.com/mbianchidev/sql-not-so-lite/releases/download/v0.1.1/sql-not-so-lite_0.1.1_darwin_arm64.tar.gz"
      sha256 "6f5da6762dbe187cd6709887c0857130c9747126fa803df24b94cf9e5ce663de"
    end
    on_intel do
      url "https://github.com/mbianchidev/sql-not-so-lite/releases/download/v0.1.1/sql-not-so-lite_0.1.1_darwin_amd64.tar.gz"
      sha256 "1f517c4a1a0a407b609f1ed946e3d4ebdc8841f6eca57efab5c0f8aeb5d158d9"
    end
  end

  on_linux do
    on_arm do
      url "https://github.com/mbianchidev/sql-not-so-lite/releases/download/v0.1.1/sql-not-so-lite_0.1.1_linux_arm64.tar.gz"
      sha256 "b1811d840b879ab8f8378a311bb74ce5eaf99489ed0453f2176d7f783dd9acac"
    end
    on_intel do
      url "https://github.com/mbianchidev/sql-not-so-lite/releases/download/v0.1.1/sql-not-so-lite_0.1.1_linux_amd64.tar.gz"
      sha256 "fea94db777759174abc67ab8036042f3dc9294da40949f9a40874a1a1eef66db"
    end
  end

  def install
    bin.install "sqnsl"
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
  end
end
