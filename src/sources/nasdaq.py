"""Nasdaq 공개 데이터 API (키 불필요).

제공: 종목 시세/과거주가, 4개년 재무제표, 애널리스트 목표주가 컨센서스,
미국 전체 상장 종목 스크리너.
"""
from __future__ import annotations

import re

from ..net import fetch

BASE = "https://api.nasdaq.com/api"
_HDRS = {"Origin": "https://www.nasdaq.com", "Referer": "https://www.nasdaq.com/"}
DAY = 24 * 3600


def _num(s) -> float | None:
    """'$416,161,000' / '-$12,715' / '46.9%' / '--' → float 또는 None."""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    t = str(s).strip()
    if t in ("", "--", "N/A", "NA", "null"):
        return None
    neg = t.startswith("(") and t.endswith(")")
    t = re.sub(r"[()$,%\s]", "", t)
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


def _get(path: str, params: dict | None = None, ttl: float = DAY) -> dict | None:
    d = fetch(f"{BASE}/{path}", params=params, headers=_HDRS, ttl=ttl, min_interval=0.3)
    if not isinstance(d, dict):
        return None
    return d.get("data") or None


# ---------------------------------------------------------------- 시세

def quote(symbol: str, asset: str = "stocks", ttl: float = 3600) -> dict | None:
    """현재가/변동률. asset: stocks | etf | index"""
    d = _get(f"quote/{symbol}/info", {"assetclass": asset}, ttl)
    if not d:
        return None
    p = d.get("primaryData") or {}
    return {
        "symbol": d.get("symbol"),
        "name": d.get("companyName"),
        "price": _num(p.get("lastSalePrice")),
        "change": _num(p.get("netChange")),
        "change_pct": _num(p.get("percentageChange")),
    }


def history(symbol: str, asset: str, frm: str, to: str, ttl: float = DAY) -> list[dict]:
    """일별 종가 리스트(오래된 날짜 → 최근 날짜)."""
    d = _get(f"quote/{symbol}/historical",
             {"assetclass": asset, "fromdate": frm, "todate": to, "limit": 9999}, ttl)
    rows = ((d or {}).get("tradesTable") or {}).get("rows") or []
    out = []
    for r in rows:
        c = _num(r.get("close"))
        if c is not None:
            out.append({"date": r.get("date"), "close": c})
    out.reverse()  # API는 최신순으로 준다
    return out


# ---------------------------------------------------------------- 기업 정보

def summary(symbol: str, ttl: float = DAY) -> dict:
    """섹터/산업/시가총액/52주 범위/배당 등."""
    d = _get(f"quote/{symbol}/summary", {"assetclass": "stocks"}, ttl) or {}
    sd = d.get("summaryData") or {}
    val = lambda k: (sd.get(k) or {}).get("value")
    hi_lo = val("FiftTwoWeekHighLow") or ""
    hi, lo = (hi_lo.split("/") + ["", ""])[:2]
    return {
        "sector": val("Sector"),
        "industry": val("Industry"),
        "market_cap": _num(val("MarketCap")),
        "one_year_target": _num(val("OneYrTarget")),
        "prev_close": _num(val("PreviousClose")),
        "week52_high": _num(hi),
        "week52_low": _num(lo),
        "dividend_yield": _num(val("Yield")),
    }


def _statement(table: dict | None) -> dict[str, list[float | None]]:
    """재무제표 테이블 → {항목명: [최근기, 그 전기, ...]} (단위: 달러)."""
    out: dict[str, list[float | None]] = {}
    if not table:
        return out
    cols = [k for k in ("value2", "value3", "value4", "value5", "value6")
            if k in (table.get("headers") or {})]
    for row in table.get("rows") or []:
        label = (row.get("value1") or "").strip()
        if not label:
            continue
        vals = [_num(row.get(c)) for c in cols]
        if any(v is not None for v in vals):
            # Nasdaq은 재무제표를 '천 달러' 단위로 제공한다.
            out[label] = [None if v is None else v * 1000 for v in vals]
    return out


def financials(symbol: str, annual: bool = True, ttl: float = 3 * DAY) -> dict:
    """손익/재무상태/현금흐름 + 기간 라벨."""
    d = _get(f"company/{symbol}/financials", {"frequency": 1 if annual else 2}, ttl) or {}
    headers = (d.get("incomeStatementTable") or {}).get("headers") or {}
    periods = [headers[k] for k in ("value2", "value3", "value4", "value5", "value6") if k in headers]
    return {
        "periods": periods,
        "income": _statement(d.get("incomeStatementTable")),
        "balance": _statement(d.get("balanceSheetTable")),
        "cashflow": _statement(d.get("cashFlowTable")),
    }


def price_target(symbol: str, ttl: float = DAY) -> dict | None:
    """월가 애널리스트 목표주가 컨센서스."""
    d = _get(f"analyst/{symbol}/targetprice", ttl=ttl)
    c = (d or {}).get("consensusOverview") or {}
    mean = _num(c.get("priceTarget"))
    if mean is None:
        return None
    buy, hold, sell = (_num(c.get(k)) or 0 for k in ("buy", "hold", "sell"))
    n = buy + hold + sell
    return {
        "mean": mean,
        "low": _num(c.get("lowPriceTarget")),
        "high": _num(c.get("highPriceTarget")),
        "buy": int(buy), "hold": int(hold), "sell": int(sell),
        "analysts": int(n),
        "buy_ratio": (buy / n) if n else None,
    }


# ---------------------------------------------------------------- 유니버스

# 보통주가 아닌 증권(우선주·예탁증서·워런트·유닛·채권형)은 분석 대상에서 뺀다
_NOT_COMMON = ("PREFERRED", "DEPOSITARY SHARE", "WARRANT", " UNIT", "RIGHTS", "NOTES DUE",
               "DEBENTURE", "% NOTES", "SUBORDINATED", "TRUST PREFERRED")

def screener(ttl: float = DAY) -> list[dict]:
    """미국 상장 전체 종목 (심볼/이름/가격/시가총액)."""
    d = _get("screener/stocks", {"tableonly": "true", "limit": 10000, "offset": 0,
                                 "download": "true"}, ttl)
    rows = ((d or {}).get("table") or {}).get("rows") or (d or {}).get("rows") or []
    out = []
    for r in rows:
        sym = (r.get("symbol") or "").strip()
        mc = _num(r.get("marketCap"))
        # 우선주/워런트/유닛(예: BRK/A, ABC^D)은 제외
        if not sym or not mc or any(ch in sym for ch in "^/. "):
            continue
        name_u = (r.get("name") or "").upper()
        if any(w in name_u for w in _NOT_COMMON):
            continue
        out.append({
            "symbol": sym,
            "name": (r.get("name") or "").strip(),
            "price": _num(r.get("lastsale")),
            "change_pct": _num(r.get("pctchange")),
            "market_cap": mc,
        })
    out.sort(key=lambda x: -x["market_cap"])
    return out
