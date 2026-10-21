class Sendbox < Formula
  desc "Run coding agents in policy-controlled Linux virtual machines"
  homepage "https://github.com/mbianchidev/sendbox"
  # The updater needs one version before the interpolated, metadata-safe default URL.
  version "0.2.2"
  url "https://github.com/mbianchidev/sendbox/releases/download/v#{version}/sendbox-#{version}-macos-arm64.tar.gz"
  sha256 "0acf0d14db16dd9b7124f23f3f589c189b3ec1807d7d3cf9d7dcd7c44a1c8c5c"
  license "Apache-2.0"

  on_macos do
    depends_on arch: :arm64
    depends_on macos: :sequoia
  end

  on_linux do
    depends_on "patchelf" => :build
    depends_on "elfutils"
    depends_on "gcc"
    depends_on "glibc"
    depends_on "libseccomp"
    depends_on "zlib"

    on_intel do
      url "https://github.com/mbianchidev/sendbox/releases/download/v#{version}/sendbox-#{version}-linux-x86_64.tar.gz"
      sha256 "6be290ce83adb14d922991626acf5a838239f98601eedf0ac85c77e6f8cf7046"
    end

    on_arm do
      url "https://github.com/mbianchidev/sendbox/releases/download/v#{version}/sendbox-#{version}-linux-aarch64.tar.gz"
      sha256 "89081de540ccfbf90d2b38c1a122b6b3796881fc083715517507e830fca201d2"
    end
  end

  # Guest executables and metadata are covered by upstream signatures.
  skip_clean "libexec"

  def install
    libexec.install Dir["*"]

    if OS.linux?
      loader = Hardware::CPU.arm? ? "ld-linux-aarch64.so.1" : "ld-linux-x86-64.so.2"
      libraries = [
        formula_opt_lib("glibc"),
        formula_opt_lib("gcc")/"gcc/current",
        formula_opt_lib("elfutils"),
        formula_opt_lib("libseccomp"),
        formula_opt_lib("zlib"),
      ]
      system formula_opt_bin("patchelf")/"patchelf",
             "--set-interpreter", formula_opt_lib("glibc")/loader,
             "--set-rpath", libraries.join(":"),
             libexec/"sendbox"
    end

    bin.install_symlink libexec/"sendbox"
  end

  def caveats
    <<~EOS
      This installs the CLI and signed release payload, not a VM runtime.
      The payload is in #{opt_libexec}.

      Homebrew paths are user-owned and must not be used directly as trusted
      guest bundles. Before launching a VM, follow the verified, versioned,
      root-owned staging instructions at:
        https://github.com/mbianchidev/sendbox/blob/main/docs/installation.md#homebrew

      Run sendbox as your normal user, never with sudo. No setup helper,
      runtime service, or application is started automatically.
      macOS VM sessions need Apple silicon, macOS 26+, and container CLI 0.10.0.
      Linux VM sessions need a separately configured Kata/containerd runtime.
    EOS
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/sendbox --version")
    assert_match "Usage:", shell_output("#{bin}/sendbox --help")
    # Lifecycle CI covers init/policy writes outside Homebrew's restrictive test sandbox.
    assert_match "sendbox", shell_output("#{bin}/sendbox completions print --shell bash")
  end
end
