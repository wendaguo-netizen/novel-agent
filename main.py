#!/usr/bin/env python3
import typer
from typing import Optional
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

from novel_agent.memory.store import MemoryStore
from novel_agent.pipeline import run_pipeline

app = typer.Typer(
    name="novel-agent",
    help="网络小说 AI 创作助手 — 修仙 · 穿越 · 科幻",
    add_completion=False,
)
console = Console()
memory = MemoryStore()


def _require_active() -> tuple[int, dict]:
    pid = memory.get_active_project_id()
    if pid is None:
        console.print("[red]当前没有激活的项目。请先用 [bold]new[/bold] 创建项目或用 [bold]use[/bold] 切换项目。[/red]")
        raise typer.Exit(1)
    project = memory.get_project(pid)
    if project is None:
        console.print("[red]激活的项目不存在，请重新选择。[/red]")
        raise typer.Exit(1)
    return pid, project


@app.command()
def new(
    name: str = typer.Argument(..., help="项目名称"),
    genre: str = typer.Option("修仙", "--genre", "-g", help="题材类型（修仙/穿越/科幻等）"),
    description: str = typer.Option("", "--desc", "-d", help="项目简介"),
):
    """创建新的小说项目并激活。"""
    existing = memory.get_project_by_name(name)
    if existing:
        console.print(f"[yellow]项目「{name}」已存在，直接激活。[/yellow]")
        memory.set_active_project(existing["id"])
        return
    pid = memory.create_project(name, genre, description)
    memory.set_active_project(pid)
    console.print(Panel(
        f"[bold green]✓ 已创建并激活项目「{name}」[/bold green]\n"
        f"题材：{genre}\n"
        f"简介：{description or '（未填写）'}",
        title="新项目",
        expand=False,
    ))


@app.command("list")
def list_projects():
    """列出所有项目。"""
    projects = memory.list_projects()
    active_id = memory.get_active_project_id()
    if not projects:
        console.print("[dim]还没有项目。用 [bold]new <名称>[/bold] 创建第一个。[/dim]")
        return
    table = Table(title="小说项目列表", show_header=True)
    table.add_column("ID", style="dim", width=4)
    table.add_column("状态", width=4)
    table.add_column("名称", style="bold")
    table.add_column("题材")
    table.add_column("最后更新")
    for p in projects:
        active_mark = "[green]●[/green]" if p["id"] == active_id else " "
        table.add_row(str(p["id"]), active_mark, p["name"], p["genre"] or "-", p["updated_at"][:10])
    console.print(table)


@app.command()
def use(name: str = typer.Argument(..., help="项目名称")):
    """切换当前激活项目。"""
    project = memory.get_project_by_name(name)
    if not project:
        console.print(f"[red]项目「{name}」不存在。[/red]")
        raise typer.Exit(1)
    memory.set_active_project(project["id"])
    console.print(f"[green]✓ 已切换到项目「{name}」[/green]")


@app.command()
def write(
    brief: str = typer.Argument(..., help="本章创作简报（自然语言描述）"),
):
    """根据简报写作下一章。"""
    pid, project = _require_active()
    console.print(Panel(
        f"[bold]项目：{project['name']}[/bold]  题材：{project['genre']}\n"
        f"简报：{brief}",
        title="开始创作",
        expand=False,
    ))
    final = run_pipeline(pid, brief, memory)
    latest = memory.get_latest_chapter_num(pid)
    console.print(Panel(
        f"[bold green]✓ 第{latest}章创作完成，共 {len(final)} 字[/bold green]",
        title="创作完成",
        expand=False,
    ))


@app.command()
def note(content: str = typer.Argument(..., help="要记录的创作笔记")):
    """记录创作笔记。"""
    pid, project = _require_active()
    memory.add_note(pid, content)
    console.print(f"[green]✓ 已记录到项目「{project['name']}」[/green]")


