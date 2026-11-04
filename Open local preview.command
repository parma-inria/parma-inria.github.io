#!/bin/bash
# Start the preview from this project, even when Finder opens the file elsewhere.
parma_script_dir="$(cd -- "$(dirname "$0")" && pwd)" || exit 1
cd -- "$parma_script_dir" || exit 1

# Finder may not include Homebrew or the Python installer in its PATH.
parma_python=""
for parma_candidate in python3 /opt/homebrew/bin/python3 /usr/local/bin/python3 python; do
  if command -v "$parma_candidate" >/dev/null 2>&1 &&
     "$parma_candidate" -c 'import sys; sys.exit(sys.version_info < (3, 10))' >/dev/null 2>&1; then
    parma_python="$parma_candidate"
    break
  fi
done

# Keep failures readable when the launcher was opened by double-clicking.
parma_pause_after_error() {
  if [ -t 0 ]; then
    printf '\nPress Return to close this window...'
    IFS= read -r parma_reply
  fi
}

if [ -z "$parma_python" ]; then
  printf 'Python 3.10 or later is required. Install Python 3 and try again.\n'
  printf 'Download: https://www.python.org/downloads/macos/\n'
  parma_pause_after_error
  exit 1
fi

# The shared preview tool builds the site, opens the browser and reuses a running preview.
"$parma_python" "$parma_script_dir/tools/preview.py" --open
parma_preview_status=$?
if [ "$parma_preview_status" -ne 0 ]; then
  printf '\nThe preview could not start. See the message above.\n'
  parma_pause_after_error
fi
exit "$parma_preview_status"
