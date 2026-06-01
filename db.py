import aiosqlite
from datetime import datetime, timezone, timedelta
from pathlib import Path

from monitor import Result, REGISTERS

DB_PATH = Path(__file__).parent / "rc_monitor.db"


CURRENT_NAMES = {r.name for r in REGISTERS}


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS checks (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                ts        TEXT    NOT NULL,
                name      TEXT    NOT NULL,
                up        INTEGER NOT NULL,
                http_code INTEGER,
                error     TEXT
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_ts   ON checks(ts)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_name ON checks(name)")
        # Išvalo senus registrų įrašus kurių nėra dabartiniame sąraše
        placeholders = ",".join("?" * len(CURRENT_NAMES))
        await db.execute(
            f"DELETE FROM checks WHERE name NOT IN ({placeholders})",
            list(CURRENT_NAMES),
        )
        await db.commit()


async def save_results(results: list[Result]) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executemany(
            "INSERT INTO checks (ts, name, up, http_code, error) VALUES (?,?,?,?,?)",
            [(ts, r.name, int(r.up), r.http_code, r.error) for r in results],
        )
        await db.commit()


async def get_latest() -> list[dict]:
    placeholders = ",".join("?" * len(CURRENT_NAMES))
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(f"""
            SELECT c.name, c.up, c.http_code, c.error, c.ts
            FROM checks c
            INNER JOIN (
                SELECT name, MAX(ts) AS max_ts FROM checks GROUP BY name
            ) latest ON c.name = latest.name AND c.ts = latest.max_ts
            WHERE c.name IN ({placeholders})
            ORDER BY c.name
        """, list(CURRENT_NAMES)) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_history_48h() -> dict:
    now = datetime.now(timezone.utc)
    slots = [
        (now - timedelta(hours=47 - i)).strftime("%Y-%m-%dT%H:00")
        for i in range(48)
    ]

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT
                name,
                strftime('%Y-%m-%dT%H:00', ts) AS hour,
                ROUND(AVG(up) * 100, 1)        AS pct
            FROM checks
            WHERE ts >= datetime('now', '-48 hours')
            GROUP BY name, hour
        """) as cur:
            rows = [dict(r) for r in await cur.fetchall()]

    by_name: dict[str, dict[str, float]] = {}
    for r in rows:
        by_name.setdefault(r["name"], {})[r["hour"]] = r["pct"]

    return {
        "slots": slots,
        "registers": {
            reg.name: [by_name.get(reg.name, {}).get(slot) for slot in slots]
            for reg in REGISTERS
        },
    }
