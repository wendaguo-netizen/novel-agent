"""
Auto-selects the storage backend:
  DATABASE_URL set  →  PostgreSQL (store_pg.py)   — Vercel / production
  DATABASE_URL unset →  SQLite    (store_sqlite.py) — local development
"""
from ..config import DATABASE_URL

if DATABASE_URL:
    from .store_pg import MemoryStore  # noqa: F401
else:
    from .store_sqlite import MemoryStore  # noqa: F401
