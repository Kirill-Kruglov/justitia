#!/usr/bin/env bash
# Install the gate_harness pre-commit hook into this repository.
#
# Fails closed: if a different pre-commit hook already exists, this script
# refuses to overwrite it and tells you to chain them manually.
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
hooks_dir="$repo_root/.git/hooks"
src="$repo_root/gate_harness/hooks/pre-commit"
dst="$hooks_dir/pre-commit"

if [[ ! -f "$src" ]]; then
  echo "error: $src not found" >&2
  exit 1
fi

mkdir -p "$hooks_dir"

if [[ -e "$dst" ]] && ! cmp -s "$src" "$dst"; then
  echo "error: a different pre-commit hook already exists at $dst" >&2
  echo "refusing to overwrite (fail closed). Chain them manually, then re-run." >&2
  exit 1
fi

# Symlink so the installed hook tracks the versioned source.
ln -sf "$src" "$dst"
chmod +x "$src"
echo "installed gate_harness pre-commit hook -> $dst"
