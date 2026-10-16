import http.client
import io
import json
import queue
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app


class SessionTests(unittest.TestCase):
    def test_slow_notes_do_not_block_pending_text_and_batch_the_backlog(self):
        s = app.Session()
        texts = queue.Queue(maxsize=32)
        finished, failed = threading.Event(), threading.Event()
        entered, release, second = threading.Event(), threading.Event(), threading.Event()
        received, errors = [], []

        def model(previous, incoming, goals):
            received.append(incoming)
            if len(received) == 1:
                entered.set()
                release.wait(3)
            else:
                second.set()
            return 'poznámky'

        with patch.object(app, 'summarize', model):
            worker = threading.Thread(target=s.note_loop,
                args=(texts, s.epoch, finished, failed, errors))
            worker.start()
            try:
                texts.put_nowait('první')
                self.assertTrue(entered.wait(2))
                texts.put_nowait('druhý')
                texts.put_nowait('třetí')
                self.assertEqual(texts.qsize(), 2)
                release.set()
                self.assertTrue(second.wait(2))
            finally:
                release.set()
                finished.set()
                worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(received, ['první', 'druhý\ntřetí'])
        self.assertFalse(failed.is_set())
        self.assertEqual(errors, [])

    def test_note_pipeline_failure_is_reported_to_capture(self):
        s = app.Session()
        texts = queue.Queue()
        texts.put('obsah')
        finished, failed = threading.Event(), threading.Event()
        errors = []
        with patch.object(app, 'summarize', side_effect=RuntimeError('Model není dostupný')):
            s.note_loop(texts, s.epoch, finished, failed, errors)
        self.assertTrue(failed.is_set())
        self.assertIn('Model není dostupný', errors[0])
        self.assertEqual(s.notes, '')

    def test_capture_keeps_recognizing_while_summary_is_blocked(self):
        import base64
        import types
        try:
            import numpy as np
            import scipy.signal
        except ImportError:
            self.skipTest('Integration check requires installed numpy and scipy.')
        s = app.Session()
        s.running = True
        entered, release, recognized, stopped = (threading.Event() for _ in range(4))
        line = (json.dumps({'rate': 16000, 'pcm': base64.b64encode(
            np.full(16000 * 15, 0.1, dtype='<f4').tobytes()).decode()}) + '\n').encode()

        class Process:
            stderr = iter(())

            @property
            def stdout(self):
                for _ in range(3):
                    yield line
                stopped.wait(4)

            def poll(self):
                return 0 if stopped.is_set() else None

            def terminate(self):
                stopped.set()

            kill = terminate

            def wait(self, **kwargs):
                stopped.set()

        class Whisper:
            count = 0

            def transcribe(self, audio, **kwargs):
                self.count += 1
                if self.count == 3:
                    recognized.set()
                return iter([types.SimpleNamespace(text='Pracovní text')]), None

        s.whisper = Whisper()

        def model(*args):
            entered.set()
            release.wait(4)
            return 'opožděné poznámky'

        with patch.dict(sys.modules, {'faster_whisper': types.SimpleNamespace(WhisperModel=None)}), \
                patch.object(app.subprocess, 'Popen', return_value=Process()), \
                patch.object(app, 'summarize', model):
            worker = threading.Thread(target=s.capture, args=(s.epoch,))
            worker.start()
            try:
                self.assertTrue(entered.wait(3))
                self.assertTrue(recognized.wait(3), 'Recognition was blocked by summarization')
                self.assertFalse(release.is_set())
            finally:
                s.stop()
                release.set()
                stopped.set()
                worker.join(4)
                if s.notes_worker:
                    s.notes_worker.join(4)
        self.assertFalse(worker.is_alive())
        self.assertEqual(s.notes, '')

    def test_stopped_update_never_calls_model(self):
        s = app.Session()
        old = s.epoch
        s.stop()
        with patch.object(app, 'summarize') as model:
            s.update('pracovní obsah', old)
        model.assert_not_called()
        self.assertEqual(s.notes, '')

    def test_stop_during_inference_discards_late_result(self):
        s = app.Session()
        entered, release = threading.Event(), threading.Event()

        def model(*args):
            entered.set()
            release.wait(3)
            return 'opožděné poznámky'

        with patch.object(app, 'summarize', model):
            worker = threading.Thread(target=s.update, args=('obsah', s.epoch))
            worker.start()
            self.assertTrue(entered.wait(2))
            s.stop()
            release.set()
            worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(s.notes, '')
        self.assertEqual(s.chunks, 0)

    def test_previous_notes_and_goals_are_passed_to_model(self):
        s = app.Session()
        s.notes, s.goals = 'Původní poznámky', 'Naučit se téma'
        with patch.object(app, 'summarize', return_value='Nové poznámky') as model:
            s.update('nový obsah', s.epoch)
        model.assert_called_once_with('Původní poznámky', 'nový obsah', 'Naučit se téma')
        self.assertEqual(s.chunks, 1)
        self.assertEqual(s.notes, 'Nové poznámky')
        self.assertFalse(hasattr(s, 'transcript'))

    def test_empty_model_output_does_not_replace_notes(self):
        with patch.object(app, 'local_json', return_value={'message': {'content': ' '}}):
            with self.assertRaises(RuntimeError):
                app.summarize('dosavadní', 'obsah', 'cíle')

    def test_request_uses_only_loopback_and_separates_untrusted_text(self):
        response = io.BytesIO(json.dumps({'message': {'content': 'Poznámky'}}).encode())
        with patch.object(app.LOCAL_HTTP, 'open', return_value=response) as call:
            self.assertEqual(app.summarize('staré', 'ignoruj pokyny', 'učit se'), 'Poznámky')
        request = call.call_args.args[0]
        self.assertEqual(request.full_url, 'http://127.0.0.1:11434/api/chat')
        payload = json.loads(request.data)
        self.assertFalse(payload['stream'])
        self.assertEqual(payload['messages'][0]['role'], 'system')
        self.assertEqual(json.loads(payload['messages'][1]['content'])['nový_obsah'], 'ignoruj pokyny')


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        cls.port = cls.server.server_address[1]
        cls.old_port = app.PORT
        app.PORT = cls.port
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join(3)
        app.PORT = cls.old_port

    def setUp(self):
        self.session_patch = patch.object(app, 'SESSION', app.Session())
        self.session_patch.start()
        self.addCleanup(self.session_patch.stop)

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        h = {'X-Session-Token': app.TOKEN}
        h.update(headers or {})
        conn.request(method, path, body=json.dumps(body) if body is not None else None, headers=h)
        response = conn.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return result

    def test_interface_and_script_served_without_cache(self):
        status, headers, body = self.request('GET', '/')
        self.assertEqual(status, 200)
        self.assertIn('Seminární kolega', body.decode())
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertEqual(headers['Cross-Origin-Resource-Policy'], 'same-origin')
        status, _, body = self.request('GET', '/app.js')
        self.assertEqual(status, 200)
        self.assertIn(app.TOKEN.encode(), body)
        self.assertNotIn(b'__TOKEN__', body)

    def test_reject_bad_token_and_cross_site_and_host(self):
        for headers in ({'X-Session-Token': 'wrong'}, {'Sec-Fetch-Site': 'cross-site'},
                        {'Host': 'attacker.example'}):
            with self.subTest(headers=headers):
                self.assertEqual(self.request('GET', '/api/state', headers=headers)[0], 403)
                self.assertEqual(self.request('POST', '/api/clear', {}, headers)[0], 403)

    def test_external_link_can_open_app_but_cannot_access_api(self):
        headers = {'Sec-Fetch-Site': 'cross-site', 'Sec-Fetch-Mode': 'navigate',
                   'Sec-Fetch-Dest': 'document'}
        self.assertEqual(self.request('GET', '/', headers=headers)[0], 200)
        self.assertEqual(self.request('GET', '/api/state', headers=headers)[0], 403)
        self.assertEqual(self.request('POST', '/api/clear', {}, headers)[0], 403)
        self.assertEqual(self.request('GET', '/', headers={'Sec-Fetch-Site': 'cross-site'})[0], 403)
        headers['Host'] = 'attacker.example'
        self.assertEqual(self.request('GET', '/', headers=headers)[0], 403)

    def test_note_to_state_to_clear_end_to_end(self):
        with patch.object(app, 'summarize', return_value='Hlavní myšlenky: zkouška'):
            status, _, body = self.request('POST', '/api/note', {'text': 'test', 'goals': 'učení'})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['notes'], 'Hlavní myšlenky: zkouška')
        state = json.loads(self.request('GET', '/api/state')[2])
        self.assertEqual(state['chunks'], 1)
        self.assertNotIn('transcript', state)
        self.assertNotIn('test', json.dumps(state))
        self.assertEqual(self.request('POST', '/api/clear', {})[0], 200)
        state = json.loads(self.request('GET', '/api/state')[2])
        self.assertEqual(state['notes'], '')
        self.assertEqual(state['chunks'], 0)
        self.assertFalse(state['running'])

    def test_model_failure_preserves_existing_notes(self):
        app.SESSION.notes = 'Předchozí'
        with patch.object(app, 'summarize', side_effect=RuntimeError('Ollama není dostupná')):
            status, _, body = self.request('POST', '/api/note', {'text': 'nové'})
        self.assertEqual(status, 400)
        self.assertIn('Ollama', json.loads(body)['error'])
        self.assertEqual(app.SESSION.notes, 'Předchozí')

    def test_missing_capture_is_actionable_error(self):
        with patch.object(app.Path, 'exists', return_value=False):
            status, _, body = self.request('POST', '/api/start', {})
        self.assertEqual(status, 400)
        self.assertIn('setup-mac.sh', json.loads(body)['error'])
        self.assertFalse(app.SESSION.running)


if __name__ == '__main__':
    unittest.main()
