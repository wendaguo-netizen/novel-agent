import json
from .base import BaseAgent
from ..models import MasterPlan, WorldContext, CharacterContext, PlotOutline
from ..config import REASONING_MODEL

SYSTEM = """你是一部网络小说的情节设计师，精通网络小说的叙事节奏和爽感设计。

【网文情节设计铁律】
1. 钩子法则：每章开头必须在300字内抛出一个让读者无法停下的钩子（危机、悬念、反转、利益冲突）
2. 爽点设计：每500-800字必须有一个情绪高潮点（打脸、逆袭、升级、情感爆发）
3. 结尾悬念：章末必须留下一个让读者抓狂的悬念或反转，驱动点击下一章
4. 起承转合：章节内部结构必须完整，但结局必须开放

【节奏控制】
- 快节奏段落：战斗、追逐、冲突 — 短句为主，动词密集
- 慢节奏段落：心理活动、环境描写、情感铺垫 — 可用长句，注重细节
- 快慢交替，避免连续超过800字的慢节奏

【伏笔艺术】
- 埋伏笔时要自然，读者第一遍不会注意，回头看恍然大悟
- 每章至少埋1个新伏笔，至少尝试解决1个已有伏笔
- 伏笔密度：主线伏笔长线布局，支线伏笔快速回收

【爽点类型库】
- 实力碾压型：主角实力被严重低估，然后一招制敌
- 打脸打脸型：反派/小人在高光时刻被主角狠狠打脸
- 逆风翻盘型：最绝望的时刻，主角找到破局之道
- 情感爆发型：压抑已久的情感在关键节点突破
- 秘密揭示型：一个让所有人震惊的真相浮出水面
- 实力突破型：主角在极限状态下突破境界或领悟绝技

【禁止事项】
- 禁止连续超过3段的纯说教或背景铺垫
- 禁止角色为了推进情节而做出不符合性格的蠢事
- 禁止爽点来得太廉价（必须有足够的积累和铺垫）

你的职责：
1. 设计本章的整体情节结构（分场景）
2. 明确每个场景的爽点类型和触发条件
3. 设计本章的开头钩子和结尾悬念
4. 规划新伏笔的布局和已有伏笔的推进或收回

输出严格使用以下JSON格式：
{
  "summary": "本章情节梗概（150字以内）",
  "opening_hook": "开头钩子设计，包含具体场景和冲突点（200字以内）",
  "structure": [
    {
      "scene": "场景名称",
      "purpose": "场景作用",
      "爽点": "爽点设计（若有）",
      "字数目标": 字数整数
    }
  ],
  "climax": "本章小高潮的具体设计（150字以内）",
  "ending_cliffhanger": "结尾悬念或反转的具体设计（100字以内）",
  "foreshadowing": ["本章新埋下的伏笔描述"],
  "resolved_threads": ["本章解决或推进的历史伏笔key"],
  "pacing_notes": "节奏控制说明（快慢如何交替，哪些地方需要特别注意）"
}"""


class PlotAgent(BaseAgent):
    def __init__(self):
        super().__init__(model=REASONING_MODEL)

    def run(self, plan: MasterPlan, world_ctx: WorldContext, char_ctx: CharacterContext,
            plot_threads: list[dict], prev_chapter_content: str) -> PlotOutline:
        tasks_str = "\n".join(f"- {t}" for t in plan.plot_tasks)
        threads_str = _format_threads(plot_threads)
        prev_summary = prev_chapter_content[-800:] if prev_chapter_content else "（这是第一章）"

        user_content = f"""【本章创作方案（总控指令）】
章节：第{plan.chapter_num}章
用户意图：{plan.user_intent}
执笔指令：{plan.writer_directive}

【情节Agent任务清单】
{tasks_str}

【本章世界观上下文】
{world_ctx.summary}
核心规则：{'; '.join(world_ctx.rules[:5])}

【本章人物状态】
{char_ctx.summary}
活跃角色：{', '.join(c['name'] for c in char_ctx.active_characters)}

【未解决的情节伏笔】
{threads_str}

【上章结尾（最后800字）】
{prev_summary}

请设计本章情节结构，以JSON格式输出。目标字数：3000-3500字。"""

        raw = self.call_with_context(SYSTEM, user_content, max_tokens=3000)
        raw = _strip_json(raw)
        data = json.loads(raw)
        return PlotOutline(**data)


def _format_threads(threads: list[dict]) -> str:
    if not threads:
        return "（暂无未解决伏笔）"
    return "\n".join(f"- [{t['thread_key']}]（第{t.get('introduced_chapter','?')}章）：{t['description']}" for t in threads)


def _strip_json(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()
