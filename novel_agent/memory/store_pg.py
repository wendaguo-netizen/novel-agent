"""
Memory store — PostgreSQL backend (Supabase-compatible).
Interface is identical to the original SQLite version.
"""
import json
from contextlib import contextmanager
from typing import Optional

import psycopg2
import psycopg2.extras

from ..config import DATABASE_URL

# ── Connection helper ─────────────────────────────────────────────────────────

@contextmanager
def _conn():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _cur(conn):
    """Return a cursor that yields dicts."""
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


# ── Schema ────────────────────────────────────────────────────────────────────

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS projects (
        id BIGSERIAL PRIMARY KEY,
        name TEXT UNIQUE NOT NULL,
        genre TEXT,
        description TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS active_project (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        project_id BIGINT REFERENCES projects(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS world_entries (
        id BIGSERIAL PRIMARY KEY,
        project_id BIGINT NOT NULL REFERENCES projects(id),
        category TEXT NOT NULL,
        key TEXT NOT NULL,
        value TEXT NOT NULL,
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(project_id, category, key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS characters (
        id BIGSERIAL PRIMARY KEY,
        project_id BIGINT NOT NULL REFERENCES projects(id),
        name TEXT NOT NULL,
        profile TEXT NOT NULL,
        current_state TEXT,
        relationships TEXT DEFAULT '{}',
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(project_id, name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chapters (
        id BIGSERIAL PRIMARY KEY,
        project_id BIGINT NOT NULL REFERENCES projects(id),
        chapter_num INTEGER NOT NULL,
        title TEXT,
        content TEXT NOT NULL,
        word_count INTEGER,
        brief TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(project_id, chapter_num)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS plot_threads (
        id BIGSERIAL PRIMARY KEY,
        project_id BIGINT NOT NULL REFERENCES projects(id),
        thread_key TEXT NOT NULL,
        description TEXT NOT NULL,
        status TEXT DEFAULT 'open',
        introduced_chapter INTEGER,
        resolved_chapter INTEGER,
        UNIQUE(project_id, thread_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS notes (
        id BIGSERIAL PRIMARY KEY,
        project_id BIGINT NOT NULL REFERENCES projects(id),
        content TEXT NOT NULL,
        tags TEXT DEFAULT '[]',
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS map_data (
        project_id BIGINT PRIMARY KEY REFERENCES projects(id),
        data TEXT NOT NULL,
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS story_bible (
        project_id BIGINT PRIMARY KEY REFERENCES projects(id),
        data TEXT NOT NULL DEFAULT '{}',
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
]


class MemoryStore:
    def __init__(self):
        self._init_db()

    def _init_db(self):
        with _conn() as conn:
            cur = _cur(conn)
            for stmt in _DDL:
                cur.execute(stmt)

    # ── Projects ──────────────────────────────────────────────────────────────

    def create_project(self, name: str, genre: str = "", description: str = "") -> int:
        with _conn() as conn:
            cur = _cur(conn)
            cur.execute(
                "INSERT INTO projects (name, genre, description) VALUES (%s, %s, %s) RETURNING id",
                (name, genre, description),
            )
            return cur.fetchone()["id"]

    def list_projects(self) -> list[dict]:
        with _conn() as conn:
            cur = _cur(conn)
            cur.execute(
                "SELECT id, name, genre, description, updated_at FROM projects ORDER BY updated_at DESC"
            )
            return [dict(r) for r in cur.fetchall()]

    def get_project(self, project_id: int) -> Optional[dict]:
        with _conn() as conn:
            cur = _cur(conn)
            cur.execute("SELECT * FROM projects WHERE id = %s", (project_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def get_project_by_name(self, name: str) -> Optional[dict]:
        with _conn() as conn:
            cur = _cur(conn)
            cur.execute("SELECT * FROM projects WHERE name = %s", (name,))
            row = cur.fetchone()
            return dict(row) if row else None

    def set_active_project(self, project_id: int):
        with _conn() as conn:
            cur = _cur(conn)
            cur.execute(
                "INSERT INTO active_project (id, project_id) VALUES (1, %s) "
                "ON CONFLICT (id) DO UPDATE SET project_id = EXCLUDED.project_id",
                (project_id,),
            )

    def get_active_project_id(self) -> Optional[int]:
        with _conn() as conn:
            cur = _cur(conn)
            cur.execute("SELECT project_id FROM active_project WHERE id = 1")
            row = cur.fetchone()
            return row["project_id"] if row else None

    # ── World state ───────────────────────────────────────────────────────────

    def upsert_world_entry(self, project_id: int, category: str, key: str, value: str):
        with _conn() as conn:
            cur = _cur(conn)
            cur.execute(
                """
                INSERT INTO world_entries (project_id, category, key, value, updated_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (project_id, category, key) DO UPDATE
                SET value = EXCLUDED.value, updated_at = NOW()
                """,
                (project_id, category, key, value),
            )

    def get_world_state(self, project_id: int) -> dict[str, dict[str, str]]:
        with _conn() as conn:
            cur = _cur(conn)
            cur.execute(
                "SELECT category, key, value FROM world_entries "
                "WHERE project_id = %s ORDER BY category, key",
                (project_id,),
            )
            result: dict[str, dict[str, str]] = {}
            for r in cur.fetchall():
                result.setdefault(r["category"], {})[r["key"]] = r["value"]
            return result

    # ── Characters ────────────────────────────────────────────────────────────

    def upsert_character(self, project_id: int, name: str, profile: str,
                         current_state: str = "", relationships: dict = None):
        rels = json.dumps(relationships or {}, ensure_ascii=False)
        with _conn() as conn:
            cur = _cur(conn)
            cur.execute(
                """
                INSERT INTO characters (project_id, name, profile, current_state, relationships, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON CONFLICT (project_id, name) DO UPDATE
                SET profile = EXCLUDED.profile,
                    current_state = EXCLUDED.current_state,
                    relationships = EXCLUDED.relationships,
                    updated_at = NOW()
                """,
                (project_id, name, profile, current_state, rels),
            )

    def get_characters(self, project_id: int) -> list[dict]:
        with _conn() as conn:
            cur = _cur(conn)
            cur.execute(
                "SELECT name, profile, current_state, relationships "
                "FROM characters WHERE project_id = %s",
                (project_id,),
            )
            result = []
            for r in cur.fetchall():
                d = dict(r)
                d["relationships"] = json.loads(d["relationships"] or "{}")
                result.append(d)
            return result

    # ── Chapters ──────────────────────────────────────────────────────────────

    def save_chapter(self, project_id: int, chapter_num: int, content: str,
                     title: str = "", brief: str = ""):
        word_count = len(content)
        with _conn() as conn:
            cur = _cur(conn)
            cur.execute(
                """
                INSERT INTO chapters (project_id, chapter_num, title, content, word_count, brief)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (project_id, chapter_num) DO UPDATE
                SET title = EXCLUDED.title,
                    content = EXCLUDED.content,
                    word_count = EXCLUDED.word_count,
                    brief = EXCLUDED.brief
                """,
                (project_id, chapter_num, title, content, word_count, brief),
            )
            cur.execute(
                "UPDATE projects SET updated_at = NOW() WHERE id = %s", (project_id,)
            )

    def get_chapter(self, project_id: int, chapter_num: int) -> Optional[dict]:
        with _conn() as conn:
            cur = _cur(conn)
            cur.execute(
                "SELECT * FROM chapters WHERE project_id = %s AND chapter_num = %s",
                (project_id, chapter_num),
            )
            row = cur.fetchone()
            if not row:
                return None
            d = dict(row)
            # Convert timestamptz to string for JSON serialisation
            for k in ("created_at",):
                if d.get(k) and not isinstance(d[k], str):
                    d[k] = d[k].isoformat()
            return d

    def get_latest_chapter_num(self, project_id: int) -> int:
        with _conn() as conn:
            cur = _cur(conn)
            cur.execute(
                "SELECT MAX(chapter_num) AS n FROM chapters WHERE project_id = %s",
                (project_id,),
            )
            row = cur.fetchone()
            return row["n"] or 0

    def list_chapters(self, project_id: int) -> list[dict]:
        with _conn() as conn:
            cur = _cur(conn)
            cur.execute(
                "SELECT chapter_num, title, word_count, created_at "
                "FROM chapters WHERE project_id = %s ORDER BY chapter_num",
                (project_id,),
            )
            result = []
            for r in cur.fetchall():
                d = dict(r)
                if d.get("created_at") and not isinstance(d["created_at"], str):
                    d["created_at"] = d["created_at"].isoformat()
                result.append(d)
            return result

    # ── Plot threads ──────────────────────────────────────────────────────────

    def upsert_plot_thread(self, project_id: int, thread_key: str, description: str,
                           status: str = "open", introduced_chapter: int = None,
                           resolved_chapter: int = None):
        with _conn() as conn:
            cur = _cur(conn)
            cur.execute(
                """
                INSERT INTO plot_threads
                    (project_id, thread_key, description, status, introduced_chapter, resolved_chapter)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (project_id, thread_key) DO UPDATE
                SET description = EXCLUDED.description,
                    status = EXCLUDED.status,
                    resolved_chapter = EXCLUDED.resolved_chapter
                """,
                (project_id, thread_key, description, status, introduced_chapter, resolved_chapter),
            )

    def get_open_plot_threads(self, project_id: int) -> list[dict]:
        with _conn() as conn:
            cur = _cur(conn)
            cur.execute(
                "SELECT thread_key, description, introduced_chapter FROM plot_threads "
                "WHERE project_id = %s AND status = 'open' ORDER BY introduced_chapter",
                (project_id,),
            )
            return [dict(r) for r in cur.fetchall()]

    # ── Notes ─────────────────────────────────────────────────────────────────

    def add_note(self, project_id: int, content: str, tags: list[str] = None):
        with _conn() as conn:
            cur = _cur(conn)
            cur.execute(
                "INSERT INTO notes (project_id, content, tags) VALUES (%s, %s, %s)",
                (project_id, content, json.dumps(tags or [], ensure_ascii=False)),
            )

    def get_notes(self, project_id: int) -> list[dict]:
        with _conn() as conn:
            cur = _cur(conn)
            cur.execute(
                "SELECT content, tags, created_at FROM notes "
                "WHERE project_id = %s ORDER BY created_at DESC",
                (project_id,),
            )
            result = []
            for r in cur.fetchall():
                d = dict(r)
                d["tags"] = json.loads(d["tags"] or "[]")
                if d.get("created_at") and not isinstance(d["created_at"], str):
                    d["created_at"] = d["created_at"].isoformat()
                result.append(d)
            return result

    # ── Map data ──────────────────────────────────────────────────────────────

    def save_map_data(self, project_id: int, data: dict):
        with _conn() as conn:
            cur = _cur(conn)
            cur.execute(
                """
                INSERT INTO map_data (project_id, data, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (project_id) DO UPDATE
                SET data = EXCLUDED.data, updated_at = NOW()
                """,
                (project_id, json.dumps(data, ensure_ascii=False)),
            )

    def get_map_data(self, project_id: int) -> Optional[dict]:
        with _conn() as conn:
            cur = _cur(conn)
            cur.execute("SELECT data FROM map_data WHERE project_id = %s", (project_id,))
            row = cur.fetchone()
            return json.loads(row["data"]) if row else None

    # ── Story Bible ───────────────────────────────────────────────────────────

    def save_story_bible(self, project_id: int, data: dict):
        with _conn() as conn:
            cur = _cur(conn)
            cur.execute(
                """
                INSERT INTO story_bible (project_id, data, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (project_id) DO UPDATE
                SET data = EXCLUDED.data, updated_at = NOW()
                """,
                (project_id, json.dumps(data, ensure_ascii=False)),
            )

    def get_story_bible(self, project_id: int) -> dict:
        with _conn() as conn:
            cur = _cur(conn)
            cur.execute("SELECT data FROM story_bible WHERE project_id = %s", (project_id,))
            row = cur.fetchone()
            return json.loads(row["data"]) if row else {}
