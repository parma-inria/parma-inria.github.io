"""Build the site and serve a local preview that follows source changes."""

import argparse
import functools
import hashlib
import json
import subprocess
import sys
import webbrowser
from datetime import date
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from urllib.request import urlopen
from urllib.parse import urlsplit

# Local paths and preview identity
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "public"
BUILD_SCRIPT = ROOT / "tools/build.py"
# Reuse a running preview only when it belongs to this checkout.
PROJECT_ID = hashlib.sha256(str(ROOT).casefold().encode("utf-8")).hexdigest()
build_lock = Lock()
last_signature = None


# Rebuild the generated files when editable sources change


def source_signature():
    """Rebuild only when the date or an editable source changes."""
    files = [BUILD_SCRIPT]
    for folder in ("content", "pages", "assets"):
        files.extend(path for path in (ROOT / folder).rglob("*") if path.is_file())
    return (date.today().isoformat(), tuple(
        (str(path), path.stat().st_mtime_ns, path.stat().st_size)
        for path in sorted(files)
    ))


def rebuild_if_needed():
    """Serialize builds so simultaneous browser requests cannot overlap."""
    global last_signature
    with build_lock:
        signature = source_signature()
        if signature != last_signature:
            subprocess.run([sys.executable, str(BUILD_SCRIPT)], cwd=ROOT, check=True)
            last_signature = signature


# Serve the preview and identify it for the Windows launcher


class PreviewServer(ThreadingHTTPServer):
    # On Windows, prevent two servers from binding to the same port.
    allow_reuse_address = False


class PreviewHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        # This lets the launcher recognise this project's already-running preview.
        if urlsplit(self.path).path == "/__parma_preview__":
            body = json.dumps({"project": PROJECT_ID}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        # Refresh public/ before serving the requested page or asset.
        try:
            rebuild_if_needed()
        except (OSError, subprocess.CalledProcessError):
            self.send_error(500, "Build failed. Check the message in the preview terminal.")
            return
        super().do_GET()


def existing_preview_matches(url):
    """Check whether the requested port already serves this project."""
    try:
        with urlopen(url + "__parma_preview__", timeout=2) as response:
            return json.load(response).get("project") == PROJECT_ID
    except (OSError, ValueError):
        return False


def open_browser(url):
    """Open the default browser, or leave a usable URL in the terminal."""
    try:
        if not webbrowser.open(url):
            print("Open the preview URL in your browser.", flush=True)
    except webbrowser.Error:
        print("Open the preview URL in your browser.", flush=True)


# Start the server, or reuse this project's existing preview


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765, help="Local port (default: 8765).")
    parser.add_argument("--open", action="store_true", help="Open the preview in your browser.")
    arguments = parser.parse_args()
    url = f"http://127.0.0.1:{arguments.port}/"
    if arguments.open and existing_preview_matches(url):
        print(f"Preview already running: {url}", flush=True)
        open_browser(url)
        return 0

    # Bind only to this computer and serve the generated folder.
    handler = functools.partial(PreviewHandler, directory=str(OUTPUT))
    try:
        server = PreviewServer(("127.0.0.1", arguments.port), handler)
    except OSError as error:
        if arguments.open and existing_preview_matches(url):
            print(f"Preview already running: {url}", flush=True)
            open_browser(url)
            return 0
        print(f"Cannot start preview: {error}", file=sys.stderr)
        return 1

    # Build once before opening the browser.
    try:
        rebuild_if_needed()
    except (OSError, subprocess.CalledProcessError) as error:
        server.server_close()
        print(f"Cannot build preview: {error}", file=sys.stderr)
        return 1
    print(f"Preview: {url}", flush=True)
    print("Keep this terminal open. Save your changes and refresh the browser.", flush=True)
    print("Press Ctrl+C to stop the preview.", flush=True)
    if arguments.open:
        open_browser(url)

    # Keep serving until Ctrl+C, then release the port.
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nPreview stopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
