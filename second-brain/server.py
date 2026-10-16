"""Loopback web app. Sources persist locally; cloud calls require explicit Ask."""
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import secrets
import sys
import threading
from urllib.parse import urlsplit, parse_qs

from brain import Brain, CloudAI
from google_readonly import GoogleReadOnly
from library import Library

ROOT = Path(__file__).resolve().parent


class Application:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.directory.chmod(0o700)
        self.library = Library(self.directory / 'brain.sqlite3')
        self.ai = CloudAI()
        self.brain = Brain(self.library, self.ai)
        self.google = GoogleReadOnly(self.directory)
        self.token = secrets.token_urlsafe(32)
        self.settings_lock = threading.Lock()
        self.event_cache = {}

    def state(self):
        return {'projects': self.library.projects(), 'sources': self.library.sources(),
                'api_configured': bool(self.ai.api_key), 'model': self.ai.model,
                'google': self.google.status()}

    def post(self, path, body):
        project = body.get('project_id')
        if project is not None:
            project = int(project)
        if path == '/api/settings':
            with self.settings_lock:
                model = str(body.get('model', self.ai.model)).strip()
                if not model or len(model) > 100:
                    raise ValueError('Vyplň identifikátor dostupného OpenAI modelu.')
                if body.get('forget_key'):
                    self.ai.api_key = ''
                elif body.get('api_key', '').strip():
                    self.ai.api_key = body['api_key'].strip()
                self.ai.model = model
            return self.state()
        if path == '/api/projects':
            return {'id': self.library.add_project(str(body.get('name', '')))}
        if path == '/api/sources':
            return {'id': self.library.add_source(str(body.get('title', '')), str(body.get('text', '')), project)}
        if path == '/api/pdf':
            from pypdf import PdfReader
            raw = base64.b64decode(body.get('data', ''), validate=True)
            if len(raw) > 8_000_000:
                raise ValueError('PDF může mít nejvýše 8 MB.')
            try:
                reader = PdfReader(io.BytesIO(raw))
                if len(reader.pages) > 300:
                    raise ValueError('PDF může mít nejvýše 300 stran.')
                text = '\n\n'.join(page.extract_text() or '' for page in reader.pages)
            except Exception:
                raise ValueError('PDF nelze přečíst. Použij nešifrované PDF s textovou vrstvou.') from None
            if not text.strip():
                raise ValueError('PDF nemá čitelný text. OCR skenovaných dokumentů zatím není podporované.')
            return {'id': self.library.add_source(str(body.get('title', 'PDF')), text, project)}
        if path == '/api/delete-source':
            self.library.delete_source(int(body['id']))
            return {'ok': True}
        if path == '/api/prepare':
            return {'evidence': self.brain.prepare(str(body.get('question', '')), project,
                                                   body.get('source_ids', []))}
        if path == '/api/ask':
            # Snapshot key/model so settings changes cannot alter an in-flight call.
            with self.settings_lock:
                brain = Brain(self.library, CloudAI(self.ai.api_key, self.ai.model))
            return brain.answer(str(body.get('question', '')), body.get('passage_ids', []), project)
        if path == '/api/google/configure':
            self.google.configure(body.get('config', {}))
            return self.google.status()
        if path == '/api/google/connect':
            self.google.connect()
            return self.google.status()
        if path == '/api/google/disconnect':
            self.google.disconnect()
            return self.google.status()
        if path == '/api/gmail/search':
            return {'messages': self.google.messages(str(body.get('query', 'newer_than:30d')))}
        if path == '/api/gmail/import':
            title, text = self.google.message_source(str(body['id']))
            return {'id': self.library.add_source(title, text, project)}
        if path == '/api/calendar/list':
            events = self.google.events()
            self.event_cache = {event['id']: event for event in events if event.get('id')}
            return {'events': [{'id': e['id'], 'title': e.get('summary', '(bez názvu)'),
                'start': e.get('start', {}).get('dateTime', e.get('start', {}).get('date', ''))}
                for e in events if e.get('id')]}
        if path == '/api/calendar/import':
            event = self.event_cache.get(str(body['id']))
            if event is None:
                raise ValueError('Nejdříve obnov seznam událostí.')
            title, text = self.google.event_source(event)
            return {'id': self.library.add_source(title, text, project)}
        raise ValueError('Neznámá akce.')


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    @property
    def app(self):
        return self.server.app

    def allowed(self, navigation=False):
        port = self.server.server_address[1]
        if self.headers.get('Host') not in (f'127.0.0.1:{port}', f'localhost:{port}'):
            return False
        site = self.headers.get('Sec-Fetch-Site', 'none')
        return (site in ('same-origin', 'none') or (navigation and
            self.headers.get('Sec-Fetch-Mode') == 'navigate' and
            self.headers.get('Sec-Fetch-Dest') == 'document'))

    def reply(self, status, value, mime='application/json; charset=utf-8'):
        raw = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        for key, val in {'Content-Type': mime, 'Content-Length': str(len(raw)), 'Cache-Control': 'no-store',
            'X-Content-Type-Options': 'nosniff', 'Cross-Origin-Resource-Policy': 'same-origin',
            'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; form-action 'self'"}.items():
            self.send_header(key, val)
        self.end_headers()
        self.wfile.write(raw)

    def authorized(self):
        return self.allowed() and secrets.compare_digest(
            self.headers.get('X-Session-Token', ''), self.app.token)

    def do_GET(self):
        parsed = urlsplit(self.path)
        if not self.allowed(navigation=parsed.path == '/'):
            return self.reply(403, {'error': 'Nepovolený přístup.'})
        if parsed.path.startswith('/api/'):
            if not self.authorized():
                return self.reply(403, {'error': 'Nepovolený přístup.'})
            try:
                if parsed.path == '/api/state':
                    return self.reply(200, self.app.state())
                if parsed.path == '/api/source':
                    source_id = int(parse_qs(parsed.query).get('id', ['0'])[0])
                    return self.reply(200, self.app.library.source(source_id))
            except (ValueError, KeyError):
                return self.reply(404, {'error': 'Zdroj neexistuje.'})
            return self.reply(404, {'error': 'Nenalezeno.'})
        files = {'/': ('index.html', 'text/html; charset=utf-8'),
                 '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                 '/style.css': ('style.css', 'text/css; charset=utf-8')}
        if parsed.path not in files:
            return self.reply(404, {'error': 'Nenalezeno.'})
        name, mime = files[parsed.path]
        raw = (ROOT / 'web' / name).read_bytes().replace(b'__TOKEN__', self.app.token.encode())
        self.reply(200, raw, mime)

    def do_POST(self):
        if not self.authorized():
            return self.reply(403, {'error': 'Nepovolený přístup.'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 12_000_000:
                raise ValueError('Požadavek je prázdný nebo příliš velký.')
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError('Neplatný požadavek.')
            self.reply(200, self.app.post(self.path, body))
        except (ValueError, KeyError, TypeError) as exc:
            self.reply(400, {'error': str(exc)})
        except Exception:
            # Never send provider payloads, OAuth secrets or document contents in errors.
            self.reply(500, {'error': 'Operace selhala. Ověř instalaci závislostí a připojení.'})


def create_server(directory, port=8766):
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.app = Application(directory)
    server.daemon_threads = True
    return server


if __name__ == '__main__':
    default = Path.home() / ('Library/Application Support/Second Brain' if sys.platform == 'darwin'
                             else '.local/share/second-brain')
    directory = Path(os.environ.get('BRAIN_DATA_DIR', str(default)))
    server = create_server(directory)
    print('Second Brain: otevři v Chromu http://127.0.0.1:8766 · ukončení Ctrl+C', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