@app.command()
def status():
    """查看当前项目状态。"""
    pid, project = _require_active()
    latest_num = memory.get_latest_chapter_num(pid)
    chars = memory.get_characters(pid)
    threads = memory.get_open_plot_threads(pid)
    world = memory.get_world_state(pid)
    notes = memory.get_notes(pid)

    console.print(Panel(
        f"[bold]{project['name']}[/bold]  ({project['genre']})\n"
        f"{project['description'] or ''}",
        title="当前项目",
        expand=False,
    ))

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("key", style="dim")
    table.add_column("value", style="bold")
    table.add_row("已写章节", f"{latest_num} 章")
    table.add_row("角色数量", f"{len(chars)} 个")
    table.add_row("未解伏笔", f"{len(threads)} 条")
    world_count = sum(len(v) for v in world.values())
    table.add_row("世界设定条目", f"{world_count} 条")
    table.add_row("创作笔记", f"{len(notes)} 条")
    console.print(table)

    if threads:
        console.print("\n[yellow]未解决伏笔：[/yellow]")
        for t in threads[:5]:
            console.print(f"  [dim]· [{t['thread_key']}][/dim] {t['description'][:60]}")


@app.command()
def chapter(
    num: int = typer.Argument(..., help="章节编号"),
    raw: bool = typer.Option(False, "--raw", help="输出原始文本"),
):
    """查看指定章节内容。"""
    pid, _ = _require_active()
    ch = memory.get_chapter(pid, num)
    if not ch:
        console.print(f"[red]第{num}章不存在。[/red]")
        raise typer.Exit(1)
    title = ch["title"] or f"第{num}章"
    if raw:
        print(ch["content"])
    else:
        console.print(Panel(
            ch["content"],
            title=f"[bold]{title}[/bold]  ({ch['word_count']} 字)",
            expand=False,
        ))


@app.command()
def chars():
    """查看所有角色。"""
    pid, _ = _require_active()
    characters = memory.get_characters(pid)
    if not characters:
        console.print("[dim]还没有角色记录。[/dim]")
        return
    for c in characters:
        console.print(Panel(
            f"[bold]{c['name']}[/bold]\n"
            f"档案：{c['profile']}\n"
            f"当前状态：{c.get('current_state') or '未知'}",
            expand=False,
        ))


@app.command()
def world():
    """查看世界观设定。"""
    pid, _ = _require_active()
    state = memory.get_world_state(pid)
    if not state:
        console.print("[dim]暂无世界观记录。[/dim]")
        return
    for category, entries in state.items():
        table = Table(title=f"[{category}]", show_header=True)
        table.add_column("条目", style="bold")
        table.add_column("内容")
        for k, v in entries.items():
            table.add_row(k, v[:100] + ("..." if len(v) > 100 else ""))
        console.print(table)


@app.command()
def chapters():
    """查看所有章节列表。"""
    pid, project = _require_active()
    ch_list = memory.list_chapters(pid)
    if not ch_list:
        console.print("[dim]还没有写任何章节。[/dim]")
        return
    table = Table(title=f"《{project['name']}》章节列表", show_header=True)
    table.add_column("章节", style="bold", width=6)
    table.add_column("标题")
    table.add_column("字数", width=8)
    table.add_column("日期", width=12)
    for ch in ch_list:
        table.add_row(
            f"第{ch['chapter_num']}章",
            ch["title"] or "-",
            str(ch["word_count"]),
            ch["created_at"][:10],
        )
    console.print(table)


@app.command()
def export(
    output: Optional[Path] = typer.Option(None, "--out", "-o", help="输出文件路径（默认：项目名.txt）"),
):
    """将所有章节导出为文本文件。"""
    pid, project = _require_active()
    ch_list = memory.list_chapters(pid)
    if not ch_list:
        console.print("[red]没有章节可导出。[/red]")
        raise typer.Exit(1)

    out_path = output or Path(f"{project['name']}.txt")
    lines = [f"《{project['name']}》\n\n"]
    for ch_meta in ch_list:
        ch = memory.get_chapter(pid, ch_meta["chapter_num"])
        if ch:
            title = ch["title"] or f"第{ch['chapter_num']}章"
            lines.append(f"\n\n{'='*40}\n{title}\n{'='*40}\n\n")
            lines.append(ch["content"])
    out_path.write_text("".join(lines), encoding="utf-8")
    console.print(f"[green]✓ 已导出至 {out_path}（共 {len(ch_list)} 章）[/green]")


if __name__ == "__main__":
    app()
