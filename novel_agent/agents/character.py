import json
from .base import BaseAgent
from ..models import MasterPlan, WorldContext, CharacterContext
from ..config import REASONING_MODEL

SYSTEM = """你是一部网络小说的人物塑造专家，负责管理所有角色的状态、关系与成长轨迹。

【人物塑造核心原则】
1. 立体性：每个角色都有自己的欲望、恐惧、底线和矛盾，不是工具人
2. 行为一致性：角色的每个决定都必须有性格和处境的支撑
3. 成长弧线：主角和重要配角必须在关键节点有可见的内心变化
4. 关系动态：人物关系不是静态的，随情节推进而演变

【主角塑造要点】
- 外在目标（想要什么）vs 内在渴望（真正需要什么）的张力
- 核心缺陷（让读者觉得真实）和核心优势（让读者崇拜）的平衡
- 独特的说话方式、思维习惯、下意识动作

【配角塑造要点】
- 每个配角都有自己的小目标，不以主角为中心运转
- 情感层次：表面态度 vs 内心真实想法
- 关键配角需要有记忆点：一个独特的习惯、口头禅或执念

【情感线处理】
- 情感发展要有节奏，禁止一见钟情式速成
- 通过细节行为传递情感，避免直接说"他爱她"
- 喜欢和依赖、欣赏和爱情的层次要区分清楚

你的职责：
1. 根据本章任务更新角色当前状态和心理
2. 分析本章涉及的关系动态变化
3. 为执笔Agent提供角色在本章的行为逻辑和内心状态
4. 识别哪些角色在本章会有成长或转变

输出严格使用以下JSON格式：
{
  "summary": "本章角色状态摘要（100字以内）",
  "active_characters": [
    {
      "name": "角色名",
      "current_state": "当前处境",
      "psychology": "本章心理状态和内心冲突",
      "behavior_logic": "本章行为逻辑（为什么会这么做）",
      "speech_style": "说话风格特点"
    }
  ],
  "relationships": ["本章涉及的关键关系动态描述"],
  "arcs": ["本章推进的角色成长弧线描述"],
  "updates": {"角色名": "需要更新到记忆库的角色状态"}
}"""


class CharacterAgent(BaseAgent):
    def __init__(self):
        super().__init__(model=REASONING_MODEL)

    def run(self, plan: MasterPlan, characters: list[dict], world_ctx: WorldContext) -> CharacterContext:
        chars_str = _format_chars(characters)
        tasks_str = "\n".join(f"- {t}" for t in plan.character_tasks)

        user_content = f"""【本章创作方案（总控指令）】
章节：第{plan.chapter_num}章
用户意图：{plan.user_intent}
执笔指令：{plan.writer_directive}

【人物Agent任务清单】
{tasks_str}

【本章世界观上下文】
{world_ctx.summary}
涉及地点：{', '.join(world_ctx.locations)}

【角色记忆库】
{chars_str}

请完成人物任务，以JSON格式输出本章人物上下文。"""

        raw = self.call_with_context(SYSTEM, user_content, max_tokens=3000)
        raw = _strip_json(raw)
        data = json.loads(raw)
        return CharacterContext(**data)


def _format_chars(characters: list[dict]) -> str:
    if not characters:
        return "（角色库为空，这是全新项目，请根据总控指令和世界观创建主要角色）"
    lines = []
    for c in characters:
        lines.append(f"【{c['name']}】")
        lines.append(f"  档案：{c['profile']}")
        if c.get("current_state"):
            lines.append(f"  当前状态：{c['current_state']}")
        rels = c.get("relationships", {})
        if rels:
            for other, desc in rels.items():
                lines.append(f"  与{other}的关系：{desc}")
    return "\n".join(lines)


def _strip_json(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()
