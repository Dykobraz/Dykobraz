from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from library import Library


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'brain.sqlite3'
        self.lib = Library(self.path)

    def test_persists_sources_and_returns_exact_evidence_after_restart(self):
        text = 'Příští seminář bude věnován rozhodování a řízení projektu.'
        source_id = self.lib.add_source('Seminář', text)
        reopened = Library(self.path)
        found = reopened.search('rozhodovani')
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['source_id'], source_id)
        self.assertEqual(found[0]['text'], text[found[0]['start']:found[0]['end']])
        self.assertEqual(reopened.source(source_id)['body'], text)

    def test_project_scope_does_not_mix_evidence(self):
        a, b = self.lib.add_project('Projekt A'), self.lib.add_project('Projekt B')
        self.lib.add_source('A', 'Rozpočet projektu: 100 Kč.', a)
        self.lib.add_source('B', 'Rozpočet projektu: 500 Kč.', b)
        self.assertEqual([r['title'] for r in self.lib.search('rozpocet', a)], ['A'])

    def test_missing_evidence_is_empty_not_an_invented_answer(self):
        self.lib.add_source('Poznámka', 'Dnes jsme plánovali projekt.')
        self.assertEqual(self.lib.search('astrofyzika'), [])

    def test_deletion_removes_search_results_and_source(self):
        sid = self.lib.add_source('Zkouška', 'Přednáška o plánování.')
        self.lib.delete_source(sid)
        self.assertEqual(self.lib.search('planovani'), [])
        with self.assertRaises(KeyError):
            self.lib.source(sid)

    def test_long_sources_are_covered_and_citations_are_exact(self):
        text = ('Příprava projektu má několik kroků. ' * 300) + 'Unikátní závěr.'
        sid = self.lib.add_source('Dlouhý text', text)
        self.assertEqual(self.lib.source(sid)['body'], text)
        found = self.lib.search('Unikátní')
        self.assertTrue(found)
        for passage in found:
            self.assertEqual(passage['text'], text[passage['start']:passage['end']])

    def test_fts_operators_are_treated_as_user_text(self):
        self.lib.add_source('Test', 'Projekt se připravuje.')
        for question in ['" OR * NOT (', "'; DROP TABLE sources; --", '', '项目']:
            self.lib.search(question)
        self.assertEqual(len(self.lib.sources()), 1)

    def test_reimport_is_idempotent_and_export_preserves_content(self):
        a = self.lib.add_source('Zdroj', 'Původní přesný text.')
        b = self.lib.add_source('Zdroj', 'Původní přesný text.')
        self.assertEqual(a, b)
        self.assertEqual(self.lib.export_markdown(a), '# Zdroj\n\nPůvodní přesný text.\n')

    def test_unknown_project_does_not_create_orphaned_source(self):
        with self.assertRaises(ValueError):
            self.lib.add_source('Test', 'Obsah', 999)
        self.assertEqual(self.lib.sources(), [])

    def test_deleted_citation_ids_are_never_reassigned_to_another_source(self):
        old_source = self.lib.add_source('Starý', 'Rozhodnutí o projektu.')
        old_passage = self.lib.search('Rozhodnutí')[0]['passage_id']
        self.lib.delete_source(old_source)
        new_source = self.lib.add_source('Nový', 'Rozhodnutí o jiné věci.')
        new_passage = self.lib.search('Rozhodnutí')[0]['passage_id']
        self.assertNotEqual(old_source, new_source)
        self.assertNotEqual(old_passage, new_passage)


if __name__ == '__main__':
    unittest.main()
