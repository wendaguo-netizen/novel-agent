import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

CHAT_MODEL = "deepseek-chat"          # 执笔、润色、修改——创作型
REASONING_MODEL = "deepseek-reasoner" # 总控、世界观、人物、情节、地图、摘要——推理型
MODEL = CHAT_MODEL                     # 默认兜底

# PostgreSQL (Supabase) — set DATABASE_URL in env for production
DATABASE_URL = os.getenv("DATABASE_URL", "")

# SQLite fallback — used locally when DATABASE_URL is not set
DB_PATH = Path.home() / ".novel-agent" / "memory.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_style_path = Path(__file__).parent / "style.md"


def load_style_guide() -> str:
    """每次调用从磁盘读取，支持热更新（无需重启服务）。"""
    if _style_path.exists():
        return _style_path.read_text(encoding="utf-8").strip()
    return ""
