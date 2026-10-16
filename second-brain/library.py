"""Persistent local sources and exact passages; no AI or network calls."""
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
import sqlite3


class Library:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
                CREATE TABLE IF NOT EXISTS sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
                    body TEXT NOT NULL, created_at TEXT NOT NULL,
                    project_id INTEGER REFERENCES projects(id), digest TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS passages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
                    start INTEGER NOT NULL, end INTEGER NOT NULL, text TEXT NOT NULL);
                CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
                    text, content=passages, content_rowid=id,
                    tokenize='unicode61 remove_diacritics 2');
                CREATE TRIGGER IF NOT EXISTS passage_insert AFTER INSERT ON passages BEGIN
                    INSERT INTO search_index(rowid, text) VALUES(new.id, new.text);
                END;
                CREATE TRIGGER IF NOT EXISTS passage_delete AFTER DELETE ON passages BEGIN
                    INSERT INTO search_index(search_index, rowid, text)
                    VALUES('delete', old.id, old.text);
                END;
            ''')

    def connect(self):
        # Connection lifetime must be explicit: SQLite's context manager alone
        # commits transactions, but does not close the underlying connection.
        class Connection:
            def __enter__(inner):
                inner.db = sqlite3.connect(self.path, timeout=10)
                inner.db.row_factory = sqlite3.Row
                inner.db.execute('PRAGMA foreign_keys=ON')
                return inner.db

            def __exit__(inner, *error):
                try:
                    inner.db.__exit__(*error)
                finally:
                    inner.db.close()

        return Connection()

    def add_project(self, name):
        name = name.strip()
        if not name or len(name) > 120:
            raise ValueError('Název projektu musí mít 1–120 znaků.')
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO projects(name) VALUES (?)', (name,))
            return db.execute('SELECT id FROM projects WHERE name=?', (name,)).fetchone()['id']

    def projects(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM projects ORDER BY name')]

    def add_source(self, title, body, project_id=None):
        title = title.strip()
        if not title or len(title) > 240:
            raise ValueError('Název zdroje musí mít 1–240 znaků.')
        if not body.strip() or len(body) > 500_000:
            raise ValueError('Zdroj musí obsahovat text, nejvýše 500 000 znaků.')
        digest = hashlib.sha256(body.encode()).hexdigest()
        with self.connect() as db:
            if project_id is not None and not db.execute(
                    'SELECT id FROM projects WHERE id=?', (project_id,)).fetchone():
                raise ValueError('Projekt neexistuje.')
            existing = db.execute('SELECT id FROM sources WHERE title=? AND digest=? '
                                  'AND project_id IS ?', (title, digest, project_id)).fetchone()
            if existing:
                return existing['id']
            cursor = db.execute('INSERT INTO sources(title,body,created_at,project_id,digest) '
                                'VALUES(?,?,?,?,?)',
                                (title, body, datetime.now(timezone.utc).isoformat(), project_id, digest))
            source_id = cursor.lastrowid
            start = 0
            while start < len(body):
                end = min(start + 1400, len(body))
                if end < len(body):
                    boundary = body.rfind(' ', start + 900, end)
                    if boundary > start:
                        end = boundary
                db.execute('INSERT INTO passages(source_id,start,end,text) VALUES(?,?,?,?)',
                           (source_id, start, end, body[start:end]))
                if end == len(body):
                    break
                start = end - 200
            return source_id

    def sources(self, project_id=None):
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                'SELECT id,title,created_at,project_id,length(body) AS characters FROM sources '
                'WHERE (? IS NULL OR project_id=?) ORDER BY id DESC', (project_id, project_id))]

    def source(self, source_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM sources WHERE id=?', (source_id,)).fetchone()
            if row is None:
                raise KeyError('Zdroj neexistuje.')
            return dict(row)

    def delete_source(self, source_id):
        with self.connect() as db:
            db.execute('DELETE FROM sources WHERE id=?', (source_id,))

    def search(self, question, project_id=None, limit=6):
        words = list(dict.fromkeys(re.findall(r'[^\W_]+', question, re.UNICODE)))[:24]
        if not words:
            return []
        query = ' OR '.join('"' + word + '"' for word in words)
        with self.connect() as db:
            rows = db.execute('''SELECT passages.id AS passage_id, source_id, title,
                start, end, passages.text, sources.project_id FROM search_index
                JOIN passages ON passages.id=search_index.rowid
                JOIN sources ON sources.id=passages.source_id
                WHERE search_index MATCH ? AND (? IS NULL OR sources.project_id=?)
                ORDER BY bm25(search_index), passages.id LIMIT ?''',
                (query, project_id, project_id, min(max(int(limit), 1), 20)))
            return [dict(row) for row in rows]

    def export_markdown(self, source_id):
        source = self.source(source_id)
        return f"# {source['title']}\n\n{source['body']}\n"
