from .base import BaseAgent
from ..models import MasterPlan, WorldContext, CharacterContext, PlotOutline
from ..config import CHAT_MODEL, load_style_guide

SYSTEM = """你是一位顶级网络小说执笔作家，文风细腻而有力度，擅长把大纲化为鲜活的故事。

【写作铁则】
1. 开篇必须在300字内制造张力，让读者无法放下
2. 每500-800字设置一个情绪落差（高潮或转折），避免读者疲劳
3. 章节结尾必须是悬念句或反转句，不能以平淡状态收尾
4. 目标字数：3000-3500汉字

【叙事技巧】
- 视角一致性：全程保持叙事视角（第一人称/第三人称限知），不随意切换
- 展示而非说教：用具体行为和细节展示人物性格，不用"他是个善良的人"
- 感官叙事：用视觉、听觉、嗅觉、触觉、味觉让场景立体起来
- 对话推进：对话不只是传递信息，更要展示人物关系和内心

【句子层面要求】
- 句子长度变化：短句制造张力，长句营造氛围，交替使用
- 动词要有力：用"猛地抓住"而不是"抓住了"
- 细节要具体：用"那件洗得发白的青色道袍"而不是"一件旧道袍"
- 对话要有个性：每个角色说话方式不同，听声知人

【内心独白技巧】
- 碎片化处理：用破折号和省略号模拟真实思维流
- 不要大段分析：内心想法要简短、凌乱、有情绪
- 好的内心独白：「活该——他们活该——但为什么手还是在抖……」
- 避免：「他心想，这件事情确实让他感到非常愤怒，因为……」

【对话写作规范】
- 对话后要有动作或神态描写，不要连续三段纯对话
- 对话可以有打断、欲言又止、言不由衷
- 通过语气词、停顿展示情绪：「我……没事。」比「我没事。」更真实

【禁忌清单】
× 禁止出现总结性段落（"就这样，他们……"）
× 禁止连续超过3段的背景说明
× 禁止角色说出不符合其身份和处境的话
× 禁止用"忽然"、"突然"超过2次
× 禁止结尾用平静收场（必须有悬念钩子）

请直接输出正文内容，不要有任何说明、前言或标注。"""


class WriterAgent(BaseAgent):
    def __init__(self):
        super().__init__(model=CHAT_MODEL)

    def _get_system(self) -> str:
        style = load_style_guide()
        return SYSTEM + (f"\n\n---\n【用户写作风格偏好】\n{style}" if style else "")

    def _build_content(self, plan: MasterPlan, world_ctx: WorldContext,
                       char_ctx: CharacterContext, plot_outline: PlotOutline,
                       prev_chapter_content: str, story_summary: str = "") -> str:
        char_details = _format_active_chars(char_ctx)
        prev_tail = prev_chapter_content[-500:] if prev_chapter_content else ""
        structure_str = _format_structure(plot_outline)

        return f"""【写作指令】
{plan.writer_directive}

【本章情节大纲】
开头钩子：{plot_outline.opening_hook}

场景结构：
{structure_str}

小高潮：{plot_outline.climax}
结尾悬念：{plot_outline.ending_cliffhanger}

节奏说明：{plot_outline.pacing_notes}

【世界观素材】
{world_ctx.summary}
地点氛围：{'; '.join(world_ctx.locations[:3])}
本章涉及规则：{'; '.join(world_ctx.rules[:3])}

【角色素材】
{char_details}

【上章结尾衔接】
{prev_tail if prev_tail else '（第一章，无前文）'}

【需要埋入的伏笔】
{'; '.join(plot_outline.foreshadowing) if plot_outline.foreshadowing else '无'}

{f"【历史故事记忆（保持一致性）】{chr(10)}{story_summary}{chr(10)}" if story_summary else ""}现在请直接开始写作，目标3000-3500字，不要有任何前言或说明："""

    def run(self, plan, world_ctx, char_ctx, plot_outline, prev_chapter_content,
            story_summary: str = "") -> str:
        content = self._build_content(plan, world_ctx, char_ctx, plot_outline,
                                      prev_chapter_content, story_summary)
        return self.stream_write(self._get_system(), content, max_tokens=8192)

    def run_gen(self, plan, world_ctx, char_ctx, plot_outline, prev_chapter_content,
                story_summary: str = ""):
        content = self._build_content(plan, world_ctx, char_ctx, plot_outline,
                                      prev_chapter_content, story_summary)
        yield from self.stream_write_gen(self._get_system(), content, max_tokens=8192)


def _format_active_chars(char_ctx: CharacterContext) -> str:
    lines = []
    for c in char_ctx.active_characters:
        lines.append(f"【{c['name']}】")
        lines.append(f"  处境：{c.get('current_state', '')}")
        lines.append(f"  心理：{c.get('psychology', '')}")
        lines.append(f"  行为逻辑：{c.get('behavior_logic', '')}")
        if c.get('speech_style'):
            lines.append(f"  说话风格：{c['speech_style']}")
    return "\n".join(lines)


def _format_structure(outline: PlotOutline) -> str:
    lines = []
    for i, scene in enumerate(outline.structure, 1):
        lines.append(f"{i}. {scene.get('scene', '')}（目标{scene.get('字数目标', '')}字）")
        lines.append(f"   作用：{scene.get('purpose', '')}")
        if scene.get('爽点'):
            lines.append(f"   爽点：{scene['爽点']}")
    return "\n".join(lines)
