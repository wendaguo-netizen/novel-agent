from pydantic import BaseModel, Field
from typing import Optional


class MasterPlan(BaseModel):
    task_type: str = Field(description="任务类型: new_chapter / continue / revise")
    chapter_num: int = Field(description="章节编号")
    user_intent: str = Field(description="用户核心意图摘要")
    world_tasks: list[str] = Field(description="世界观Agent需要处理的任务列表")
    character_tasks: list[str] = Field(description="人物Agent需要处理的任务列表")
    plot_tasks: list[str] = Field(description="情节Agent需要处理的任务列表")
    map_tasks: list[str] = Field(default_factory=list, description="地图Agent需要新增或更新的地点/地理关系任务")
    writer_directive: str = Field(description="执笔Agent的写作指令，含风格、重点和约束")
    polish_focus: list[str] = Field(description="润色Agent需要重点关注的维度")


class WorldContext(BaseModel):
    summary: str = Field(description="本章世界观要点摘要")
    rules: list[str] = Field(description="本章涉及的核心规则或设定")
    locations: list[str] = Field(description="本章涉及的地点描述")
    new_elements: list[str] = Field(description="本章新引入的世界观元素")
    updates: dict[str, str] = Field(default_factory=dict, description="需要更新到记忆库的世界观条目")


class CharacterContext(BaseModel):
    summary: str = Field(description="本章角色状态摘要")
    active_characters: list[dict] = Field(description="本章活跃角色的当前状态和心理")
    relationships: list[str] = Field(description="本章涉及的关键关系动态")
    arcs: list[str] = Field(description="本章推进的角色成长弧线")
    updates: dict[str, str] = Field(default_factory=dict, description="需要更新到记忆库的角色条目")


class MapLocation(BaseModel):
    id: str = Field(description="唯一标识符（英文下划线）")
    name: str = Field(description="地点名称")
    type: str = Field(description="类型：宗门/城市/山脉/秘境/禁地/河流/关隘/星球/空间站等")
    x: float = Field(description="横坐标 0-100（西→东）")
    y: float = Field(description="纵坐标 0-100（北→南）")
    description: str = Field(description="地点描述")
    importance: str = Field(default="minor", description="重要性：major / minor")


class MapConnection(BaseModel):
    from_id: str
    to_id: str
    type: str = Field(description="连接类型：官道/秘道/河流/边界/航线等")
    label: str = Field(default="", description="距离或备注")


class MapData(BaseModel):
    title: str = Field(default="世界地图")
    lore: str = Field(default="", description="世界地理总述")
    locations: list[MapLocation] = Field(default_factory=list)
    connections: list[MapConnection] = Field(default_factory=list)


class PlotOutline(BaseModel):
    summary: str = Field(description="本章情节梗概")
    opening_hook: str = Field(description="开头钩子设计，200字以内")
    structure: list[dict] = Field(description="章节结构，每段含scene/purpose/爽点/字数目标")
    climax: str = Field(description="本章小高潮设计")
    ending_cliffhanger: str = Field(description="结尾悬念或反转")
    foreshadowing: list[str] = Field(description="本章埋下的伏笔")
    resolved_threads: list[str] = Field(description="本章解决的历史伏笔")
    pacing_notes: str = Field(description="节奏控制说明")
