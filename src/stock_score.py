"""종목 점수 (0~100) 와 추천 종목 선정.

각 지표를 분석 대상 종목 전체 안에서 백분위(0~100)로 바꾼 뒤 7개 영역으로 묶어
가중 평균한다. 자료가 없는 지표는 50(중립)으로 두고, 영역 전체가 비면 가중치를 줄인다.
시장 점수에 따라 가중치를 살짝 바꾼다(약세장일수록 재무 안정·현금흐름 중시).
"""
from __future__ import annotations

from bisect import bisect_left

FINANCE = {"Finance", "Real Estate"}

AREAS = [
    ("value", "가치", "지금 가격이 이익·현금흐름 대비 싼가 (PER, P/FCF, PEG)"),
    ("growth", "성장", "매출과 이익이 꾸준히 늘고 있는가"),
    ("safety", "재무 안정", "빚이 적고 단기 지급 능력이 충분한가"),
    ("cashflow", "현금흐름", "장부상 이익이 실제 현금으로 들어오는가"),
    ("analyst", "월가 목표주가", "애널리스트 목표가까지 여유가 있고 매수 의견이 많은가"),
    ("momentum", "주가 흐름", "최근 6개월 주가가 건강하게 오르고 있는가"),
    ("guru", "거장 보유", "버핏·테퍼 등 거장이 들고 있는가"),
]

BASE_W = {"value": 20, "growth": 20, "safety": 15, "cashflow": 15, "analyst": 15, "momentum": 10, "guru": 5}
BEAR_W = {"value": 20, "growth": 12, "safety": 22, "cashflow": 20, "analyst": 13, "momentum": 5, "guru": 8}
BULL_W = {"value": 15, "growth": 25, "safety": 10, "cashflow": 12, "analyst": 15, "momentum": 18, "guru": 5}


class _Pct:
    """지표별 백분위 계산기."""

    def __init__(self, stocks: list[dict]):
        self.sorted: dict[str, list[float]] = {}
        for s in stocks:
            for k, v in s.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    self.sorted.setdefault(k, []).append(float(v))
        for k in self.sorted:
            self.sorted[k].sort()

    def rank(self, key: str, v: float | None, higher_is_better: bool = True) -> float | None:
        arr = self.sorted.get(key)
        if v is None or not arr or len(arr) < 5:
            return None
        p = bisect_left(arr, v) / len(arr) * 100
        return p if higher_is_better else 100 - p


def _avg(vals: list[float | None]) -> float | None:
    v = [x for x in vals if x is not None]
    return sum(v) / len(v) if v else None


def _weights(market_score: int) -> dict:
    if market_score < 40:
        return BEAR_W
    if market_score >= 70:
        return BULL_W
    return BASE_W


def _fmt_pct(x, nd=0):
    return "–" if x is None else f"{x*100:+.{nd}f}%"


def score_all(stocks: list[dict], gurus: list[dict], market_score: int) -> list[dict]:
    pct = _Pct(stocks)
    w = _weights(market_score)

    # 거장 보유 맵: ticker → [(인물, 행동)]
    held: dict[str, list[tuple[str, str]]] = {}
    for g in gurus:
        for r in g["top"] + g["new_buys"] + g["added"]:
            if r.get("ticker"):
                lst = held.setdefault(r["ticker"], [])
                if not any(p == g["person"] for p, _ in lst):
                    lst.append((g["person"], r["action"]))

    for s in stocks:
        fin = (s.get("sector") in FINANCE)
        areas: dict[str, float | None] = {}

        # 가치: 낮을수록 좋음. PER이 없는(적자) 회사는 가치 점수 15.
        if s.get("per") is None:
            areas["value"] = 15.0
        else:
            areas["value"] = _avg([pct.rank("per", s["per"], False),
                                   pct.rank("p_fcf", s.get("p_fcf"), False),
                                   pct.rank("peg", s.get("peg"), False)])

        areas["growth"] = _avg([pct.rank("rev_cagr3", s.get("rev_cagr3")),
                                pct.rank("rev_growth", s.get("rev_growth")),
                                pct.rank("ni_cagr3", s.get("ni_cagr3")),
                                pct.rank("eps_growth", s.get("eps_growth"))])

        if fin:  # 금융사는 부채비율·유동비율이 의미가 다르다 → ROE·흑자 여부로 대체
            areas["safety"] = _avg([pct.rank("roe", s.get("roe")), 60.0 if (s.get("net_income") or 0) > 0 else 20.0])
        else:
            areas["safety"] = _avg([pct.rank("debt_to_equity", s.get("debt_to_equity"), False),
                                    pct.rank("current_ratio", s.get("current_ratio")),
                                    pct.rank("net_debt_to_fcf", s.get("net_debt_to_fcf"), False)])

        if fin:
            areas["cashflow"] = None
        else:
            q = s.get("ocf_to_ni")
            q_score = None if q is None else max(0.0, min(100.0, (min(q, 1.5) / 1.5) * 100))
            fy = s.get("fcf_years") or 0
            consistency = (s.get("fcf_positive_years", 0) / fy * 100) if fy else None
            areas["cashflow"] = _avg([pct.rank("fcf_margin", s.get("fcf_margin")), q_score, consistency])

        t = s.get("target")
        if t and s.get("target_upside") is not None:
            conf = min(1.0, t["analysts"] / 8)  # 애널리스트 8명 이상이면 완전 신뢰
            raw = _avg([pct.rank("target_upside", s["target_upside"]),
                        (t["buy_ratio"] * 100) if t["buy_ratio"] is not None else None])
            areas["analyst"] = None if raw is None else 50 + (raw - 50) * conf
        else:
            areas["analyst"] = None

        areas["momentum"] = _avg([pct.rank("ret_6m", s.get("ret_6m")),
                                  pct.rank("dist_200dma_pct", s.get("dist_200dma_pct"))])

        holders = held.get(s["symbol"], [])
        g_score = {0: 35.0, 1: 70.0, 2: 85.0}.get(len(holders), 100.0)
        if any(a in ("신규매수", "비중확대") for _, a in holders):
            g_score = min(100.0, g_score + 10)
        areas["guru"] = g_score

        tw = sum(w[k] for k in areas if areas[k] is not None) or 1
        total = sum((areas[k] or 0) * w[k] for k in areas if areas[k] is not None) / tw
        s["score"] = round(total)
        s["areas"] = {k: (None if v is None else round(v)) for k, v in areas.items()}
        s["gurus"] = [{"person": p, "action": a} for p, a in holders]
        s["reasons"] = _reasons(s)
        s["grade"] = ("A" if total >= 75 else "B" if total >= 62 else "C" if total >= 48 else "D")
    return stocks


