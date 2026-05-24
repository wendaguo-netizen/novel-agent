from rich.console import Console
from rich.panel import Panel

from .memory.store import MemoryStore
from .agents.master import MasterAgent
from .agents.world import WorldAgent
from .agents.character import CharacterAgent
from .agents.plot import PlotAgent
from .agents.map_agent import MapAgent
from .agents.summary_agent import SummaryAgent
from .agents.writer import WriterAgent
from .agents.polish import PolishAgent

console = Console()


def run_pipeline_gen(project_id: int, user_brief: str, memory: MemoryStore):
    """Generator pipeline — yields (event_type, data) tuples for web UI."""
    master = MasterAgent()
    world_agent = WorldAgent()
    char_agent = CharacterAgent()
    plot_agent = PlotAgent()
    map_agent = MapAgent()
    summary_agent = SummaryAgent()
    writer = WriterAgent()
    polish = PolishAgent()

    world_state = memory.get_world_state(project_id)
    characters = memory.get_characters(project_id)
    plot_threads = memory.get_open_plot_threads(project_id)
    latest_num = memory.get_latest_chapter_num(project_id)
    existing_map = memory.get_map_data(project_id)
    story_bible = memory.get_story_bible(project_id)
    prev_chapter = ""
    if latest_num > 0:
        row = memory.get_chapter(project_id, latest_num)
        prev_chapter = row["content"] if row else ""

    # Stage 1: Master
    yield "status", {"msg": "总控Agent 正在解析创作指令...", "stage": 1}
    plan = master.run(user_brief, world_state, characters, plot_threads, latest_num,
                      story_bible=story_bible)
    yield "plan", {
        "chapter_num": plan.chapter_num,
        "user_intent": plan.user_intent,
        "task_type": plan.task_type,
    }

    # Stage 2: World
    yield "status", {"msg": "世界观Agent 构建本章世界设定...", "stage": 2}
    world_ctx = world_agent.run(plan, world_state)
    yield "world", {
        "summary": world_ctx.summary,
        "new_elements": world_ctx.new_elements,
    }

    # Stage 3: Character
    yield "status", {"msg": "人物Agent 分析角色状态...", "stage": 3}
    char_ctx = char_agent.run(plan, characters, world_ctx)
    yield "chars", {
        "summary": char_ctx.summary,
        "active": [c["name"] for c in char_ctx.active_characters],
    }

    # Stage 4: Plot
    yield "status", {"msg": "情节Agent 设计章节结构...", "stage": 4}
    plot_outline = plot_agent.run(plan, world_ctx, char_ctx, plot_threads, prev_chapter)
    yield "plot", {
        "summary": plot_outline.summary,
        "scene_count": len(plot_outline.structure),
        "opening_hook": plot_outline.opening_hook[:80],
    }

    # Stage 5: Map
    yield "status", {"msg": "地图Agent 更新世界地图...", "stage": 5}
    map_data = map_agent.run(plan, world_ctx, existing_map)
    map_dict = map_data.model_dump()
    memory.save_map_data(project_id, map_dict)
    yield "map", {
        "location_count": len(map_data.locations),
        "title": map_data.title,
    }

    # Stage 6: Writer (streaming)
    # Generate story summary for chapters > 1 to maintain long-term continuity
    story_summary = ""
    if latest_num > 0:
        try:
            story_summary = summary_agent.run(project_id, memory)
        except Exception:
            story_summary = ""

    yield "status", {"msg": "执笔Agent 开始写作...", "stage": 6}
    yield "draft_start", {}
    draft_chunks = []
    for chunk in writer.run_gen(plan, world_ctx, char_ctx, plot_outline, prev_chapter, story_summary):
        draft_chunks.append(chunk)
        yield "draft_chunk", {"text": chunk}
    draft = "".join(draft_chunks)
    yield "draft_end", {"word_count": len(draft)}

    # Stage 7: Polish (streaming)
    yield "status", {"msg": "润色Agent 消除AI写作痕迹...", "stage": 7}
    yield "polish_start", {}
    polish_chunks = []
    for chunk in polish.run_gen(draft, plan):
        polish_chunks.append(chunk)
        yield "polish_chunk", {"text": chunk}
    final = "".join(polish_chunks)
    yield "polish_end", {"word_count": len(final)}

    _update_memory(project_id, plan, world_ctx, char_ctx, plot_outline, final, memory)
    yield "done", {"chapter_num": plan.chapter_num, "word_count": len(final)}


