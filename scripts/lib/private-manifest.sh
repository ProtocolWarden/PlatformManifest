# private-manifest.sh — shared role resolver for the private-manifest repo.
# Sourced by clone-repos.sh and provision-machine.sh (single source of truth;
# the two copies this replaces had already started life byte-identical).
#
# Contract: the caller must set GITHUB_DIR before sourcing. Resolution is by
# ROLE, never by repo-instance name: $PRIVATE_MANIFEST_DIR wins, else scan
# GITHUB_DIR for a repo hosting a private_manifest*.yaml (the manifest *type*
# filename).

_discover_private_manifest_dir() {
  if [[ -n "${PRIVATE_MANIFEST_DIR:-}" && -d "$PRIVATE_MANIFEST_DIR" ]]; then
    echo "$PRIVATE_MANIFEST_DIR"
    return 0
  fi
  local d
  for d in "$GITHUB_DIR"/*/; do
    if compgen -G "${d}private_manifest*.yaml" >/dev/null 2>&1 \
       || compgen -G "${d}src/*/data/private_manifest*.yaml" >/dev/null 2>&1 \
       || compgen -G "${d}manifests/private_manifest*.yaml" >/dev/null 2>&1 \
       || compgen -G "${d}manifests/*/private_manifest*.yaml" >/dev/null 2>&1; then
      echo "${d%/}"
      return 0
    fi
  done
  return 1
}
