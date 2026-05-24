from .base import BaseAgent
from ..config import REASONING_MODEL

SYSTEM = """你是一部网络小说的「创作总监」。创作者给你看他的故事圣经（人物设定、冲突、卷构思），你的任务是把它转化成一份清晰可执行的章节路线图。

你不写正文，只做规划。规划必须对网文读者有吸引力。

【网文节奏铁律】
- 每3-5章必须有一个爽点高潮章
- 每10章前后设一个大反转或新危机，推动故事进入下一阶段
- 不允许连续超过3章的平淡推进
- 每章结尾必须有悬念钩子，驱动读者点击下一章

【输出结构——严格按两层输出】

## 一、卷级叙事弧线

简述这批章节的整体走向：
- 主角经历了什么核心变化？
- 核心冲突如何演变？
- 情感基调如何起伏？
- 哪些伏笔需要在这一段埋下或收回？

## 二、章节提纲

用表格输出每章规划：

| 章节 | 章节类型 | 核心事件 | 爽点/反转设计 | 结尾悬念钩子 |
|------|---------|---------|-------------|------------|
| 第N章 | 铺垫/爽点/反转/收束 | ... | ... | ... |

章节类型说明：铺垫章（蓄力）/ 爽点章（高潮）/ 反转章（反转）/ 收束章（收线）

表格之后，单独列出：
**关键伏笔规划**
- 本段需新埋的伏笔
- 本段需推进或收回的已有伏笔

直接输出规划内容，不要加前言或说明。"""


class DirectorAgent(BaseAgent):
    def __init__(self):
        super().__init__(model=REASONING_MODEL)

    def run_gen(self, bible: dict, chapter_range: str,
                chapters_written: int, characters: list[dict],
                plot_threads: list[dict]):
        """Stream a two-layer creative plan."""
        chars_str = "\n".join(
            f"- {c['name']}：{c.get('current_state') or c.get('profile', '')[:80]}"
            for c in characters
        ) or "（尚未创建角色）"

        threads_str = "\n".join(
            f"- [{t['thread_key']}]（第{t.get('introduced_chapter', '?')}章）：{t['description']}"
            for t in plot_threads
        ) or "（暂无未解伏笔）"

        bible_text = _format_bible(bible)

        user_content = f"""【故事圣经】
{bible_text}

【当前进度】
已完成：第{chapters_written}章

【规划范围】
{chapter_range}

【现有角色状态】
{chars_str}

【未解伏笔】
{threads_str}

请按两层结构输出创作规划："""

        yield from self.stream_write_gen(SYSTEM, user_content, max_tokens=4096)


def _format_bible(bible: dict) -> str:
    parts = []
    labels = [
        ("characters", "🎭 人物设定"),
        ("conflicts",  "⚔️ 故事冲突"),
        ("volumes",    "📚 卷构思"),
        ("notes",      "📝 创作备注"),
    ]
    for key, label in labels:
        val = (bible.get(key) or "").strip()
        if val:
            parts.append(f"### {label}\n{val}")
    return "\n\n".join(parts) if parts else "（故事圣经尚未填写）"
