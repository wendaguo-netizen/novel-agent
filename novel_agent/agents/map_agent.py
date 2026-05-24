import json
from .base import BaseAgent
from ..models import MasterPlan, WorldContext, MapData
from ..config import REASONING_MODEL

SYSTEM = """你是一位奇幻世界的地图绘制师，专门负责构建和维护小说世界的地理数据。

【坐标系统】
- 使用0-100的二维坐标（x: 西→东，y: 北→南）
- 地点之间的相对位置必须符合地理逻辑（邻近宗门x/y差值不超过20，大陆跨度接近100）
- 重要地点尽量分布在地图中部，偏远之地放在边缘

【地点类型（type字段）】
修仙题材：宗门 / 城市 / 山脉 / 秘境 / 禁地 / 古遗迹 / 渡口 / 关隘
穿越题材：皇城 / 王府 / 城镇 / 边关 / 战场 / 山寨 / 渡口
科幻题材：星球 / 空间站 / 星港 / 军事基地 / 殖民地 / 虫洞节点

【重要性判断】
- major：已出现或必将反复出现的核心地点（主角所在地、关键势力驻地）
- minor：偶尔提及的背景地点

【连接类型（type字段）】
官道 / 秘道 / 河流 / 山脉边界 / 势力边界 / 星际航线 / 传送阵 / 古道

【职责】
1. 根据本章任务和世界观上下文，新增或更新地点信息
2. 建立或更新地点之间的地理连接
3. 保持与已有地图数据的一致性（不能随意改变已有地点的坐标）
4. 输出完整地图数据（包含所有历史地点+本章新增/更新内容）

输出严格使用以下JSON格式：
{
  "title": "世界地图名称（如：苍天大陆地图）",
  "lore": "世界地理总述（80字以内）",
  "locations": [
    {
      "id": "唯一英文标识符_下划线分隔",
      "name": "地点中文名称",
      "type": "地点类型",
      "x": 坐标数值0-100,
      "y": 坐标数值0-100,
      "description": "地点描述（30字以内）",
      "importance": "major 或 minor"
    }
  ],
  "connections": [
    {
      "from_id": "起点id",
      "to_id": "终点id",
      "type": "连接类型",
      "label": "距离或备注（可为空）"
    }
  ]
}"""


class MapAgent(BaseAgent):
    def __init__(self):
        super().__init__(model=REASONING_MODEL)

    def run(self, plan: MasterPlan, world_ctx: WorldContext,
            existing_map: dict | None) -> MapData:
        tasks_str = "\n".join(f"- {t}" for t in plan.map_tasks) if plan.map_tasks else "- 根据本章内容自动识别并添加涉及的地点"
        existing_str = json.dumps(existing_map, ensure_ascii=False, indent=2) if existing_map else "（暂无地图数据，这是第一次构建）"

        user_content = f"""【本章创作方案（总控指令）】
章节：第{plan.chapter_num}章
用户意图：{plan.user_intent}

【地图Agent任务清单】
{tasks_str}

【本章世界观上下文】
{world_ctx.summary}
涉及地点：{'; '.join(world_ctx.locations[:5])}
新元素：{'; '.join(world_ctx.new_elements[:3]) if world_ctx.new_elements else '无'}

【现有地图数据】
{existing_str}

请根据以上信息，输出完整的更新后地图数据（JSON格式）："""

        raw = self.call_with_context(SYSTEM, user_content, max_tokens=3000)
        raw = _strip_json(raw)
        data = json.loads(raw)
        return MapData(**data)


def _strip_json(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()
