"""Google desktop OAuth; only read-only Gmail and Calendar endpoints."""
import base64
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import threading

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly',
          'https://www.googleapis.com/auth/calendar.readonly']


def private_json(path, value):
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    import os
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class PlainHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.hidden = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        if tag in ('br', 'p', 'div', 'li'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def mail_text(payload):
    plain, html = [], []

    def walk(part):
        if part.get('filename'):
            return  # No attachments are fetched or imported.
        data = part.get('body', {}).get('data', '')
        if data and part.get('mimeType') in ('text/plain', 'text/html'):
            decoded = base64.urlsafe_b64decode(data + '=' * (-len(data) % 4)).decode('utf-8', errors='replace')
            (plain if part['mimeType'] == 'text/plain' else html).append(decoded)
        for child in part.get('parts', []):
            walk(child)

    walk(payload)
    if plain:
        return '\n'.join(plain)
    parser = PlainHTML()
    parser.feed('\n'.join(html))
    return ''.join(parser.parts)


class GoogleReadOnly:
    def __init__(self, data_dir):
        self.directory = Path(data_dir)
        self.client_path = self.directory / 'google-client.json'
        self.token_path = self.directory / 'google-token.json'
        self.lock = threading.RLock()
        self.authorizing = False
        self.generation = 0
        self.message = ''

    def status(self):
        with self.lock:
            return {'configured': self.client_path.exists(), 'connected': self.token_path.exists(),
                    'authorizing': self.authorizing, 'message': self.message}

    def configure(self, config):
        installed = config.get('installed', {})
        if (not installed.get('client_id') or not installed.get('client_secret')
                or installed.get('auth_uri') != 'https://accounts.google.com/o/oauth2/auth'
                or installed.get('token_uri') != 'https://oauth2.googleapis.com/token'):
            raise ValueError('Vyber OAuth JSON stažený z Google Cloud pro aplikaci typu Desktop app.')
        with self.lock:
            if self.authorizing:
                raise ValueError('Nejdříve dokonči probíhající přihlášení.')
            self.token_path.unlink(missing_ok=True)
            private_json(self.client_path, config)

    def connect(self):
        with self.lock:
            if self.authorizing:
                return
            if not self.client_path.exists():
                raise ValueError('Nejdříve nahraj Google OAuth JSON v nastavení.')
            self.authorizing = True
            self.message = 'Dokonči přihlášení v otevřeném prohlížeči.'
            generation = self.generation

        def authorize():
            try:
                from google_auth_oauthlib.flow import InstalledAppFlow
                flow = InstalledAppFlow.from_client_secrets_file(str(self.client_path), SCOPES)
                credentials = flow.run_local_server(host='127.0.0.1', port=0,
                    authorization_prompt_message='', success_message='Připojeno. Tuto kartu můžeš zavřít.',
                    open_browser=True, timeout_seconds=180, access_type='offline', prompt='consent')
                with self.lock:
                    if generation == self.generation:
                        private_json(self.token_path, json.loads(credentials.to_json()))
                        self.message = 'Google účet připojen pouze pro čtení.'
            except Exception:
                with self.lock:
                    if generation == self.generation:
                        self.message = 'Přihlášení se nezdařilo. Ověř OAuth klienta, testovacího uživatele a povolená API.'
            finally:
                with self.lock:
                    self.authorizing = False

        threading.Thread(target=authorize, daemon=True).start()

    def disconnect(self):
        with self.lock:
            self.generation += 1
            self.token_path.unlink(missing_ok=True)
            self.message = 'Místní přístup odpojen. Dříve importované zdroje zůstávají v knihovně.'

    def _get(self, path, params=None):
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import AuthorizedSession
        with self.lock:
            if not self.token_path.exists():
                raise ValueError('Nejdříve připoj Google účet v nastavení.')
            try:
                credentials = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
                with AuthorizedSession(credentials) as session:
                    host = 'https://gmail.googleapis.com/' if path.startswith('gmail/v1/') else 'https://www.googleapis.com/'
                    response = session.get(host + path, params=params, timeout=30)
                response.raise_for_status()
                private_json(self.token_path, json.loads(credentials.to_json()))
                return response.json()
            except Exception:
                raise ValueError('Google požadavek selhal. Ověř připojení účtu a povolení Gmail/Calendar API.') from None

    def messages(self, query):
        results = self._get('gmail/v1/users/me/messages', {'q': query[:500], 'maxResults': 10})
        messages = []
        for item in results.get('messages', []):
            result = self._get('gmail/v1/users/me/messages/' + item['id'],
                               {'format': 'metadata', 'metadataHeaders': ['Subject', 'From', 'Date']})
            headers = {h['name'].lower(): h['value'] for h in result.get('payload', {}).get('headers', [])}
            messages.append({'id': item['id'], 'title': headers.get('subject', '(bez předmětu)'),
                             'sender': headers.get('from', ''), 'date': headers.get('date', '')})
        return messages

    def message_source(self, message_id):
        import re
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', message_id):
            raise ValueError('Neplatný identifikátor zprávy.')
        result = self._get('gmail/v1/users/me/messages/' + message_id, {'format': 'full'})
        headers = {h['name'].lower(): h['value'] for h in result.get('payload', {}).get('headers', [])}
        body = mail_text(result.get('payload', {}))
        if len(body) > 400_000:
            raise ValueError('Zpráva je příliš dlouhá pro tento import.')
        title = headers.get('subject', '(bez předmětu)')[:210]
        text = (f"Gmail · {title}\nOd: {headers.get('from', '')}\n"
                f"Datum zprávy: {headers.get('date', '')}\nID zprávy: {message_id}\n\n{body}")
        return 'Gmail: ' + title, text

    def events(self):
        now = datetime.now(timezone.utc)
        return self._get('calendar/v3/calendars/primary/events', {
            'timeMin': now.isoformat(), 'timeMax': (now + timedelta(days=7)).isoformat(),
            'singleEvents': 'true', 'orderBy': 'startTime', 'maxResults': 30}).get('items', [])

    @staticmethod
    def event_source(event):
        title = str(event.get('summary', '(bez názvu)'))[:210]
        text = (f"Google Kalendář · {title}\nStav: {event.get('status', '')}\n"
                f"Začátek: {json.dumps(event.get('start', {}), ensure_ascii=False)}\n"
                f"Konec: {json.dumps(event.get('end', {}), ensure_ascii=False)}\n"
                f"Místo: {event.get('location', '')}\n\n{event.get('description', '')}")
        return 'Kalendář: ' + title, text
