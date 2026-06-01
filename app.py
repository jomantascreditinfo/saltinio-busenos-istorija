import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

NO_CACHE = {"Cache-Control": "no-cache, no-store, must-revalidate"}

from db import get_history_48h, get_latest, init_db, save_results
from monitor import run_checks

INTERVAL = 300  # 5 min


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    task = asyncio.create_task(_monitoring_loop())
    yield
    task.cancel()


async def _monitoring_loop() -> None:
    while True:
        results = await run_checks()
        await save_results(results)
        await asyncio.sleep(INTERVAL)


app = FastAPI(title="RC Monitor", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse("static/index.html", headers=NO_CACHE)


@app.get("/api/status")
async def api_status():
    return JSONResponse(content=await get_latest(), headers=NO_CACHE)


@app.get("/api/history")
async def api_history():
    return JSONResponse(content=await get_history_48h(), headers=NO_CACHE)
