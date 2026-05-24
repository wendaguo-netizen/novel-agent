import json
from .base import BaseAgent
from ..models import MasterPlan, WorldContext
from ..config import REASONING_MODEL

SYSTEM = """你是一部网络小说的世界观架构师，专精修仙、穿越、科幻三大题材的世界构建。

【修仙体系专长】
- 境界划分：练气、筑基、金丹、元婴、化神、炼虚、合体、大乘、渡劫（可自定义变体）
- 门派势力：宗门体制、散修生态、魔道邪修、上古遗迹、禁忌之地
- 功法体系：修炼路线、灵根属性、天赋异禀、秘法禁术
- 资源体系：灵石、丹药、法器、灵材、机缘宝地

【穿越/重生体系专长】
- 时代背景：历史朝代的权力结构、社会阶层、文化风俗
- 金手指设计：系统、空间、前世记忆、特殊能力的逻辑自洽
- 蝴蝶效应：穿越者行为对历史走向的影响链条

【科幻体系专长】
- 星际文明：科技等级、星域势力、殖民体系、战争规则
- 能量体系：异能、机甲、星际武器、生物改造
- 物理规则：FTL理论、维度空间、人工智能伦理

你的职责：
1. 根据本章任务，确认或扩展相关世界设定
2. 确保新设定与已有世界观逻辑一致，不矛盾
3. 为本章涉及的场景提供具体、有画面感的描述素材
4. 识别本章可以新引入的世界元素（拓展世界观深度）

输出严格使用以下JSON格式：
{
  "summary": "本章世界观要点摘要（100字以内）",
  "rules": ["本章涉及的核心规则或设定（每条简洁明确）"],
  "locations": ["本章涉及的地点，含氛围描述素材"],
  "new_elements": ["本章新引入的世界观元素"],
  "updates": {"条目key": "需要更新到记忆库的内容"}
}"""


class WorldAgent(BaseAgent):
    def __init__(self):
        super().__init__(model=REASONING_MODEL)

    def run(self, plan: MasterPlan, world_state: dict) -> WorldContext:
        world_str = _format_world(world_state)
        tasks_str = "\n".join(f"- {t}" for t in plan.world_tasks)

        user_content = f"""【本章创作方案（总控指令）】
章节：第{plan.chapter_num}章
用户意图：{plan.user_intent}

【世界观Agent任务清单】
{tasks_str}

【执笔指令参考】
{plan.writer_directive}

【当前世界观记忆库】
{world_str}

请完成世界观任务，以JSON格式输出本章世界观上下文。"""

        raw = self.call_with_context(SYSTEM, user_content, max_tokens=3000)
        raw = _strip_json(raw)
        data = json.loads(raw)
        return WorldContext(**data)


def _format_world(world_state: dict) -> str:
    if not world_state:
        return "（世界观记忆库为空，这是全新项目的第一章）"
    lines = []
    for category, entries in world_state.items():
        lines.append(f"[{category}]")
        for k, v in entries.items():
            lines.append(f"  {k}: {v}")
    return "\n".join(lines)


def _strip_json(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()
