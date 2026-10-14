"""미 재무부 일별 국채 수익률 곡선 (공식 자료, 키 불필요).

금리 정책 판단의 근거: 10년물 수준/방향, 10년-2년 장단기 스프레드,
3개월물(정책금리 대리 지표)의 방향.
"""
from __future__ import annotations

import datetime as dt
import xml.etree.ElementTree as ET

from ..net import fetch

URL = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
NS = {"a": "http://www.w3.org/2005/Atom",
      "m": "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"}

TENORS = {"BC_3MONTH": "3M", "BC_6MONTH": "6M", "BC_1YEAR": "1Y", "BC_2YEAR": "2Y",
          "BC_5YEAR": "5Y", "BC_10YEAR": "10Y", "BC_30YEAR": "30Y"}


def _year(year: int, ttl: float) -> list[dict]:
    xml = fetch(URL, params={"data": "daily_treasury_yield_curve",
                             "field_tdr_date_value": str(year)},
                kind="text", ttl=ttl, min_interval=0.5)
    if not xml:
        return []
    try:
        root = ET.fromstring(xml.encode("utf-8"))
    except ET.ParseError:
        return []

    out = []
    for entry in root.findall("a:entry", NS):
        props = entry.find("a:content/m:properties", NS)
        if props is None:
            continue
        row: dict = {}
        for child in props:
            tag = child.tag.split("}")[-1]
            if tag == "NEW_DATE" and child.text:
                row["date"] = child.text[:10]
            elif tag in TENORS and child.text:
                try:
                    row[TENORS[tag]] = float(child.text)
                except ValueError:
                    pass
        if row.get("date") and row.get("10Y") is not None:
            out.append(row)
    out.sort(key=lambda r: r["date"])
    return out


def curve(ttl: float = 6 * 3600) -> dict:
    """최근 2년치 수익률 곡선 이력 + 최신 스냅샷."""
    today = dt.date.today()
    rows = _year(today.year - 1, ttl=30 * 24 * 3600) + _year(today.year, ttl=ttl)
    if not rows:
        return {}

    latest = rows[-1]

    def ago(days: int, tenor: str) -> float | None:
        """대략 days 거래일 전 값 (영업일 ≈ 21일/월)."""
        idx = len(rows) - 1 - days
        return rows[idx].get(tenor) if idx >= 0 else None

    y10, y2, m3 = latest.get("10Y"), latest.get("2Y"), latest.get("3M")
    return {
        "date": latest["date"],
        "latest": {k: latest.get(k) for k in TENORS.values()},
        "spread_10y_2y": None if (y10 is None or y2 is None) else round(y10 - y2, 2),
        "y10": y10, "y2": y2, "m3": m3,
        "y10_chg_3m": None if (y10 is None or ago(63, "10Y") is None) else round(y10 - ago(63, "10Y"), 2),
        "m3_chg_3m": None if (m3 is None or ago(63, "3M") is None) else round(m3 - ago(63, "3M"), 2),
        "m3_chg_6m": None if (m3 is None or ago(126, "3M") is None) else round(m3 - ago(126, "3M"), 2),
        "history": [{"date": r["date"], "y10": r.get("10Y"), "y2": r.get("2Y"), "m3": r.get("3M")}
                    for r in rows[-500:]],
    }
