"""ETF 분석: 초보자가 알아야 할 대표 ETF 50여 개를 분류·채점한다.

개별 종목과 달리 재무제표가 없으므로 가격 흐름(모멘텀·추세), 위험(변동성·최대낙폭),
비용(보수율), 배당으로 점수를 매긴다. 시장 점수에 따라 공격/방어 가중치를 바꾼다.
"""
from __future__ import annotations

import datetime as dt
import math
from bisect import bisect_left
from concurrent.futures import ThreadPoolExecutor

from .sources import nasdaq
from .sources.nasdaq import _get, _num

# (티커, 분류, 한국어 이름, 초보자용 한 줄 설명)
UNIVERSE = [
    # 핵심 — 시장 전체를 통째로
    ("VOO", "핵심", "S&P 500", "미국 대표 500개 기업. 버핏이 가족에게 권한 바로 그 상품"),
    ("SPY", "핵심", "S&P 500 (SPY)", "VOO와 같은 지수, 세계에서 가장 많이 거래되는 ETF"),
    ("QQQ", "핵심", "나스닥 100", "애플·엔비디아·MS 등 대형 기술주 100개"),
    ("VTI", "핵심", "미국 전체 주식", "대·중·소형주 4,000여 개를 한 번에"),
    ("RSP", "핵심", "S&P 500 동일가중", "500개를 똑같은 비중으로 — 대형 기술주 쏠림을 피함"),
    ("IWM", "핵심", "러셀 2000 (소형주)", "미국 중소형주 2,000개. 경기 회복기에 강함"),
    ("DIA", "핵심", "다우존스 30", "미국 대표 우량주 30개"),
    # 섹터
    ("XLK", "섹터", "기술", "소프트웨어·반도체·하드웨어"),
    ("XLV", "섹터", "헬스케어", "제약·의료기기·보험. 불황에 강한 편"),
    ("XLF", "섹터", "금융", "은행·보험·카드사"),
    ("XLE", "섹터", "에너지", "석유·가스. 유가에 연동"),
    ("XLY", "섹터", "임의소비재", "아마존·테슬라·나이키 등 경기 좋을 때 잘 팔리는 것"),
    ("XLP", "섹터", "필수소비재", "식품·생필품. 불황에도 꾸준"),
    ("XLI", "섹터", "산업재", "항공·기계·방산"),
    ("XLU", "섹터", "유틸리티", "전기·가스. 배당 높고 변동 작음"),
    ("XLC", "섹터", "통신", "구글·메타·넷플릭스"),
    ("XLRE", "섹터", "부동산", "리츠(REITs). 금리 내릴 때 유리"),
    # 테마·성장
    ("SMH", "테마", "반도체", "엔비디아·TSMC·브로드컴 등 반도체 25개"),
    ("SOXX", "테마", "반도체 (SOXX)", "SMH와 비슷, 구성 종목 약간 다름"),
    ("IGV", "테마", "소프트웨어", "클라우드·SaaS 기업"),
    ("XBI", "테마", "바이오테크", "신약 개발사. 변동 매우 큼"),
    ("ARKK", "테마", "혁신 기술 (ARK)", "캐시 우드의 파괴적 혁신 기업. 고위험"),
    ("ICLN", "테마", "청정에너지", "태양광·풍력"),
    ("BOTZ", "테마", "로봇·AI", "로봇·자동화·인공지능"),
    # 배당
    ("SCHD", "배당", "고배당 우량주", "10년 이상 배당 늘려온 재무 우량 기업. 초보자 인기 1위"),
    ("VIG", "배당", "배당 성장", "배당을 꾸준히 늘리는 기업"),
    ("VYM", "배당", "고배당", "배당수익률 높은 대형주"),
    ("JEPI", "배당", "월배당 커버드콜", "옵션 판매로 월 배당. 상승장엔 덜 오름"),
    ("DVY", "배당", "고배당 (DVY)", "배당 높은 100개 기업"),
    # 채권
    ("BND", "채권", "미국 채권 전체", "국채+회사채 종합. 주식의 완충재"),
    ("TLT", "채권", "장기 국채 (20년+)", "금리 내리면 크게 오르고, 오르면 크게 떨어짐"),
    ("IEF", "채권", "중기 국채 (7~10년)", "TLT보다 변동 작음"),
    ("SHY", "채권", "단기 국채 (1~3년)", "현금에 가까운 안전자산"),
    ("LQD", "채권", "투자등급 회사채", "우량 기업 회사채"),
    ("HYG", "채권", "하이일드 회사채", "위험한 회사채, 이자 높음. 주식과 비슷하게 움직임"),
    ("TIP", "채권", "물가연동 국채", "물가 오르면 원금도 올라감"),
    # 금·원자재·달러
    ("GLD", "금·원자재", "금", "위기 때 피난처. 주식과 반대로 움직이는 경향"),
    ("IAU", "금·원자재", "금 (IAU)", "GLD와 같고 보수가 더 쌈"),
    ("SLV", "금·원자재", "은", "금보다 변동 큼, 산업 수요 영향"),
    ("DBC", "금·원자재", "원자재 종합", "원유·금속·곡물. 인플레이션 방어"),
    ("USO", "금·원자재", "원유", "WTI 유가 추종. 장기 보유 불리"),
    ("UUP", "금·원자재", "달러 인덱스", "달러 강세에 베팅"),
    # 해외
    ("VEA", "해외", "선진국 (미국 제외)", "유럽·일본·호주 등"),
    ("VWO", "해외", "신흥국", "중국·인도·대만·브라질"),
    ("EWJ", "해외", "일본", "일본 대형주"),
    ("INDA", "해외", "인도", "인도 대형주"),
    ("FXI", "해외", "중국 대형주", "중국 본토 대형주 50개"),
    ("EWY", "해외", "한국", "삼성전자·SK하이닉스 등 한국 대형주"),
    # 방어
    ("USMV", "방어", "저변동 미국주식", "출렁임이 작은 종목만 골라 담음"),
    ("SPLV", "방어", "S&P 저변동 100", "S&P500 중 가장 덜 흔들리는 100개"),
]
CATEGORIES = ["핵심", "섹터", "테마", "배당", "채권", "금·원자재", "해외", "방어"]
DEFENSIVE = {"채권", "금·원자재", "방어", "배당"}


