"""종목별 핵심 재무지표 계산: PER, 부채, 현금흐름, 성장률, 목표주가.

Nasdaq 재무제표(연간 4개년)와 시세·목표주가를 합쳐 한 종목을 하나의 dict로 만든다.
값을 구할 수 없으면 None — 점수 계산 단계에서 '모름'으로 다룬다.
"""
from __future__ import annotations

import datetime as dt

from .sources import nasdaq


def _first(stmt: dict, *labels: str) -> list[float | None]:
    for l in labels:
        if l in stmt:
            return stmt[l]
    return []


def _at(vals: list, i: int) -> float | None:
    return vals[i] if i < len(vals) else None


def _cagr(vals: list, years: int) -> float | None:
    """vals[0]=최근, vals[years]=years년 전. 둘 다 양수여야 의미가 있다."""
    a, b = _at(vals, 0), _at(vals, years)
    if a is None or b is None or a <= 0 or b <= 0:
        return None
    return (a / b) ** (1 / years) - 1


def _yoy(vals: list) -> float | None:
    a, b = _at(vals, 0), _at(vals, 1)
    if a is None or b is None or b == 0:
        return None
    if b < 0:  # 적자 → 흑자 전환 같은 경우는 비율이 무의미
        return None
    return a / b - 1


def _div(a, b) -> float | None:
    if a is None or b is None or b == 0:
        return None
    return a / b


def _momentum(hist: list[dict]) -> dict:
    """6개월·1년 수익률, 200일선 대비 위치."""
    closes = [h["close"] for h in hist]
    out = {"ret_6m": None, "ret_1y": None, "above_200dma": None, "dist_200dma_pct": None}
    if not closes:
        return out
    last = closes[-1]
    if len(closes) > 126:
        out["ret_6m"] = last / closes[-127] - 1
    if len(closes) > 250:
        out["ret_1y"] = last / closes[-251] - 1
    elif len(closes) > 20:
        out["ret_1y"] = last / closes[0] - 1
    if len(closes) >= 200:
        dma = sum(closes[-200:]) / 200
        out["above_200dma"] = last > dma
        out["dist_200dma_pct"] = (last / dma - 1) * 100
    return out


def analyze(symbol: str, base: dict) -> dict:
    """base = 스크리너 행 {symbol,name,price,market_cap,...}"""
    price = base.get("price")
    mcap = base.get("market_cap")

    fin = nasdaq.financials(symbol)
    inc, bal, cf = fin["income"], fin["balance"], fin["cashflow"]
    summ = nasdaq.summary(symbol)
    tgt = nasdaq.price_target(symbol)

    today = dt.date.today()
    hist = nasdaq.history(symbol, "stocks", (today - dt.timedelta(days=400)).isoformat(),
                          today.isoformat())

    revenue = _first(inc, "Total Revenue")
    net_income = _first(inc, "Net Income", "Net Income Applicable to Common Shareholders")
    op_income = _first(inc, "Operating Income")
    ocf = _first(cf, "Net Cash Flow-Operating")
    capex = _first(cf, "Capital Expenditures")
    equity = _first(bal, "Total Equity")
    lt_debt = _first(bal, "Long-Term Debt")
    st_debt = _first(bal, "Short-Term Debt / Current Portion of Long-Term Debt")
    cash = _first(bal, "Cash and Cash Equivalents")
    st_inv = _first(bal, "Short-Term Investments")
    cur_assets = _first(bal, "Total Current Assets")
    cur_liab = _first(bal, "Total Current Liabilities")
    total_liab = _first(bal, "Total Liabilities")

    ni0, rev0, ocf0, eq0 = _at(net_income, 0), _at(revenue, 0), _at(ocf, 0), _at(equity, 0)
    capex0 = _at(capex, 0)
    fcf_series = [
        (None if (o is None or c is None) else o + c)  # capex는 음수로 적혀 있다
        for o, c in zip(ocf, capex)
    ] if ocf and capex else []
    fcf0 = _at(fcf_series, 0)

    debt0 = (_at(lt_debt, 0) or 0) + (_at(st_debt, 0) or 0)
    cash0 = (_at(cash, 0) or 0) + (_at(st_inv, 0) or 0)
    net_debt = debt0 - cash0

    per = _div(mcap, ni0) if (ni0 and ni0 > 0) else None
    p_fcf = _div(mcap, fcf0) if (fcf0 and fcf0 > 0) else None
    eps_growth = _yoy(net_income)
    rev_growth = _yoy(revenue)
    rev_cagr3 = _cagr(revenue, min(3, max(len(revenue) - 1, 1))) if len(revenue) >= 2 else None
    ni_cagr3 = _cagr(net_income, min(3, max(len(net_income) - 1, 1))) if len(net_income) >= 2 else None
    # 피터 린치식 PEG: PER ÷ 이익성장률(%)
    growth_for_peg = ni_cagr3 if ni_cagr3 is not None else eps_growth
    peg = (per / (growth_for_peg * 100)) if (per and growth_for_peg and growth_for_peg > 0.03) else None

    mom = _momentum(hist)

    upside = None
    if tgt and price:
        upside = tgt["mean"] / price - 1

    return {
        "symbol": symbol,
        "name": base.get("name", "").replace(" Common Stock", "").replace(" Class A", "").strip(),
        "price": price,
        "change_pct": base.get("change_pct"),
        "market_cap": mcap,
        "sector": summ.get("sector"),
        "industry": summ.get("industry"),
        "week52_high": summ.get("week52_high"),
        "week52_low": summ.get("week52_low"),
        "dividend_yield": summ.get("dividend_yield"),
        "fiscal_period": fin["periods"][0] if fin["periods"] else None,
        # 가치
        "per": per, "p_fcf": p_fcf, "peg": peg,
        # 성장
        "rev_growth": rev_growth, "rev_cagr3": rev_cagr3,
        "eps_growth": eps_growth, "ni_cagr3": ni_cagr3,
        # 수익성
        "net_margin": _div(ni0, rev0), "op_margin": _div(_at(op_income, 0), rev0),
        "roe": _div(ni0, eq0) if (eq0 and eq0 > 0) else None,
        # 재무 안정
        "debt_to_equity": _div(debt0, eq0) if (eq0 and eq0 > 0) else None,
        "liab_to_assets": _div(_at(total_liab, 0), (_at(total_liab, 0) or 0) + (eq0 or 0)) if eq0 is not None else None,
        "current_ratio": _div(_at(cur_assets, 0), _at(cur_liab, 0)),
        "net_debt": net_debt, "net_debt_to_fcf": _div(net_debt, fcf0) if (fcf0 and fcf0 > 0) else None,
        "cash": cash0, "debt": debt0,
        # 현금흐름
        "ocf": ocf0, "fcf": fcf0, "fcf_margin": _div(fcf0, rev0),
        "ocf_to_ni": _div(ocf0, ni0) if (ni0 and ni0 > 0) else None,
        "fcf_positive_years": sum(1 for f in fcf_series if f is not None and f > 0),
        "fcf_years": sum(1 for f in fcf_series if f is not None),
        "revenue": rev0, "net_income": ni0,
        "revenue_series": revenue[:4], "net_income_series": net_income[:4], "fcf_series": fcf_series[:4],
        # 월가 목표주가
        "target": tgt, "target_upside": upside,
        # 모멘텀
        **mom,
        "price_series": [h["close"] for h in hist[-130:]],  # 6개월 스파크라인용
    }
