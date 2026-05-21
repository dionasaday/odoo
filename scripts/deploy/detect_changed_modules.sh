#!/usr/bin/env bash
set -euo pipefail

FROM_REV="${1:-}"
TO_REV="${2:-}"
REPO_DIR="${3:-$(pwd)}"

if [[ -z "$FROM_REV" || -z "$TO_REV" ]]; then
  echo "Usage: $0 <from_rev> <to_rev> [repo_dir]" >&2
  exit 1
fi

declare -A MODULES=()

while IFS= read -r path; do
  top="${path%%/*}"
  [[ -z "$top" || "$top" == "$path" ]] && continue
  if [[ -f "$REPO_DIR/$top/__manifest__.py" ]]; then
    MODULES["$top"]=1
  fi
done < <(git -C "$REPO_DIR" diff --name-only "$FROM_REV" "$TO_REV")

if [[ ${#MODULES[@]} -eq 0 ]]; then
  exit 0
fi

printf '%s\n' "${!MODULES[@]}" | sort | paste -sd "," -
