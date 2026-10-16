import base64
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from google_readonly import GoogleReadOnly, SCOPES, mail_text


def encoded(text):
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip('=')


class GoogleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.google = GoogleReadOnly(self.temp.name)

    def test_oauth_config_has_private_permissions_and_status_never_exposes_secrets(self):
        config = {'installed': {'client_id': 'test-id', 'client_secret': 'test-secret',
            'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
            'token_uri': 'https://oauth2.googleapis.com/token'}}
        self.google.configure(config)
        self.assertEqual(stat.S_IMODE(self.google.client_path.stat().st_mode), 0o600)
        self.assertNotIn('test-secret', json.dumps(self.google.status()))
        self.assertTrue(all(scope.endswith('.readonly') for scope in SCOPES))

    def test_third_party_oauth_token_destination_is_rejected(self):
        with self.assertRaises(ValueError):
            self.google.configure({'installed': {'client_id': 'id', 'client_secret': 'secret',
                'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                'token_uri': 'https://attacker.example/token'}})
        self.assertFalse(self.google.client_path.exists())

    def test_mail_uses_plain_text_and_ignores_attachments(self):
        payload = {'parts': [
            {'mimeType': 'text/html', 'body': {'data': encoded('<b>HTML verze</b>')}},
            {'mimeType': 'text/plain', 'body': {'data': encoded('Původní zpráva')}},
            {'mimeType': 'text/plain', 'filename': 'private.txt', 'body': {'data': encoded('Příloha')}}]}
        self.assertEqual(mail_text(payload), 'Původní zpráva')

    def test_html_mail_drops_scripts_and_markup(self):
        payload = {'mimeType': 'text/html', 'body': {'data': encoded('<p>Ahoj</p><script>nebezpečí()</script><p>Svět</p>')}}
        text = mail_text(payload)
        self.assertIn('Ahoj', text)
        self.assertNotIn('nebezpečí', text)
        self.assertNotIn('<p>', text)

    def test_search_does_not_fetch_message_bodies(self):
        with patch.object(self.google, '_get', side_effect=[{'messages': [{'id': 'abc'}]},
            {'payload': {'headers': [{'name': 'Subject', 'value': 'Seminář'}]}}]) as get:
            result = self.google.messages('newer_than:7d')
        self.assertEqual(result[0]['title'], 'Seminář')
        self.assertEqual(get.call_args_list[1].args[1]['format'], 'metadata')

    def test_import_fetches_only_selected_mail(self):
        with patch.object(self.google, '_get', return_value={'payload': {
                'headers': [{'name': 'Subject', 'value': 'Projekt'}],
                'mimeType': 'text/plain', 'body': {'data': encoded('Příští krok')}}}) as get:
            title, body = self.google.message_source('abc123')
        self.assertEqual(title, 'Gmail: Projekt')
        self.assertIn('Příští krok', body)
        self.assertEqual(get.call_args.args[0], 'gmail/v1/users/me/messages/abc123')

    def test_disconnect_invalidates_pending_oauth_and_deletes_local_token(self):
        self.google.token_path.write_text('{}')
        generation = self.google.generation
        self.google.disconnect()
        self.assertFalse(self.google.token_path.exists())
        self.assertGreater(self.google.generation, generation)


if __name__ == '__main__':
    unittest.main()
