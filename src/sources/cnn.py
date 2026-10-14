"""CNN Fear & Greed Index — 시장 심리 7개 구성지표 + 실제 S&P500/VIX 시계열."""
from __future__ import annotations

from ..net import fetch

URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
_HDRS = {"Origin": "https://edition.cnn.com", "Referer": "https://edition.cnn.com/"}

# 구성지표 → (한국어 이름, 초보자용 설명)
COMPONENTS = {
    "market_momentum_sp500": ("주가 모멘텀", "S&P500이 125일 평균선보다 위에 있는지 — 큰 흐름이 상승인가"),
    "stock_price_strength": ("신고가 종목 수", "52주 신고가 종목이 신저가 종목보다 많은가 — 오르는 주식이 넓게 퍼졌는가"),
    "stock_price_breadth": ("거래량 폭", "오르는 주식의 거래량이 내리는 주식보다 많은가 — 상승에 돈이 실렸는가"),
    "put_call_options": ("풋/콜 비율", "하락 베팅(풋) 대비 상승 베팅(콜) — 투자자가 겁먹었는가"),
    "market_volatility_vix": ("변동성(VIX)", "'공포지수'. 낮으면 시장이 평온, 높으면 불안"),
    "junk_bond_demand": ("정크본드 수요", "위험한 회사채를 사려는 수요 — 위험을 감수할 분위기인가"),
    "safe_haven_demand": ("안전자산 수요", "주식 대신 국채로 돈이 도망가고 있는가"),
}


def snapshot(ttl: float = 3600) -> dict:
    """Fear & Greed 종합점수 + 구성지표 + S&P500/VIX 일별 시계열."""
    d = fetch(URL, headers=_HDRS, ttl=ttl, min_interval=0.5)
    if not isinstance(d, dict):
        return {}

    fng = d.get("fear_and_greed") or {}
    comps = []
    for key, (ko, desc) in COMPONENTS.items():
        c = d.get(key) or {}
        if c.get("score") is None:
            continue
        comps.append({
            "key": key, "label": ko, "desc": desc,
            "score": round(float(c["score"]), 1),
            "rating": c.get("rating"),
        })

    def series(key: str) -> list[dict]:
        rows = (d.get(key) or {}).get("data") or []
        return [{"t": int(r["x"]), "v": float(r["y"])}
                for r in rows if r.get("x") is not None and r.get("y") is not None]

    sp500 = series("market_momentum_sp500")   # y = S&P500 실제 종가
    vix = series("market_volatility_vix")     # y = VIX 실제 값

    return {
        "score": round(float(fng.get("score") or 0), 1),
        "rating": fng.get("rating"),
        "prev_close": fng.get("previous_close"),
        "prev_week": fng.get("previous_1_week"),
        "prev_month": fng.get("previous_1_month"),
        "prev_year": fng.get("previous_1_year"),
        "components": comps,
        "sp500_series": sp500,
        "vix_series": vix,
        "sp500": sp500[-1]["v"] if sp500 else None,
        "vix": vix[-1]["v"] if vix else None,
    }
