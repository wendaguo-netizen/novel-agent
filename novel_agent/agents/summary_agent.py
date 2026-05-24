from .base import BaseAgent
from ..config import REASONING_MODEL

SYSTEM = """你是小说历史记录员，负责将已写章节提炼成精准的故事记忆，供后续章节创作使用。

要求：
- 客观记录已发生的事件，绝不预测未来情节
- 重点保留：主线进展、角色状态、重要揭示、待解悬念
- 每项文字精炼，不超过3句
- 严格按照指定格式输出，不要有多余的说明

输出格式（直接输出，无前言）：
【主线进展】（到第N章）
...

【角色动态】
角色名：当前状态和位置
...

【重要揭示】
已揭示的关键信息或秘密（若无则写"暂无"）

【待解悬念】
读者和角色都知道但尚未解决的问题

【整体基调】
故事当前的情绪氛围（一句话）"""


class SummaryAgent(BaseAgent):
    def __init__(self):
        super().__init__(model=REASONING_MODEL)

    def run(self, project_id: int, memory) -> str:
        from ..memory.store import MemoryStore
        chapters = memory.list_chapters(project_id)
        if not chapters:
            return ""

        chapter_texts = []
        for meta in chapters[-6:]:
            ch = memory.get_chapter(project_id, meta["chapter_num"])
            if ch:
                preview = ch["content"][:600] + "……" if len(ch["content"]) > 600 else ch["content"]
                chapter_texts.append(
                    f"第{meta['chapter_num']}章（简报：{ch.get('brief','无')}）\n{preview}"
                )

        chars = memory.get_characters(project_id)
        threads = memory.get_open_plot_threads(project_id)
        chars_str = "\n".join(f"- {c['name']}：{c.get('current_state','未知')}" for c in chars) or "（暂无）"
        threads_str = "\n".join(f"- {t['thread_key']}：{t['description']}" for t in threads) or "（暂无）"
        latest_num = chapters[-1]["chapter_num"]

        user_content = f"""【已写章节数】{len(chapters)} 章（最新：第{latest_num}章）

【最近章节节选】
{"---\n".join(chapter_texts)}

【当前角色状态】
{chars_str}

【当前未解伏笔】
{threads_str}

请生成到第{latest_num}章的故事记忆摘要："""

        return self.call_with_context(SYSTEM, user_content, max_tokens=1500)