def run_pipeline(project_id: int, user_brief: str, memory: MemoryStore) -> str:
    """CLI pipeline — prints progress to console."""
    polish_buf = []
    in_draft = False
    in_polish = False

    for event_type, data in run_pipeline_gen(project_id, user_brief, memory):
        if event_type == "status":
            console.print(f"\n[bold cyan]{data['msg']}[/bold cyan]")
        elif event_type == "plan":
            console.print(f"[green]→ 第{data['chapter_num']}章  {data['user_intent']}[/green]")
        elif event_type == "world":
            console.print(f"[green]→ 世界观：{data['summary'][:60]}[/green]")
        elif event_type == "chars":
            console.print(f"[green]→ 角色：{', '.join(data['active'])}[/green]")
        elif event_type == "plot":
            console.print(f"[green]→ 情节：{data['summary'][:60]}[/green]")
        elif event_type == "map":
            console.print(f"[green]→ 地图：{data['title']}，共{data['location_count']}个地点[/green]")
        elif event_type == "draft_start":
            in_draft = True
            console.print("[dim](草稿实时输出)[/dim]\n")
        elif event_type == "draft_chunk" and in_draft:
            print(data["text"], end="", flush=True)
        elif event_type == "draft_end":
            in_draft = False
            print()
            console.print(f"\n[green]✓ 草稿完成：{data['word_count']} 字[/green]")
        elif event_type == "polish_start":
            in_polish = True
            console.print("[dim](润色实时输出)[/dim]\n")
        elif event_type == "polish_chunk" and in_polish:
            print(data["text"], end="", flush=True)
            polish_buf.append(data["text"])
        elif event_type == "polish_end":
            in_polish = False
            print()
            console.print(f"\n[green]✓ 润色完成：{data['word_count']} 字[/green]")
        elif event_type == "done":
            console.print(Panel(
                f"[bold green]第{data['chapter_num']}章完成，共 {data['word_count']} 字[/bold green]",
                expand=False,
            ))

    return "".join(polish_buf)


def _update_memory(project_id, plan, world_ctx, char_ctx, plot_outline, final_text, memory):
    for key, value in world_ctx.updates.items():
        parts = key.split(".", 1)
        category = parts[0] if len(parts) == 2 else "general"
        entry_key = parts[1] if len(parts) == 2 else key
        memory.upsert_world_entry(project_id, category, entry_key, value)

    for char_data in char_ctx.active_characters:
        name = char_data.get("name", "")
        if not name:
            continue
        state = char_ctx.updates.get(name, char_data.get("current_state", ""))
        existing = [c for c in memory.get_characters(project_id) if c["name"] == name]
        profile = existing[0]["profile"] if existing else f"{name}（第{plan.chapter_num}章登场）"
        memory.upsert_character(project_id, name, profile, state)

    for i, thread_desc in enumerate(plot_outline.foreshadowing):
        key = f"ch{plan.chapter_num}_foreshadow_{i+1}"
        memory.upsert_plot_thread(project_id, key, thread_desc, "open", plan.chapter_num)

    for thread_key in plot_outline.resolved_threads:
        memory.upsert_plot_thread(project_id, thread_key, "", "resolved",
                                   resolved_chapter=plan.chapter_num)

    memory.save_chapter(project_id, plan.chapter_num, final_text, brief=plan.user_intent)
