class Sendbox < Formula
  desc "Run coding agents in policy-controlled Linux virtual machines"
  homepage "https://github.com/mbianchidev/sendbox"
  # The updater needs one version before the interpolated, metadata-safe default URL.
  version "0.2.7"
  url "https://github.com/mbianchidev/sendbox/releases/download/v#{version}/sendbox-#{version}-macos-arm64.tar.gz"
  sha256 "9e49068b854e72e6ff1569639320be5f9df8507b1a002f3b77516855389e1972"
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
      sha256 "277f20692700e091944c582b95e5e67cb258d86a65b93f24bf6435578e5561b5"
    end

    on_arm do
      url "https://github.com/mbianchidev/sendbox/releases/download/v#{version}/sendbox-#{version}-linux-aarch64.tar.gz"
      sha256 "8b8d4e08663b0b63208fcc6eae7aa4aa305e50fc29fcf23db312e22842da866f"
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
