"""장중 준실시간 시세: 지수·섹터·추천 종목·VIX·공포탐욕 지수만 가볍게 갱신.

점수/재무지표는 하루 한 번(build)으로 충분하므로 여기서는 가격만 다룬다.
결과는 55초 동안 메모리에 캐시되어 탭을 여러 개 열어도 요청이 늘지 않는다.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo

from .build import OUT, SECTORS
from .sources import cnn, nasdaq

ET = ZoneInfo("America/New_York")
_lock = threading.Lock()
_cache: dict = {"at": 0.0, "body": None}
CACHE_SECONDS = 55


def market_status(now: dt.datetime | None = None) -> dict:
    """미국 정규장 여부 (공휴일은 고려하지 않음 — 그날은 값이 안 움직일 뿐)."""
    n = (now or dt.datetime.now(tz=ET)).astimezone(ET)
    open_t, close_t = n.replace(hour=9, minute=30, second=0, microsecond=0), n.replace(hour=16, minute=0, second=0, microsecond=0)
    is_open = n.weekday() < 5 and open_t <= n < close_t
    return {"open": is_open, "et": n.strftime("%Y-%m-%d %H:%M ET"),
            "kst": n.astimezone(ZoneInfo("Asia/Seoul")).strftime("%H:%M KST")}


def _load_symbols() -> tuple[list[str], list[tuple[str, str]], float | None]:
    """data.json에서 추천 종목·지수 목록을 읽는다."""
    try:
        with open(OUT, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return [], [], None, []
    idx = [(i["symbol"], "index") for i in d.get("indexes", []) if i["symbol"] in ("COMP", "NDX")]
    idx += [(i["symbol"], "etf") for i in d.get("indexes", []) if i["symbol"] in ("IWM", "DIA")]
    ratio = next((i.get("spy_ratio") for i in d.get("indexes", []) if i["symbol"] == "SPX"), None)
    etfs = [e["symbol"] for e in d.get("etfs", [])]
    return d.get("recommendations", []), idx, ratio, etfs


def snapshot() -> dict:
    with _lock:
        if _cache["body"] and time.time() - _cache["at"] < CACHE_SECONDS:
            return _cache["body"]
        body = _fetch()
        _cache.update(at=time.time(), body=body)
        return body


def _fetch() -> dict:
    recs, idx, ratio, etf_syms = _load_symbols()
    jobs = [("SPY", "etf")] + idx + [(etf, "etf") for etf, _ in SECTORS] + [(s, "stocks") for s in recs]
    jobs += [(s, "etf") for s in etf_syms if s not in {j[0] for j in jobs}]
    # 응답이 건당 1~3초라 병렬로 받는다 (호스트별 최소 간격은 net.fetch가 지킨다)
    with ThreadPoolExecutor(max_workers=8) as ex:
        quotes = dict(zip([j[0] for j in jobs], ex.map(lambda j: nasdaq.quote(j[0], j[1], ttl=0) or {}, jobs)))

    indexes: dict[str, dict] = {}
    spy = quotes.get("SPY", {})
    if spy.get("price") and ratio:
        indexes["SPX"] = {"price": spy["price"] * ratio, "change_pct": spy.get("change_pct")}
    for sym, _ in idx:
        r = quotes.get(sym, {})
        if r.get("price") is not None:
            indexes[sym] = {"price": r["price"], "change_pct": r.get("change_pct")}

    sectors = {etf: quotes[etf]["change_pct"] for etf, _ in SECTORS
               if quotes.get(etf, {}).get("change_pct") is not None}
    stocks = {s: {"price": quotes[s]["price"], "change_pct": quotes[s].get("change_pct")}
              for s in recs if quotes.get(s, {}).get("price") is not None}
    etfs = {s: {"price": quotes[s]["price"], "change_pct": quotes[s].get("change_pct")}
            for s in etf_syms if quotes.get(s, {}).get("price") is not None}

    c = cnn.snapshot(ttl=0) or {}
    if c.get("vix") is not None:
        vs = c.get("vix_series") or []
        prev = next((p["v"] for p in reversed(vs[:-1]) if p["v"] != c["vix"]), None)
        indexes["VIX"] = {"price": c["vix"], "change_pct": (c["vix"] / prev - 1) * 100 if prev else None}

    return {
        "at": dt.datetime.now().isoformat(timespec="seconds"),
        "market": market_status(),
        "indexes": indexes, "sectors": sectors, "stocks": stocks, "etfs": etfs,
        "fng": {"score": c.get("score"), "rating": c.get("rating")} if c.get("score") is not None else None,
        "data_generated_at": _data_generated_at(),
    }


def _data_generated_at() -> str | None:
    try:
        return dt.datetime.fromtimestamp(os.path.getmtime(OUT)).isoformat(timespec="seconds")
    except OSError:
        return None
