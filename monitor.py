import asyncio
import httpx
from dataclasses import dataclass


@dataclass
class Register:
    name: str
    url: str
    expect: str | None = None


REGISTERS: list[Register] = [
    Register("Centre of Registers",    "https://ws.registrucentras.lt/broker/index.php?wsdl",                                        expect="definitions"),
    Register("PRDB Q1",                "https://api.creditinfo.lt/v1/bol/query-one/person"),
    Register("SODRA",                  "https://new.infobankas.lt/creditinfogroup_lt/saisws/sodrainfo.asmx?wsdl",                    expect="definitions"),
    Register("Wanted persons registry","https://new.infobankas.lt/creditinfogroup_lt/SAIS/WebServices/ieskomuasmenudb.asmx?wsdl",    expect="definitions"),
]


@dataclass
class Result:
    name: str
    up: bool
    http_code: int | None = None
    error: str | None = None


async def check_one(client: httpx.AsyncClient, reg: Register) -> Result:
    try:
        r = await client.get(reg.url, timeout=10, follow_redirects=True)
        if r.status_code >= 500:
            return Result(reg.name, False, r.status_code)
        if reg.expect and reg.expect not in r.text:
            return Result(reg.name, False, r.status_code, "unexpected content")
        return Result(reg.name, True, r.status_code)
    except httpx.TimeoutException:
        return Result(reg.name, False, error="timeout")
    except httpx.ConnectError:
        return Result(reg.name, False, error="unreachable")


async def run_checks() -> list[Result]:
    async with httpx.AsyncClient() as client:
        return list(await asyncio.gather(*[check_one(client, r) for r in REGISTERS]))