def _dividend_yield(symbol: str, price: float | None) -> float | None:
    """최근 12개월 배당 합계 ÷ 현재가 (%)."""
    d = _get(f"quote/{symbol}/dividends", {"assetclass": "etf"}, ttl=3 * 24 * 3600) or {}
    rows = ((d.get("dividends") or {}).get("rows")) or []
    if not rows or not price:
        return None
    cutoff = dt.date.today() - dt.timedelta(days=370)
    total = 0.0
    for r in rows:
        try:
            ex = dt.datetime.strptime(r.get("exOrEffDate", ""), "%m/%d/%Y").date()
        except ValueError:
            continue
        amt = _num(r.get("amount"))
        if ex >= cutoff and amt:
            total += amt
    return total / price * 100 if total else 0.0


def _stats(closes: list[float]) -> dict:
    out: dict = {}
    n = len(closes)
    if n < 30:
        return out
    last = closes[-1]
    for key, days in (("ret_1m", 21), ("ret_3m", 63), ("ret_6m", 126), ("ret_1y", 250)):
        out[key] = (last / closes[-days - 1] - 1) if n > days else (last / closes[0] - 1 if key == "ret_1y" else None)
    k = min(200, n)
    dma = sum(closes[-k:]) / k
    out["dist_200dma_pct"] = (last / dma - 1) * 100
    rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, n) if closes[i - 1] > 0]
    mu = sum(rets) / len(rets)
    out["volatility"] = math.sqrt(sum((r - mu) ** 2 for r in rets) / max(1, len(rets) - 1)) * math.sqrt(252) * 100
    peak, mdd = closes[0], 0.0
    for c in closes:
        peak = max(peak, c)
        mdd = min(mdd, c / peak - 1)
    out["max_drawdown"] = mdd * 100
    out["week52_from_high"] = (last / max(closes) - 1) * 100
    return out


def _analyze(row: tuple) -> dict | None:
    sym, cat, ko, desc = row
    today = dt.date.today()
    q = nasdaq.quote(sym, "etf") or {}
    hist = nasdaq.history(sym, "etf", (today - dt.timedelta(days=400)).isoformat(), today.isoformat())
    closes = [h["close"] for h in hist]
    price = q.get("price") or (closes[-1] if closes else None)
    if not price:
        return None
    s = _get(f"quote/{sym}/summary", {"assetclass": "etf"}, ttl=3 * 24 * 3600) or {}
    sd = s.get("summaryData") or {}
    val = lambda k: (sd.get(k) or {}).get("value")
    return {
        "symbol": sym, "category": cat, "name": ko, "desc": desc,
        "price": price, "change_pct": q.get("change_pct"),
        "expense_ratio": _num(val("ExpenseRatio")),
        "beta": _num(val("Beta")),
        "aum": _num(val("MarketCap")),
        "dividend_yield": _dividend_yield(sym, price),
        "price_series": closes[-250:],
        **_stats(closes),
    }


def _pct(arr: list[float], v: float | None, higher_better=True) -> float | None:
    if v is None or len(arr) < 5:
        return None
    p = bisect_left(arr, v) / len(arr) * 100
    return p if higher_better else 100 - p


def _avg(vals):
    v = [x for x in vals if x is not None]
    return sum(v) / len(v) if v else None


