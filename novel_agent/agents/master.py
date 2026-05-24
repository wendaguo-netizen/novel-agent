import json
from .base import BaseAgent
from ..models import MasterPlan
from ..config import REASONING_MODEL

SYSTEM = """你是一部网络小说的总策划兼主编，专注于修仙、穿越、科幻题材（可含情感线，严格避免现代都市题材）。

你的职责是：
1. 解析用户输入的自然语言创作简报，提取核心意图
2. 结合当前世界观状态、角色状态、未解决的情节线，制定本章的整体创作方案
3. 为世界观Agent、人物Agent、情节Agent分配具体任务
4. 为执笔Agent给出写作指令（含风格、情绪基调、叙事重点）
5. 为润色Agent指出本章需要重点打磨的维度

判断标准：
- 每章必须推进至少一条主线或支线
- 每章必须有明确的爽点（读者情绪高潮点）
- 每章结尾必须留有悬念或钩子，让读者想看下一章
- 新引入的设定必须有逻辑支撑，不能凭空出现
- 角色行为必须符合其既有性格和处境

请严格按照以下JSON格式输出，不要有任何额外说明：
{
  "task_type": "new_chapter 或 continue 或 revise",
  "chapter_num": 章节编号（整数）,
  "user_intent": "用户核心意图的精炼摘要（50字以内）",
  "world_tasks": ["需要世界观Agent确认或构建的具体设定任务"],
  "character_tasks": ["需要人物Agent处理的角色状态或关系任务"],
  "plot_tasks": ["需要情节Agent设计的具体情节结构任务"],
  "map_tasks": ["需要地图Agent新增或更新的地点/地理关系，如：新增青云宗位置、更新天魔山脉范围"],
  "writer_directive": "执笔Agent的详细写作指令，含叙事视角、情绪基调、节奏要求、禁忌事项",
  "polish_focus": ["润色Agent需要重点关注的维度，如：对话自然度、感官细节、节奏变化等"]
}"""


class MasterAgent(BaseAgent):
    def __init__(self):
        super().__init__(model=REASONING_MODEL)

    def run(self, user_brief: str, world_state: dict, characters: list[dict],
            plot_threads: list[dict], latest_chapter_num: int,
            story_summary: str = "") -> MasterPlan:
        world_summary = _format_world(world_state)
        char_summary = _format_chars(characters)
        threads_summary = _format_threads(plot_threads)

        user_content = f"""【用户创作简报】
{user_brief}

【当前世界观状态】
{world_summary}

【当前角色状态】
{char_summary}

【未解决的情节伏笔】
{threads_summary}

【当前最新章节】第{latest_chapter_num}章

{f"【历史故事记忆】{chr(10)}{story_summary}{chr(10)}{chr(10)}" if story_summary else ""}请根据以上信息，制定第{latest_chapter_num + 1}章的创作方案，以JSON格式输出。"""

        raw = self.call_with_context(SYSTEM, user_content, max_tokens=2048)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)
        return MasterPlan(**data)


def _format_world(world_state: dict) -> str:
    if not world_state:
        return "（暂无记录）"
    lines = []
    for category, entries in world_state.items():
        lines.append(f"[{category}]")
        for k, v in entries.items():
            lines.append(f"  {k}: {v}")
    return "\n".join(lines)


def _format_chars(characters: list[dict]) -> str:
    if not characters:
        return "（暂无角色）"
    lines = []
    for c in characters:
        state = c.get("current_state", "未知")
        lines.append(f"- {c['name']}：{state}")
    return "\n".join(lines)


def _format_threads(threads: list[dict]) -> str:
    if not threads:
        return "（暂无未解决伏笔）"
    lines = []
    for t in threads:
        ch = t.get("introduced_chapter", "?")
        lines.append(f"- [{t['thread_key']}]（第{ch}章埋下）：{t['description']}")
    return "\n".join(lines)
