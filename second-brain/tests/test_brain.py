import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from brain import Brain, CloudAI
from library import Library


class BrainTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.library = Library(Path(self.temp.name) / 'test.sqlite3')
        self.project = self.library.add_project('Můj projekt')
        self.source = self.library.add_source('Plán', 'Rozpočet projektu je 100 Kč.', self.project)
        self.passage = self.library.search('rozpočet')[0]
        self.ai = Mock()
        self.brain = Brain(self.library, self.ai)

    def test_answer_contains_exact_selected_evidence_and_validated_citation(self):
        pid = self.passage['passage_id']
        self.ai.answer.return_value = {'statements': [
            {'kind': 'fact', 'text': 'Rozpočet je 100 Kč.', 'passage_ids': [pid]}], 'follow_up': []}
        answer = self.brain.answer('Jaký je rozpočet?', [pid], self.project)
        self.assertEqual(answer['evidence'], [self.passage])
        self.ai.answer.assert_called_once_with('Jaký je rozpočet?', [self.passage])

    def test_no_evidence_does_not_call_cloud(self):
        result = self.brain.answer('Co mám dělat?', [], self.project)
        self.ai.answer.assert_not_called()
        self.assertEqual(result['statements'][0]['kind'], 'uncertain')

    def test_cross_project_evidence_is_not_sent(self):
        other = self.library.add_project('Jiný projekt')
        with self.assertRaises(ValueError):
            self.brain.answer('Rozpočet?', [self.passage['passage_id']], other)
        self.ai.answer.assert_not_called()

    def test_invented_citation_and_uncited_fact_are_rejected(self):
        pid = self.passage['passage_id']
        for ids in ([9999], [], ['1'], [True]):
            with self.subTest(ids=ids):
                self.ai.answer.return_value = {'statements': [
                    {'kind': 'fact', 'text': 'Nesprávný výstup', 'passage_ids': ids}], 'follow_up': []}
                with self.assertRaises(ValueError):
                    self.brain.answer('Rozpočet?', [pid])

    def test_prepare_can_use_selected_source_even_if_words_do_not_match(self):
        self.assertTrue(self.brain.prepare('Jak pokračovat?', self.project, [self.source]))
        self.ai.answer.assert_not_called()

    def test_selected_long_document_finds_relevant_late_passage(self):
        text = 'Obecný úvod k projektu. ' * 1500 + 'Specifický rozpočet činí 890 Kč.'
        source_id = self.library.add_source('Dlouhý dokument', text, self.project)
        evidence = self.brain.prepare('Jaký je specifický rozpočet?', self.project, [source_id])
        self.assertTrue(evidence)
        self.assertTrue(any('890 Kč' in p['text'] for p in evidence))
        self.assertTrue(all(p['source_id'] == source_id for p in evidence))

    def test_deleted_evidence_cannot_be_sent(self):
        self.library.delete_source(self.source)
        with self.assertRaises(ValueError):
            self.brain.answer('Rozpočet?', [self.passage['passage_id']])
        self.ai.answer.assert_not_called()

    def test_provider_request_does_not_include_unselected_sources(self):
        response = {'status': 'completed', 'output': [{'type': 'message', 'content': [
            {'type': 'output_text', 'text': json.dumps({'statements': [], 'follow_up': []})}]}]}
        with patch('urllib.request.urlopen', return_value=io.BytesIO(json.dumps(response).encode())) as call:
            result = CloudAI('test-only-key').answer('Dotaz', [self.passage])
        req = call.call_args.args[0]
        payload = json.loads(req.data)
        self.assertEqual(req.full_url, 'https://api.openai.com/v1/responses')
        self.assertFalse(payload['store'])
        self.assertEqual(json.loads(payload['input'])['evidence'], [self.passage])
        self.assertTrue(payload['text']['format']['strict'])
        self.assertEqual(result, {'statements': [], 'follow_up': []})

    def test_missing_api_key_has_no_network_side_effect(self):
        with patch('urllib.request.urlopen') as call:
            with self.assertRaises(ValueError):
                CloudAI('').answer('Dotaz', [self.passage])
        call.assert_not_called()


if __name__ == '__main__':
    unittest.main()