def _reasons(e: dict) -> dict:
    good, bad = [], []
    if (e.get("ret_1y") or 0) > 0.15: good.append(f"1년 수익률 {e['ret_1y']*100:+.0f}%")
    if (e.get("ret_1y") or 0) < -0.1: bad.append(f"1년 수익률 {e['ret_1y']*100:+.0f}%")
    if (e.get("dist_200dma_pct") or 0) > 0: good.append("200일선 위 — 장기 상승 추세")
    elif e.get("dist_200dma_pct") is not None: bad.append("200일선 아래 — 추세 약함")
    if e.get("volatility") is not None and e["volatility"] < 12: good.append(f"변동성 {e['volatility']:.0f}% — 출렁임 작음")
    if e.get("volatility") is not None and e["volatility"] > 30: bad.append(f"변동성 {e['volatility']:.0f}% — 출렁임 큼")
    if e.get("expense_ratio") is not None and e["expense_ratio"] <= 0.1: good.append(f"연 보수 {e['expense_ratio']:.2f}% — 매우 저렴")
    if e.get("expense_ratio") is not None and e["expense_ratio"] >= 0.6: bad.append(f"연 보수 {e['expense_ratio']:.2f}% — 비쌈")
    if (e.get("dividend_yield") or 0) >= 3: good.append(f"배당수익률 {e['dividend_yield']:.1f}%")
    if e.get("max_drawdown") is not None and e["max_drawdown"] < -30: bad.append(f"1년 최대낙폭 {e['max_drawdown']:.0f}%")
    return {"good": good[:3], "bad": bad[:2]}


def analyze_all(market_score: int, workers: int = 6) -> list[dict]:
    with ThreadPoolExecutor(max_workers=workers) as ex:
        etfs = [e for e in ex.map(_analyze, UNIVERSE) if e]

    cols = {k: sorted(e[k] for e in etfs if e.get(k) is not None)
            for k in ("ret_1m", "ret_3m", "ret_6m", "ret_1y", "dist_200dma_pct", "volatility", "max_drawdown", "expense_ratio", "dividend_yield")}
    # 시장 점수에 따른 가중치: 약세장일수록 위험·배당 중시, 강세장일수록 모멘텀 중시
    if market_score < 40:
        w = {"momentum": 25, "trend": 15, "risk": 50, "cost": 10}
    elif market_score >= 70:
        w = {"momentum": 45, "trend": 25, "risk": 20, "cost": 10}
    else:
        w = {"momentum": 35, "trend": 20, "risk": 35, "cost": 10}

    for e in etfs:
        a = {
            "momentum": _avg([_pct(cols["ret_1m"], e.get("ret_1m")), _pct(cols["ret_3m"], e.get("ret_3m")),
                              _pct(cols["ret_6m"], e.get("ret_6m")), _pct(cols["ret_1y"], e.get("ret_1y"))]),
            "trend": _pct(cols["dist_200dma_pct"], e.get("dist_200dma_pct")),
            "risk": _avg([_pct(cols["volatility"], e.get("volatility"), False), _pct(cols["max_drawdown"], e.get("max_drawdown"))]),
            "cost": _pct(cols["expense_ratio"], e.get("expense_ratio"), False),
        }
        tw = sum(w[k] for k in a if a[k] is not None) or 1
        e["score"] = round(sum((a[k] or 0) * w[k] for k in a if a[k] is not None) / tw)
        e["areas"] = {k: (None if v is None else round(v)) for k, v in a.items()}
        e["grade"] = "A" if e["score"] >= 75 else "B" if e["score"] >= 62 else "C" if e["score"] >= 48 else "D"
        e["reasons"] = _reasons(e)
    etfs.sort(key=lambda e: -e["score"])
    return etfs


def allocation(market_score: int) -> dict:
    """시장 점수에 따른 초보자용 ETF 배분 예시 (투자 조언이 아닌 교육용 예시)."""
    if market_score >= 80:
        mix, note = [("주식", 80), ("채권", 10), ("금", 10)], "환경이 매우 좋을 때. 주식 비중을 높게"
    elif market_score >= 65:
        mix, note = [("주식", 70), ("채권", 20), ("금", 10)], "대체로 좋을 때. 주식 중심, 채권으로 완충"
    elif market_score >= 50:
        mix, note = [("주식", 60), ("채권", 30), ("금", 10)], "신호가 섞여 있을 때. 고전적인 60/40에 가깝게"
    elif market_score >= 35:
        mix, note = [("주식", 45), ("채권", 40), ("금", 15)], "경고 신호가 많을 때. 채권·금 비중을 올려 방어"
    else:
        mix, note = [("주식", 30), ("채권", 50), ("금", 20)], "환경이 나쁠 때. 안전자산 중심, 주식은 최소한만"
    picks = {"주식": ["VOO", "QQQ", "SCHD"], "채권": ["BND", "TLT", "SHY"], "금": ["GLD", "IAU"]}
    return {"note": note, "mix": [{"asset": a, "pct": p, "etfs": picks[a]} for a, p in mix]}
