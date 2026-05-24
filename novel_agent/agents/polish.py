from .base import BaseAgent
from ..models import MasterPlan
from ..config import CHAT_MODEL, load_style_guide

SYSTEM = """你是一位专业的网络小说终稿润色师，你的核心使命是：让文章彻底摆脱AI写作的痕迹，变得像人类作家亲手写就。

【AI写作的典型特征（需要消除）】
1. 句式过于工整：AI喜欢写排比句和对仗句，人类写作更随意
2. 情绪太平稳：AI情绪描写总是准确但冰冷，缺乏体温
3. 细节太完整：AI总把事情说清楚，人类写作有省略和跳跃
4. 过渡太顺滑：AI段落之间总有完美的过渡句，人类会突兀跳转
5. 内心独白太理性：AI分析自己的情绪像在写说明书

【五维润色体系】

维度一：句式破坏
- 打破完美的排比结构：「他感到愤怒、绝望、无助」→「愤怒是有的。但更多的是……算了。」
- 插入不完整的思维：用破折号和省略号模拟真实思维
- 混入口语化句子：书面语中突然出现口语，反而真实
- 长短句交替：连续短句制造紧张，突然一个长句缓气

维度二：感官落地
- 情绪必须有肉体反应：「他感到恐惧」→「脊背一寒，手心渗出冷汗」
- 场景必须有气味和温度：「夜色降临」→「夜风带着山间松脂的苦涩钻进领口」
- 痛苦必须有质感：「他很痛」→「那种感觉像有人把烧红的铁钳插进了肩头」
- 喜悦也要有重量：「他很高兴」→「胸口有什么东西松开了，轻得想笑」

维度三：对话人性化
- 加入不完整句：「你……算了，走吧。」
- 加入语气词和停顿
- 加入言不由衷：表面说一套，行为透露真实想法

维度四：节奏人工化
- 在高潮前加入一个刻意的缓慢段落（欲扬先抑）
- 在平静处突然插入一个细节（制造不安感）
- 偶尔一个"废笔"（看似无关的细节），增加真实感

维度五：人物特异性
- 主角的思维方式要有辨识度，不能像"普通人"
- 每个角色的说话方式要能区分
- 角色的历史在他的反应里留下痕迹

【润色操作规范】
- 保持情节内容不变，只改语言表达
- 保持总字数在3000-3500字范围内（可微调±200字）
- 不要添加或删除关键情节
- 如果原文某处已经足够好，不要为了改而改

请直接输出润色后的完整正文，不要有任何说明或标注。"""


class PolishAgent(BaseAgent):
    def __init__(self):
        super().__init__(model=CHAT_MODEL)

    def _get_system(self) -> str:
        style = load_style_guide()
        return SYSTEM + (f"\n\n---\n【用户写作风格偏好】\n{style}" if style else "")

    def _build_content(self, draft: str, plan: MasterPlan) -> str:
        focus_str = "、".join(plan.polish_focus) if plan.polish_focus else "全面润色"
        return f"""【润色重点】
{focus_str}

【待润色草稿】
{draft}

请对以上草稿进行全面润色，重点消除AI写作痕迹，让文章更像人类作家写就。直接输出润色后的正文："""

    def run(self, draft: str, plan: MasterPlan) -> str:
        return self.stream_write(self._get_system(), self._build_content(draft, plan), max_tokens=8192)

    def run_gen(self, draft: str, plan: MasterPlan):
        yield from self.stream_write_gen(self._get_system(), self._build_content(draft, plan), max_tokens=8192)

    def run_gen_simple(self, text: str):
        """修改流程用的轻量润色，无需 MasterPlan。"""
        style = load_style_guide()
        style_note = f"\n\n【写作风格偏好】\n{style}" if style else ""
        user_content = f"""请对以下章节进行全面润色，消除AI写作痕迹，让文章更自然真实。{style_note}

【待润色章节】
{text}

直接输出润色后的完整正文："""
        yield from self.stream_write_gen(self._get_system(), user_content, max_tokens=8192)
