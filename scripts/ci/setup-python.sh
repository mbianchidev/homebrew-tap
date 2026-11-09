#!/usr/bin/env bash
set -euo pipefail

fail() {
  printf 'ci-python: %s\n' "$*" >&2
  exit 1
}

[[ "${GITHUB_ACTIONS:-}" == true && "${TAP_CI_RUNNER_ENVIRONMENT:-}" == github-hosted &&
   -n "${RUNNER_TOOL_CACHE:-}" && -n "${RUNNER_TEMP:-}" ]] ||
  fail "a GitHub-hosted Actions tool-cache environment is required"

version=3.15.1
checksum_command=(sha256sum --check)
platform="$(uname -s):$(uname -m)"
case "$platform" in
  Darwin:arm64)
    arch=arm64
    asset=662872898
    digest=e1a49acab28b4a180ee9819663f9e01d0e56ed49f78b1e370dedea8863301a3a
    checksum_command=(shasum -a 256 --check)
    ;;
  Darwin:x86_64)
    arch=x64
    asset=662872991
    digest=cf2d9c042c9ec5a42e4ae45259faf9dfbbbd21e915ab6b892acaef5312872156
    checksum_command=(shasum -a 256 --check)
    ;;
  Linux:x86_64|Linux:aarch64)
    [[ "$(lsb_release -is)" == Ubuntu ]] || fail "only Ubuntu Linux is supported"
    arch=x64
    [[ "$platform" != Linux:aarch64 ]] || arch=arm64
    case "$(lsb_release -rs):$arch" in
      22.04:x64) asset=662873037; digest=d5089a4a7ab6cea9664fb26cdae5c6379f880edc368a5be81999455c25cda556 ;;
      22.04:arm64) asset=662873061; digest=f4ba4a82780f5d4035de9e86a05f08a8b46a0d4ccbe06a5bb349700ed97e88f7 ;;
      24.04:x64) asset=662872932; digest=9809d583ffee9af685f33c8746da541d7102c30a7baa7aacf0a30a1f04731a56 ;;
      24.04:arm64) asset=662872919; digest=329908df038ce3d6ab823f84c11a5f6192b660ec93edc33c0ecc33cb832d6310 ;;
      26.04:x64) asset=662873040; digest=0aa6f845c6f40c4a88a99e92a46374889ab9170fde378f1168e2e936b34d1218 ;;
      26.04:arm64) asset=662872974; digest=119ef812a16900b5f4750d2b003766951f09d49b312123be25583db542c63b6e ;;
      *) fail "no pinned archive is configured for this Ubuntu release and architecture" ;;
    esac
    ;;
  *) fail "unsupported runner platform: $platform" ;;
esac

cache="$RUNNER_TOOL_CACHE/Python/$version/$arch"
if [[ ! -f "$cache.complete" ]]; then
  [[ -n "${GH_TOKEN:-}" ]] || fail "the job-scoped GitHub token is required for asset downloads"
  directory="$(mktemp -d "$RUNNER_TEMP/tap-python.XXXXXX")"
  cleanup() {
    [[ "$directory" == "$RUNNER_TEMP"/tap-python.* ]] || fail "refusing unexpected cleanup path"
    rm -rf -- "$directory"
  }
  trap cleanup EXIT
  archive="$directory/python.tar.gz"
  curl --fail --silent --show-error --location --retry 5 --retry-max-time 600 \
    --connect-timeout 10 --max-time 600 --header 'Accept: application/octet-stream' \
    --header "Authorization: Bearer $GH_TOKEN" \
    "https://api.github.com/repos/actions/python-versions/releases/assets/$asset" --output "$archive"
  printf '%s  %s\n' "$digest" "$archive" | "${checksum_command[@]}"
  tar -xzf "$archive" -C "$directory"
  rm -- "$archive"
  cd "$directory"
  if [[ "$platform" == Linux:* ]]; then
    export LD_LIBRARY_PATH="$directory/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  fi
  AGENT_TOOLSDIRECTORY="$RUNNER_TOOL_CACHE" bash ./setup.sh
fi

installed="$("$cache/bin/python3" --version)"
[[ "$installed" == "Python $version" ]] || fail "unexpected cached interpreter: $installed"
printf 'Using %s (%s)\n' "$installed" "$arch"
