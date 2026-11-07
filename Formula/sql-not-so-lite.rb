class SqlNotSoLite < Formula
  desc "Lightweight SQLite-as-a-service daemon with an embedded web GUI"
  homepage "https://github.com/mbianchidev/sql-not-so-lite"
  version "0.1.0"
  license "MIT"

  on_macos do
    on_arm do
      url "https://github.com/mbianchidev/sql-not-so-lite/releases/download/v0.1.0/sql-not-so-lite_0.1.0_darwin_arm64.tar.gz"
      sha256 "db3f41a3407e11c7908fa138459b0ee1a742236bc3f6d10a167fa7cfac2f9cf6"
    end
    on_intel do
      url "https://github.com/mbianchidev/sql-not-so-lite/releases/download/v0.1.0/sql-not-so-lite_0.1.0_darwin_amd64.tar.gz"
      sha256 "90b438a4fe78b0a58365aeacb6cca9cf5b4f693811c0110ef48353557af8f284"
    end
  end

  on_linux do
    on_arm do
      url "https://github.com/mbianchidev/sql-not-so-lite/releases/download/v0.1.0/sql-not-so-lite_0.1.0_linux_arm64.tar.gz"
      sha256 "b6d251a4d79035780fb335dfcae32ab02deedcd750687771d297d73c64e65fc6"
    end
    on_intel do
      url "https://github.com/mbianchidev/sql-not-so-lite/releases/download/v0.1.0/sql-not-so-lite_0.1.0_linux_amd64.tar.gz"
      sha256 "563b6196e395ebb8f69ff555f66cf1824dd08fde9507aadfa56d7cbc2f09ce11"
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