def _reasons(s: dict) -> dict:
    """초보자용 한 줄 근거. 강점 최대 3개, 약점 최대 2개."""
    good, bad = [], []
    per, peg = s.get("per"), s.get("peg")
    if per is not None:
        if per < 15: good.append(f"PER {per:.0f}배 — 이익 대비 주가가 저렴")
        elif per > 45: bad.append(f"PER {per:.0f}배 — 이익 대비 주가가 비쌈")
    else:
        bad.append("최근 회계연도 적자")
    if peg is not None and peg < 1: good.append(f"PEG {peg:.2f} — 성장 대비 싸다(피터 린치 기준 1 미만)")
    g = s.get("rev_cagr3")
    if g is not None:
        if g > 0.15: good.append(f"매출 3년 연평균 {g*100:.0f}% 성장")
        elif g < 0: bad.append(f"매출이 3년간 연 {g*100:.0f}%로 감소")
    de = s.get("debt_to_equity")
    if de is not None and s.get("sector") not in FINANCE:
        if de < 0.3: good.append("빚이 거의 없는 튼튼한 재무")
        elif de > 2: bad.append(f"부채가 자본의 {de:.1f}배 — 빚 부담 큼")
    fm = s.get("fcf_margin")
    if fm is not None:
        if fm > 0.2: good.append(f"매출의 {fm*100:.0f}%가 잉여현금으로 남음")
        elif fm < 0: bad.append("잉여현금흐름이 마이너스")
    up, t = s.get("target_upside"), s.get("target")
    if up is not None and t:
        if up > 0.15: good.append(f"월가 목표가까지 {up*100:+.0f}% 여유 (애널리스트 {t['analysts']}명)")
        elif up < -0.05: bad.append(f"이미 월가 목표가를 {abs(up)*100:.0f}% 넘어섬")
    if s.get("gurus"):
        names = "·".join(g["person"].split()[-1] for g in s["gurus"][:3])
        good.append(f"{names} 보유")
    r6 = s.get("ret_6m")
    if r6 is not None:
        if r6 > 0.25: good.append(f"6개월 주가 {r6*100:+.0f}%")
        elif r6 < -0.2: bad.append(f"6개월 주가 {r6*100:+.0f}%")
    return {"good": good[:3], "bad": bad[:2]}


def recommend(stocks: list[dict], n: int = 20, per_sector: int = 4, min_mcap: float = 5e9) -> list[dict]:
    """점수 상위 종목, 섹터 쏠림 방지(섹터당 최대 per_sector개), 시총 하한."""
    out, count = [], {}
    for s in sorted(stocks, key=lambda x: -x["score"]):
        if (s.get("market_cap") or 0) < min_mcap or s.get("per") is None:
            continue
        sec = s.get("sector") or "기타"
        if count.get(sec, 0) >= per_sector:
            continue
        count[sec] = count.get(sec, 0) + 1
        out.append(s)
        if len(out) >= n:
            break
    return out
