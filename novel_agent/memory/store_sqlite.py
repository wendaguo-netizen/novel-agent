"""
Memory store — SQLite backend (local development).
"""
import sqlite3
import json
from pathlib import Path
from typing import Optional
from ..config import DB_PATH


class MemoryStore:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    genre TEXT,
                    description TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS active_project (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    project_id INTEGER REFERENCES projects(id)
                );

                CREATE TABLE IF NOT EXISTS world_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES projects(id),
                    category TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    updated_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(project_id, category, key)
                );

                CREATE TABLE IF NOT EXISTS characters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES projects(id),
                    name TEXT NOT NULL,
                    profile TEXT NOT NULL,
                    current_state TEXT,
                    relationships TEXT DEFAULT '{}',
                    updated_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(project_id, name)
                );

                CREATE TABLE IF NOT EXISTS chapters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES projects(id),
                    chapter_num INTEGER NOT NULL,
                    title TEXT,
                    content TEXT NOT NULL,
                    word_count INTEGER,
                    brief TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(project_id, chapter_num)
                );

                CREATE TABLE IF NOT EXISTS plot_threads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES projects(id),
                    thread_key TEXT NOT NULL,
                    description TEXT NOT NULL,
                    status TEXT DEFAULT 'open',
                    introduced_chapter INTEGER,
                    resolved_chapter INTEGER,
                    UNIQUE(project_id, thread_key)
                );

                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES projects(id),
                    content TEXT NOT NULL,
                    tags TEXT DEFAULT '[]',
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS map_data (
                    project_id INTEGER PRIMARY KEY REFERENCES projects(id),
                    data TEXT NOT NULL,
                    updated_at TEXT DEFAULT (datetime('now'))
                );
            """)

    def create_project(self, name: str, genre: str = "", description: str = "") -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO projects (name, genre, description) VALUES (?, ?, ?)",
                (name, genre, description),
            )
            return cur.lastrowid

    def list_projects(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, name, genre, description, updated_at FROM projects ORDER BY updated_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_project(self, project_id: int) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            return dict(row) if row else None

    def get_project_by_name(self, name: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM projects WHERE name = ?", (name,)).fetchone()
            return dict(row) if row else None

    def set_active_project(self, project_id: int):
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO active_project (id, project_id) VALUES (1, ?)",
                (project_id,),
            )

    def get_active_project_id(self) -> Optional[int]:
        with self._conn() as conn:
            row = conn.execute("SELECT project_id FROM active_project WHERE id = 1").fetchone()
            return row["project_id"] if row else None

    def upsert_world_entry(self, project_id: int, category: str, key: str, value: str):
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO world_entries (project_id, category, key, value, updated_at)
                   VALUES (?, ?, ?, ?, datetime('now'))
                   ON CONFLICT(project_id, category, key) DO UPDATE SET
                   value=excluded.value, updated_at=excluded.updated_at""",
                (project_id, category, key, value),
            )

    def get_world_state(self, project_id: int) -> dict[str, dict[str, str]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT category, key, value FROM world_entries WHERE project_id = ? ORDER BY category, key",
                (project_id,),
            ).fetchall()
        result: dict[str, dict[str, str]] = {}
        for r in rows:
            result.setdefault(r["category"], {})[r["key"]] = r["value"]
        return result

    def upsert_character(self, project_id: int, name: str, profile: str,
                         current_state: str = "", relationships: dict = None):
        rels = json.dumps(relationships or {}, ensure_ascii=False)
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO characters (project_id, name, profile, current_state, relationships, updated_at)
                   VALUES (?, ?, ?, ?, ?, datetime('now'))
                   ON CONFLICT(project_id, name) DO UPDATE SET
                   profile=excluded.profile, current_state=excluded.current_state,
                   relationships=excluded.relationships, updated_at=excluded.updated_at""",
                (project_id, name, profile, current_state, rels),
            )

    def get_characters(self, project_id: int) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT name, profile, current_state, relationships FROM characters WHERE project_id = ?",
                (project_id,),
            ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["relationships"] = json.loads(d["relationships"])
            result.append(d)
        return result

    def save_chapter(self, project_id: int, chapter_num: int, content: str,
                     title: str = "", brief: str = ""):
        word_count = len(content)
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO chapters (project_id, chapter_num, title, content, word_count, brief)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(project_id, chapter_num) DO UPDATE SET
                   title=excluded.title, content=excluded.content,
                   word_count=excluded.word_count, brief=excluded.brief""",
                (project_id, chapter_num, title, content, word_count, brief),
            )
        with self._conn() as conn:
            conn.execute(
                "UPDATE projects SET updated_at = datetime('now') WHERE id = ?", (project_id,)
            )

    def get_chapter(self, project_id: int, chapter_num: int) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM chapters WHERE project_id = ? AND chapter_num = ?",
                (project_id, chapter_num),
            ).fetchone()
            return dict(row) if row else None

    def get_latest_chapter_num(self, project_id: int) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT MAX(chapter_num) as n FROM chapters WHERE project_id = ?", (project_id,)
            ).fetchone()
            return row["n"] or 0

    def list_chapters(self, project_id: int) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT chapter_num, title, word_count, created_at FROM chapters "
                "WHERE project_id = ? ORDER BY chapter_num",
                (project_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def upsert_plot_thread(self, project_id: int, thread_key: str, description: str,
                           status: str = "open", introduced_chapter: int = None,
                           resolved_chapter: int = None):
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO plot_threads (project_id, thread_key, description, status,
                   introduced_chapter, resolved_chapter)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(project_id, thread_key) DO UPDATE SET
                   description=excluded.description, status=excluded.status,
                   resolved_chapter=excluded.resolved_chapter""",
                (project_id, thread_key, description, status, introduced_chapter, resolved_chapter),
            )

    def get_open_plot_threads(self, project_id: int) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT thread_key, description, introduced_chapter FROM plot_threads "
                "WHERE project_id = ? AND status = 'open' ORDER BY introduced_chapter",
                (project_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def add_note(self, project_id: int, content: str, tags: list[str] = None):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO notes (project_id, content, tags) VALUES (?, ?, ?)",
                (project_id, content, json.dumps(tags or [], ensure_ascii=False)),
            )

    def get_notes(self, project_id: int) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT content, tags, created_at FROM notes WHERE project_id = ? ORDER BY created_at DESC",
                (project_id,),
            ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["tags"] = json.loads(d["tags"])
            result.append(d)
        return result

    def save_map_data(self, project_id: int, data: dict):
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO map_data (project_id, data, updated_at)
                   VALUES (?, ?, datetime('now'))
                   ON CONFLICT(project_id) DO UPDATE SET
                   data=excluded.data, updated_at=excluded.updated_at""",
                (project_id, json.dumps(data, ensure_ascii=False)),
            )

    def get_map_data(self, project_id: int) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT data FROM map_data WHERE project_id = ?", (project_id,)
            ).fetchone()
            return json.loads(row["data"]) if row else None
