"""시장 전체 점수 (0~100). 100 = 적극 매수 타이밍, 0 = 관망/현금 보유.

7개 영역을 각각 0~100으로 매긴 뒤 가중 평균한다. 각 영역은 '왜 이 점수인지'를
초보자 말로 설명하는 문장을 함께 내보낸다.
"""
from __future__ import annotations

from statistics import median


def _clamp(x: float, lo: float = 0, hi: float = 100) -> float:
    return max(lo, min(hi, x))


def _interp(x: float | None, points: list[tuple[float, float]], default: float = 50) -> float:
    """구간 선형보간. points = [(x0, y0), (x1, y1), ...] x 오름차순."""
    if x is None:
        return default
    if x <= points[0][0]:
        return points[0][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return points[-1][1]


def _fmt(x, nd=1, suffix=""):
    return "–" if x is None else f"{x:.{nd}f}{suffix}"


# 각 영역: (키, 한국어 이름, 가중치, 초보자용 한 줄 설명)
AREAS = [
    ("trend", "추세", 20, "S&P500이 장기 평균선(200일선) 위에서 우상향하고 있는가"),
    ("breadth", "시장 폭", 15, "소수 대형주만이 아니라 많은 종목이 함께 오르고 있는가"),
    ("rates", "금리·통화정책", 20, "연준이 금리를 내리는 방향인가, 국채 금리는 주식에 부담이 되지 않는가"),
    ("macro", "경기·고용", 15, "실업률·고용·물가가 경기 침체 신호를 보내지 않는가"),
    ("sentiment", "투자 심리", 10, "역발상 반영: 모두가 겁먹을 때가 기회, 모두가 들뜰 때가 위험"),
    ("volatility", "변동성", 10, "VIX(공포지수)가 낮아 시장이 안정적인가"),
    ("valuation", "밸류에이션", 10, "대형주 평균 PER이 비싸지 않고, 주식 수익률이 국채 금리보다 매력적인가"),
]

VERDICTS = [
    (80, "적극 매수", "시장 환경이 매우 우호적입니다. 분할 매수로 주식 비중을 적극적으로 늘려볼 만합니다.", "#15803d"),
    (65, "매수 우위", "대체로 긍정적입니다. 우량주 중심으로 천천히 비중을 늘리세요.", "#65a30d"),
    (50, "중립 · 분할 매수", "좋은 신호와 나쁜 신호가 섞여 있습니다. 한 번에 사지 말고 나눠서 접근하세요.", "#ca8a04"),
    (35, "신중 · 현금 확보", "경고 신호가 많습니다. 신규 매수는 줄이고 현금 비중을 늘리는 편이 안전합니다.", "#ea580c"),
    (0, "관망 · 현금 보유", "시장 환경이 나쁩니다. 섣불리 사지 말고 기다리거나 일부 매도해 현금을 확보하세요.", "#dc2626"),
]


def _trend(sp500: list[dict]) -> tuple[float, str, dict]:
    closes = [p["v"] for p in sp500]
    if len(closes) < 60:
        return 50, "S&P500 가격 자료가 부족해 중립으로 둡니다.", {}
    last = closes[-1]
    n200 = min(200, len(closes))
    dma200 = sum(closes[-n200:]) / n200
    dma50 = sum(closes[-50:]) / 50
    dma200_prev = sum(closes[-n200 - 20:-20]) / n200 if len(closes) >= n200 + 20 else dma200
    dist = (last / dma200 - 1) * 100
    slope_up = dma200 > dma200_prev
    above50 = last > dma50

    score = 50 + _clamp(dist * 3, -30, 30) + (10 if slope_up else -10) + (10 if above50 else -10)
    score = _clamp(score)
    why = (f"S&P500은 200일선보다 {dist:+.1f}% {'위' if dist >= 0 else '아래'}에 있고, "
           f"200일선은 {'상승' if slope_up else '하락'} 중, 50일선 {'위' if above50 else '아래'}입니다.")
    return score, why, {"dist_200dma_pct": round(dist, 2), "dma200_rising": slope_up, "above_50dma": above50,
                        "dma50": round(dma50, 1), "dma200": round(dma200, 1)}


def _breadth(comps: dict) -> tuple[float, str, dict]:
    s = comps.get("stock_price_strength")
    b = comps.get("stock_price_breadth")
    j = comps.get("junk_bond_demand")
    vals = [v for v in (s, b, j) if v is not None]
    if not vals:
        return 50, "시장 폭 자료가 없어 중립으로 둡니다.", {}
    score = _clamp(0.4 * (s if s is not None else 50) + 0.4 * (b if b is not None else 50) + 0.2 * (j if j is not None else 50))
    why = (f"신고가 종목 수 {_fmt(s,0)}점, 상승 거래량 폭 {_fmt(b,0)}점, 위험자산(정크본드) 수요 {_fmt(j,0)}점 "
           f"(각 0~100, 높을수록 건강).")
    return score, why, {"strength": s, "breadth": b, "junk": j}


def _rates(t: dict) -> tuple[float, str, dict]:
    if not t:
        return 50, "국채 금리 자료가 없어 중립으로 둡니다.", {}
    y10, m3_chg = t.get("y10"), t.get("m3_chg_6m")
    y10_chg, spread = t.get("y10_chg_3m"), t.get("spread_10y_2y")
    s_policy = _interp(m3_chg, [(-1.0, 90), (-0.5, 75), (0, 50), (0.5, 25), (1.0, 10)])
    s_level = _interp(y10, [(3.0, 85), (4.0, 65), (4.5, 50), (5.0, 35), (5.5, 25), (6.5, 10)])
    s_dir = _interp(y10_chg, [(-0.75, 80), (-0.25, 60), (0, 50), (0.25, 40), (0.75, 20)])
    s_curve = _interp(spread, [(-1.0, 20), (-0.3, 35), (0, 50), (0.5, 60), (1.5, 65)])
    score = _clamp(0.35 * s_policy + 0.25 * s_level + 0.2 * s_dir + 0.2 * s_curve)
    policy_txt = ("내리는 중(완화)" if (m3_chg or 0) < -0.15 else "올리는 중(긴축)" if (m3_chg or 0) > 0.15 else "동결 수준")
    why = (f"단기금리(3개월물)는 6개월 전보다 {_fmt(m3_chg,2,'%p')}로 {policy_txt}. "
           f"10년물은 {_fmt(y10,2,'%')}(3개월 전 대비 {_fmt(y10_chg,2,'%p')}), "
           f"장단기 금리차(10년-2년) {_fmt(spread,2,'%p')}.")
    return score, why, {"policy": s_policy, "level": s_level, "direction": s_dir, "curve": s_curve}


def _macro(m: dict) -> tuple[float, str, dict]:
    if not m:
        return 50, "고용·물가 자료가 없어 중립으로 둡니다.", {}
    un = m.get("unemployment") or {}
    pay = m.get("payrolls") or {}
    cpi = m.get("cpi") or {}
    rise = un.get("rise_from_12m_low")
    pay3 = pay.get("avg_monthly_change_3m")
    yoy = cpi.get("yoy_pct")
    # Sahm rule: 실업률이 1년 최저 대비 0.5%p 이상 오르면 침체 신호
    s_un = _interp(rise, [(0, 85), (0.2, 65), (0.4, 45), (0.5, 30), (0.8, 10)])
    s_pay = _interp(pay3, [(-100, 10), (0, 35), (50, 50), (100, 65), (150, 80), (250, 90)])
    s_cpi = _interp(yoy, [(0, 40), (1, 55), (2, 75), (3, 65), (4, 45), (5, 25), (7, 10)])
    score = _clamp(0.4 * s_un + 0.3 * s_pay + 0.3 * s_cpi)
    why = (f"실업률 {_fmt(un.get('value'),1,'%')}(1년 최저 대비 {_fmt(rise,1,'%p')} 상승), "
           f"최근 3개월 월평균 고용 증가 {_fmt(pay3,0,'천 명')}, 물가상승률 {_fmt(yoy,1,'%')}.")
    return score, why, {"unemployment": s_un, "payrolls": s_pay, "cpi": s_cpi}


def _sentiment(fng: float | None, put_call: float | None) -> tuple[float, str, dict]:
    if fng is None:
        return 50, "심리 지표가 없어 중립으로 둡니다.", {}
    # 역발상: 공포(낮은 점수)일수록 매수 기회 → 점수 높게. 단, 정도를 완화(0.8배).
    s_fng = _clamp(50 + (50 - fng) * 0.8)
    s_pc = _clamp(50 + (50 - put_call) * 0.5) if put_call is not None else 50
    score = _clamp(0.7 * s_fng + 0.3 * s_pc)
    mood = ("극도의 공포" if fng < 25 else "공포" if fng < 45 else "중립" if fng < 55 else "탐욕" if fng < 75 else "극도의 탐욕")
    why = (f"CNN 공포·탐욕 지수 {fng:.0f}점({mood}). 버핏의 말처럼 '남들이 두려워할 때 욕심을' — "
           f"공포일수록 점수를 높게 줍니다.")
    return score, why, {"fng": fng, "put_call": put_call}


def _volatility(vix: float | None) -> tuple[float, str, dict]:
    score = _interp(vix, [(10, 95), (14, 85), (18, 65), (22, 50), (28, 30), (35, 15), (50, 5)])
    lvl = ("매우 안정" if (vix or 20) < 15 else "안정" if (vix or 20) < 20 else "다소 불안" if (vix or 20) < 28 else "불안")
    why = f"VIX {_fmt(vix,1)} — {lvl}. (보통 20 아래면 평온, 30 위면 공포 국면)"
    return score, why, {"vix": vix}


def _valuation(stocks: list[dict], y10: float | None) -> tuple[float, str, dict]:
    pers = [s["per"] for s in stocks if s.get("per") and 0 < s["per"] < 200]
    if len(pers) < 20:
        return 50, "PER 자료가 부족해 중립으로 둡니다.", {}
    med = median(pers)
    s_per = _interp(med, [(12, 90), (16, 80), (20, 65), (25, 48), (30, 32), (35, 20), (45, 10)])
    gap = (100 / med) - (y10 or 4.5)  # 주식 수익률(1/PER) − 10년물 금리
    s_fed = _interp(gap, [(-3, 10), (-2, 25), (-1, 40), (0, 55), (1, 70), (2, 85)])
    score = _clamp(0.5 * s_per + 0.5 * s_fed)
    why = (f"대형주 PER 중앙값 {med:.1f}배. 주식 기대수익률(1/PER) {100/med:.1f}% vs 10년 국채 {_fmt(y10,2,'%')} "
           f"→ 차이 {gap:+.1f}%p ({'주식이 상대적으로 매력' if gap > 0 else '국채가 더 매력적'}).")
    return score, why, {"median_per": round(med, 1), "earnings_yield_gap": round(gap, 2)}


def compute(cnn: dict, treasury: dict, bls: dict, stocks: list[dict]) -> dict:
    comps = {c["key"]: c["score"] for c in cnn.get("components", [])}
    results = {
        "trend": _trend(cnn.get("sp500_series", [])),
        "breadth": _breadth(comps),
        "rates": _rates(treasury),
        "macro": _macro(bls),
        "sentiment": _sentiment(cnn.get("score"), comps.get("put_call_options")),
        "volatility": _volatility(cnn.get("vix")),
        "valuation": _valuation(stocks, treasury.get("y10")),
    }
    total_w = sum(w for _, _, w, _ in AREAS)
    score = sum(results[k][0] * w for k, _, w, _ in AREAS) / total_w
    score = round(_clamp(score))

    verdict = next(v for v in VERDICTS if score >= v[0])
    areas = []
    for key, label, w, desc in AREAS:
        s, why, detail = results[key]
        areas.append({"key": key, "label": label, "weight": w, "desc": desc,
                      "score": round(s), "why": why, "detail": detail})
    best = max(areas, key=lambda a: a["score"])
    worst = min(areas, key=lambda a: a["score"])
    return {
        "score": score,
        "verdict": verdict[1], "advice": verdict[2], "color": verdict[3],
        "summary": f"가장 좋은 신호는 '{best['label']}'({best['score']}점), 가장 나쁜 신호는 '{worst['label']}'({worst['score']}점)입니다.",
        "areas": areas,
    }
