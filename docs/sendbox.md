# Sendbox

[Documentation](README.md)

[Sendbox](https://github.com/mbianchidev/sendbox) runs coding agents in
policy-controlled Linux VMs. The formula installs published host binaries,
configuration examples, a setup helper and the matching signed guest payload.
No Rust compiler or frontend build is needed.

## Install and verify

The CLI supports Apple silicon on macOS 15+ and Linux x86_64/aarch64. There is
no published Intel macOS binary. On Linux, Homebrew supplies the native libraries
and ELF loader rather than relying on distribution packages.

```bash
brew install mbianchidev/tap/sendbox
sendbox --version
sendbox --help
```

The verification commands print the installed version and CLI usage. Installation
does not configure a VM runtime or start a VM, agent or service.

## Runtime setup

macOS VM sessions require Apple silicon, macOS 26+ and Apple `container` CLI
0.10.0. Linux sessions require hardware or nested virtualization and a configured
Kata/containerd/nerdctl runtime.

The complete release payload is under `$(brew --prefix sendbox)/libexec`.
**Do not pass this user-owned Homebrew guest directory directly to `sendbox run`.**
Follow the upstream [Homebrew installation guide](https://github.com/mbianchidev/sendbox/blob/main/docs/installation.md#homebrew)
to verify and copy the matching guest bundle and trust root to
`/opt/sendbox/<version>/guest/<architecture>`. That runtime path needs root-owned,
non-writable ancestors, `0555` guest executables and `0444` metadata/trust roots.

Staging is an explicit administrator action, never a formula postinstall step.
Run Sendbox as your normal user, not with `sudo`. Do not run the bundled
`setup.sh` merely to install or smoke-test the CLI: it performs runtime preflight
and can offer additional installation steps.

See the upstream [runtime quickstart](https://github.com/mbianchidev/sendbox#quick-start)
for configuration and running an agent after the runtime is ready.

## Upgrades and removal

```bash
brew update
brew upgrade mbianchidev/tap/sendbox
```

Explicitly stage the new matching guest payload before launching the upgraded
version.

```bash
brew uninstall mbianchidev/tap/sendbox
```

Upgrades and removal preserve `~/.sendbox/`, project `.sendbox.yaml` files and
separately staged root-owned runtime bundles. Homebrew removes only its package.
Retire old runtime bundles explicitly when they are no longer needed.
