from .base import BaseAgent
from ..config import CHAT_MODEL

SYSTEM = """你是一位专业的小说修改编辑，根据作者指令对章节进行精准的定向修改。

修改原则：
1. 精准定位——只修改作者指出的部分，其余内容保持原样
2. 风格一致——修改后的文字必须与原章节整体风格统一
3. 逻辑连贯——修改不能破坏情节的连贯性和前后因果
4. 质量提升——修改后必须优于原文，不能为改而改

常见修改类型：
- 情节调整：修改某个场景的走向或结果
- 对话改写：让某段对话更有张力或更符合人物性格
- 节奏加速：删减冗余，让某部分更紧凑
- 情绪加强：让关键情感节点更有冲击力
- 细节丰富：为某处补充感官细节或内心描写
- 结尾改写：重新设计章末悬念

请直接输出完整的修改后章节正文，不要说明你改了什么。"""


class ReviseAgent(BaseAgent):
    def __init__(self):
        super().__init__(model=CHAT_MODEL)

    def run_gen(self, original_content: str, instructions: str, style_guide: str = ""):
        style_note = f"\n\n【写作风格偏好】\n{style_guide}" if style_guide else ""
        user_content = f"""【修改指令】
{instructions}

【原章节内容】
{original_content}{style_note}

请根据修改指令，输出修改后的完整章节正文："""
        yield from self.stream_write_gen(SYSTEM, user_content, max_tokens=8192)
