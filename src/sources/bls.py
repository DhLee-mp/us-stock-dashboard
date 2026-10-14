"""미 노동통계국(BLS) 공공 API — 실업률, 비농업 취업자, CPI. 키 불필요(v1)."""
from __future__ import annotations

from ..net import fetch

URL = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
SERIES = {
    "unemployment": ("LNS14000000", "실업률"),
    "payrolls": ("CES0000000001", "비농업 취업자수"),
    "cpi": ("CUUR0000SA0", "소비자물가지수"),
}


def _series(series_id: str, ttl: float) -> list[dict]:
    """[{period: 'YYYY-MM', value: float}] 오래된 것 → 최근."""
    d = fetch(URL + series_id, ttl=ttl, min_interval=0.5)
    try:
        rows = d["Results"]["series"][0]["data"]
    except (TypeError, KeyError, IndexError):
        return []
    out = []
    for r in rows:
        per = r.get("period", "")
        if not per.startswith("M") or per == "M13":  # M13 = 연간 평균
            continue
        try:
            out.append({"period": f"{r['year']}-{per[1:]}", "value": float(r["value"])})
        except (KeyError, ValueError):
            pass
    out.sort(key=lambda r: r["period"])
    return out


def macro(ttl: float = 12 * 3600) -> dict:
    """고용·물가 핵심 지표와 추세."""
    un = _series(SERIES["unemployment"][0], ttl)
    pay = _series(SERIES["payrolls"][0], ttl)
    cpi = _series(SERIES["cpi"][0], ttl)
    out: dict = {}

    if un:
        vals = [r["value"] for r in un]
        low12 = min(vals[-12:])
        out["unemployment"] = {
            "period": un[-1]["period"],
            "value": vals[-1],
            # 실업률이 최근 1년 최저점 대비 얼마나 올랐는가 (경기 둔화 신호)
            "rise_from_12m_low": round(vals[-1] - low12, 2),
            "chg_3m": round(vals[-1] - vals[-4], 2) if len(vals) >= 4 else None,
            "history": un[-36:],
        }

    if len(pay) >= 4:
        vals = [r["value"] for r in pay]
        out["payrolls"] = {
            "period": pay[-1]["period"],
            "value": vals[-1],
            # 월평균 순증 (천명 단위) — 최근 3개월
            "avg_monthly_change_3m": round((vals[-1] - vals[-4]) / 3, 1),
            "history": pay[-36:],
        }

    if len(cpi) >= 13:
        vals = [r["value"] for r in cpi]
        out["cpi"] = {
            "period": cpi[-1]["period"],
            "yoy_pct": round((vals[-1] / vals[-13] - 1) * 100, 2),
            "history": cpi[-36:],
        }

    return out
