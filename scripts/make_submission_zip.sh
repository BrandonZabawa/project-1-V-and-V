#!/usr/bin/env bash
# make_submission_zip.sh -- build the autograder zip from this repo.
#
# The zip holds exactly the files git would track under .gitignore (no .git/,
# no sim_build/, no raw per-seed logs, no demo videos), under one top folder
# named fifo_p1/. That keeps the upload small: a folder upload of the working
# tree sent about 300 files and the server answered each with "502 Bad Gateway".
#
#   scripts/make_submission_zip.sh                  # writes ../fifo_p1_submission.zip (next to the repo)
#   scripts/make_submission_zip.sh ~/out.zip        # choose the output path
#   STRICT=1 scripts/make_submission_zip.sh         # refuse to build while placeholders remain
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output="$(realpath -m "${1:-$repo/../fifo_p1_submission.zip}")"

# 1. Placeholders that must be filled before submitting.
placeholder_pattern='<NID>|<paste |<%>|<team name>|<URL>|<who>|<add |<his |<one line'
if grep -n -E "$placeholder_pattern" "$repo"/*.md >/tmp/placeholders.$$ 2>/dev/null; then
    echo "Placeholders still to fill:"
    sed "s|^$repo/|  |" /tmp/placeholders.$$ | cut -c1-140
    rm -f /tmp/placeholders.$$
    if [[ "${STRICT:-0}" == "1" ]]; then
        echo "STRICT=1: not building the zip."
        exit 1
    fi
    echo "(building anyway; run with STRICT=1 to refuse)"
    echo
fi
rm -f /tmp/placeholders.$$

# 2. Let git decide what is kept, in a throwaway copy so the real repo's index is untouched.
staging="$(mktemp -d)"
trap 'rm -rf "$staging"' EXIT
tar --exclude=./.git -C "$repo" -cf - . | tar -C "$staging" -xf -
git -C "$staging" init -q
git -C "$staging" add -A
git -C "$staging" ls-files -z > "$staging/.file_list"

# 3. Write the zip (Python, so it works where the zip command is not installed).
python3 - "$staging" "$output" <<'PYTHON'
import os, sys, zipfile
staging, output = sys.argv[1], sys.argv[2]
names = [n for n in open(os.path.join(staging, ".file_list"), "rb").read().decode().split("\0") if n]
os.makedirs(os.path.dirname(output), exist_ok=True)
if os.path.exists(output):
    os.remove(output)
with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
    for name in sorted(names):
        path = os.path.join(staging, name)
        info = zipfile.ZipInfo.from_file(path, arcname=f"fifo_p1/{name}")
        info.compress_type = zipfile.ZIP_DEFLATED
        with open(path, "rb") as handle:
            archive.writestr(info, handle.read())
size_kib = os.path.getsize(output) / 1024
print(f"wrote {output}: {len(names)} files, {size_kib:.0f} KiB")
PYTHON
