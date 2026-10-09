"""Genera il sito e avvia un'anteprima locale che segue le modifiche ai sorgenti."""

import argparse
import functools
import subprocess
import sys
from datetime import date
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'public'
BUILD_SCRIPT = ROOT / 'tools/build.py'
build_lock = Lock()
last_signature = None


def source_signature():
    """Il server rigenera solo quando cambia un contenuto, un modello o un asset."""

    files = [BUILD_SCRIPT]
    for folder in ('content', 'templates', 'assets'):
        files.extend(path for path in (ROOT / folder).rglob('*') if path.is_file())
    return (date.today().isoformat(), tuple(
        (str(path), path.stat().st_mtime_ns, path.stat().st_size)
        for path in sorted(files)
    ))


def rebuild_if_needed():
    global last_signature
    with build_lock:
        signature = source_signature()
        if signature != last_signature:
            subprocess.run([sys.executable, str(BUILD_SCRIPT)], cwd=ROOT, check=True)
            last_signature = signature


class PreviewHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        try:
            rebuild_if_needed()
        except (OSError, subprocess.CalledProcessError):
            self.send_error(500, 'Generazione non riuscita. Controlla il messaggio nel terminale di VS Code.')
            return
        super().do_GET()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765, help='Porta locale (default: 8765).')
    arguments = parser.parse_args()
    try:
        rebuild_if_needed()
        handler = functools.partial(PreviewHandler, directory=str(OUTPUT))
        server = ThreadingHTTPServer(('127.0.0.1', arguments.port), handler)
    except (OSError, subprocess.CalledProcessError) as error:
        print(f'Impossibile avviare l’anteprima: {error}', file=sys.stderr)
        return 1
    print(f'Anteprima: http://127.0.0.1:{arguments.port}/', flush=True)
    print('Salva le modifiche, poi aggiorna il browser. Ctrl+C ferma l’anteprima.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nAnteprima terminata.')
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
