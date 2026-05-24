import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from novel_agent.memory.store import MemoryStore
from novel_agent.pipeline import run_pipeline_gen
from novel_agent.agents.revise_agent import ReviseAgent
from novel_agent.config import load_style_guide

app = FastAPI(title="网络小说 AI 创作助手")
memory = MemoryStore()
executor = ThreadPoolExecutor(max_workers=4)

# Static files — directory resolved relative to this file so it works everywhere
import pathlib
_static_dir = pathlib.Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.get("/")
def index():
    return FileResponse(str(_static_dir / "index.html"))


# ── Projects ──────────────────────────────────────────────────────────────────

@app.get("/api/projects")
def list_projects():
    projects = memory.list_projects()
    active_id = memory.get_active_project_id()
    for p in projects:
        p["active"] = p["id"] == active_id
    return projects


class ProjectCreate(BaseModel):
    name: str
    genre: str = "修仙"
    description: str = ""


@app.post("/api/projects")
def create_project(data: ProjectCreate):
    existing = memory.get_project_by_name(data.name)
    if existing:
        memory.set_active_project(existing["id"])
        existing["active"] = True
        return existing
    pid = memory.create_project(data.name, data.genre, data.description)
    memory.set_active_project(pid)
    project = memory.get_project(pid)
    project["active"] = True
    return project


@app.post("/api/projects/{project_id}/activate")
def activate_project(project_id: int):
    if not memory.get_project(project_id):
        raise HTTPException(404, "项目不存在")
    memory.set_active_project(project_id)
    return {"ok": True}


@app.get("/api/projects/{project_id}/status")
def project_status(project_id: int):
    project = memory.get_project(project_id)
    if not project:
        raise HTTPException(404)
    return {
        "project": project,
        "chapter_count": memory.get_latest_chapter_num(project_id),
        "character_count": len(memory.get_characters(project_id)),
        "thread_count": len(memory.get_open_plot_threads(project_id)),
        "world_count": sum(len(v) for v in memory.get_world_state(project_id).values()),
        "note_count": len(memory.get_notes(project_id)),
    }


# ── Chapters ──────────────────────────────────────────────────────────────────

@app.get("/api/projects/{project_id}/chapters")
def list_chapters(project_id: int):
    return memory.list_chapters(project_id)


@app.get("/api/projects/{project_id}/chapters/{num}")
def get_chapter(project_id: int, num: int):
    ch = memory.get_chapter(project_id, num)
    if not ch:
        raise HTTPException(404)
    return ch


# ── Characters / World / Threads / Notes ──────────────────────────────────────

@app.get("/api/projects/{project_id}/characters")
def get_characters(project_id: int):
    return memory.get_characters(project_id)


@app.get("/api/projects/{project_id}/world")
def get_world(project_id: int):
    return memory.get_world_state(project_id)


@app.get("/api/projects/{project_id}/threads")
def get_threads(project_id: int):
    return memory.get_open_plot_threads(project_id)


@app.get("/api/projects/{project_id}/map")
def get_map(project_id: int):
    data = memory.get_map_data(project_id)
    return data or {}


@app.get("/api/projects/{project_id}/notes")
def get_notes(project_id: int):
    return memory.get_notes(project_id)


class NoteCreate(BaseModel):
    content: str


@app.post("/api/projects/{project_id}/notes")
def add_note(project_id: int, data: NoteCreate):
    memory.add_note(project_id, data.content)
    return {"ok": True}


# ── Chapter update (save revised content) ────────────────────────────────────

class ChapterUpdate(BaseModel):
    content: str


@app.put("/api/projects/{project_id}/chapters/{num}")
def update_chapter(project_id: int, num: int, data: ChapterUpdate):
    ch = memory.get_chapter(project_id, num)
    if not ch:
        raise HTTPException(404, "章节不存在")
    memory.save_chapter(project_id, num, data.content,
                        title=ch.get("title", ""), brief=ch.get("brief", ""))
    return {"ok": True, "word_count": len(data.content)}


# ── SSE Streaming Write ────────────────────────────────────────────────────────

@app.get("/api/projects/{project_id}/write/stream")
async def write_stream(project_id: int, brief: str = Query(...)):
    if not memory.get_project(project_id):
        raise HTTPException(404, "项目不存在")

    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def sync_run():
        try:
            for event_type, data in run_pipeline_gen(project_id, brief, memory):
                asyncio.run_coroutine_threadsafe(queue.put((event_type, data)), loop)
        except Exception as e:
            asyncio.run_coroutine_threadsafe(queue.put(("error", {"msg": str(e)})), loop)
        finally:
            asyncio.run_coroutine_threadsafe(queue.put(None), loop)

    loop.run_in_executor(executor, sync_run)

    async def event_gen():
        yield "event: ping\ndata: {}\n\n"
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=180.0)
            except asyncio.TimeoutError:
                yield 'event: error\ndata: {"msg": "请求超时"}\n\n'
                return
            if item is None:
                yield "event: end\ndata: {}\n\n"
                return
            event_type, data = item
            payload = json.dumps(data, ensure_ascii=False)
            yield f"event: {event_type}\ndata: {payload}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── SSE Streaming Revise ──────────────────────────────────────────────────────

@app.get("/api/projects/{project_id}/chapters/{num}/revise/stream")
async def revise_stream(project_id: int, num: int, instructions: str = Query(...)):
    ch = memory.get_chapter(project_id, num)
    if not ch:
        raise HTTPException(404, "章节不存在")

    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def sync_run():
        try:
            agent = ReviseAgent()
            style = load_style_guide()
            for chunk in agent.run_gen(ch["content"], instructions, style):
                asyncio.run_coroutine_threadsafe(
                    queue.put(("chunk", chunk)), loop
                )
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                queue.put(("error", str(e))), loop
            )
        finally:
            asyncio.run_coroutine_threadsafe(queue.put(None), loop)

    loop.run_in_executor(executor, sync_run)

    async def event_gen():
        yield "event: ping\ndata: {}\n\n"
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=180.0)
            except asyncio.TimeoutError:
                yield 'event: error\ndata: {"msg":"请求超时"}\n\n'
                return
            if item is None:
                yield "event: end\ndata: {}\n\n"
                return
            kind, payload = item
            if kind == "chunk":
                yield f"event: chunk\ndata: {json.dumps({'text': payload}, ensure_ascii=False)}\n\n"
            else:
                yield f"event: error\ndata: {json.dumps({'msg': payload}, ensure_ascii=False)}\n\n"
                return

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── Export ────────────────────────────────────────────────────────────────────

@app.get("/api/projects/{project_id}/export")
def export_project(project_id: int):
    project = memory.get_project(project_id)
    if not project:
        raise HTTPException(404)
    ch_list = memory.list_chapters(project_id)
    lines = [f"《{project['name']}》\n\n"]
    for meta in ch_list:
        ch = memory.get_chapter(project_id, meta["chapter_num"])
        if ch:
            title = ch["title"] or f"第{ch['chapter_num']}章"
            lines.append(f"\n\n{'='*40}\n{title}\n{'='*40}\n\n{ch['content']}")
    content = "".join(lines)
    return StreamingResponse(
        iter([content.encode("utf-8")]),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{project["name"]}.txt"'},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8765, reload=True)
