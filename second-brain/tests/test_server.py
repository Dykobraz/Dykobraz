import base64
import http.client
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import create_server
from brain import CloudAI


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.server = create_server(self.temp.name, port=0)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(3)
        self.temp.cleanup()

    def request(self, path, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_address[1], timeout=5)
        h = {'X-Session-Token': self.server.app.token, **(headers or {})}
        conn.request('GET' if body is None else 'POST', path,
            body=None if body is None else json.dumps(body), headers=h)
        response = conn.getresponse()
        status, mime, raw = response.status, response.getheader('Content-Type'), response.read()
        conn.close()
        return status, json.loads(raw) if mime.startswith('application/json') else raw

    def test_web_app_loads_and_token_is_injected(self):
        self.assertEqual(self.request('/')[0], 200)
        status, script = self.request('/app.js')
        self.assertEqual(status, 200)
        self.assertIn(self.server.app.token.encode(), script)
        self.assertNotIn(b'__TOKEN__', script)

    def test_rejects_wrong_host_wrong_token_and_cross_origin(self):
        for headers in ({'Host': 'evil.example'}, {'X-Session-Token': 'wrong'},
                        {'Sec-Fetch-Site': 'cross-site'}):
            self.assertEqual(self.request('/api/state', headers=headers)[0], 403)
            self.assertEqual(self.request('/api/sources', {'title': 'x', 'text': 'y'}, headers)[0], 403)

    def test_navigation_from_chat_can_open_only_public_page(self):
        h = {'Sec-Fetch-Site': 'cross-site', 'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-Dest': 'document'}
        self.assertEqual(self.request('/', headers=h)[0], 200)
        self.assertEqual(self.request('/api/state', headers=h)[0], 403)

    def test_source_project_evidence_answer_export_delete_workflow(self):
        _, project = self.request('/api/projects', {'name': 'Studium'})
        _, source = self.request('/api/sources', {'title': 'Plán', 'text': 'Projekt má rozpočet 100 Kč.',
                                                  'project_id': project['id']})
        status, prepared = self.request('/api/prepare', {'question': 'rozpočet', 'project_id': project['id']})
        self.assertEqual(status, 200)
        pid = prepared['evidence'][0]['passage_id']
        reply = {'statements': [{'kind': 'fact', 'text': 'Rozpočet je 100 Kč.', 'passage_ids': [pid]}], 'follow_up': []}
        with patch.object(CloudAI, 'answer', return_value=reply) as ai:
            status, answer = self.request('/api/ask', {'question': 'Jaký je rozpočet?',
                'project_id': project['id'], 'passage_ids': [pid]})
        self.assertEqual(status, 200)
        self.assertEqual(answer['statements'], reply['statements'])
        self.assertEqual(ai.call_args.args[1][0]['text'], 'Projekt má rozpočet 100 Kč.')
        self.assertEqual(self.request('/api/source?id=' + str(source['id']))[1]['body'], 'Projekt má rozpočet 100 Kč.')
        self.request('/api/delete-source', {'id': source['id']})
        self.assertEqual(self.request('/api/source?id=' + str(source['id']))[0], 404)

    def test_key_is_never_returned_or_persisted(self):
        key = 'test-only-not-a-real-secret'
        status, settings = self.request('/api/settings', {'api_key': key, 'model': 'gpt-4.1'})
        self.assertEqual(status, 200)
        self.assertTrue(settings['api_configured'])
        self.assertNotIn(key, json.dumps(settings))
        self.assertNotIn(key, json.dumps(self.request('/api/state')[1]))
        for path in Path(self.temp.name).rglob('*'):
            if path.is_file():
                self.assertNotIn(key.encode(), path.read_bytes())
        self.request('/api/settings', {'forget_key': True})
        self.assertFalse(self.request('/api/state')[1]['api_configured'])

    def test_pdf_without_text_is_rejected_instead_of_fake_success(self):
        from pypdf import PdfWriter
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        data = io.BytesIO(); writer.write(data)
        status, result = self.request('/api/pdf', {'title': 'Sken', 'data': base64.b64encode(data.getvalue()).decode()})
        self.assertEqual(status, 400)
        self.assertIn('OCR', result['error'])
        self.assertEqual(self.server.app.library.sources(), [])

    def test_text_pdf_is_extracted_and_saved_locally(self):
        from pypdf import PdfWriter
        from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
        writer = PdfWriter()
        page = writer.add_blank_page(width=200, height=200)
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
            NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'):
            DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
        content = DecodedStreamObject()
        content.set_data(b'BT /F1 12 Tf 10 100 Td (Project budget is 100 CZK.) Tj ET')
        page[NameObject('/Contents')] = writer._add_object(content)
        data = io.BytesIO(); writer.write(data)
        status, result = self.request('/api/pdf', {'title': 'PDF plan',
            'data': base64.b64encode(data.getvalue()).decode()})
        self.assertEqual(status, 200)
        self.assertIn('100 CZK', self.server.app.library.source(result['id'])['body'])

    def test_google_import_stays_local_until_user_asks_ai(self):
        with patch.object(self.server.app.google, 'message_source', return_value=('Gmail: Projekt', 'Rozpočet je 100 Kč.')), \
                patch.object(CloudAI, 'answer') as ai:
            status, result = self.request('/api/gmail/import', {'id': 'abc'})
        self.assertEqual(status, 200)
        self.assertTrue(self.server.app.library.source(result['id']))
        ai.assert_not_called()


if __name__ == '__main__':
    unittest.main()
