"""전체 파이프라인: 수집 → 계산 → web/data.json 저장."""
from __future__ import annotations

import datetime as dt
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import etf, fundamentals, market_score, stock_score
from .net import ROOT
from .sources import bls, cnn, edgar, nasdaq, treasury

OUT = os.path.join(ROOT, "web", "data.json")

INDEXES = [  # (심볼, 자산군, 표시이름, 설명)
    ("COMP", "index", "나스닥 종합", "기술주 중심 3,000여 종목"),
    ("NDX", "index", "나스닥 100", "나스닥 대형 기술주 100개"),
    ("IWM", "etf", "러셀 2000", "미국 중소형주 2,000개 (ETF 기준)"),
    ("DIA", "etf", "다우존스", "미국 대표 우량주 30개 (ETF 기준)"),
]
SECTORS = [  # (ETF, 섹터 한국어)
    ("XLK", "기술"), ("XLC", "통신"), ("XLY", "임의소비재"), ("XLP", "필수소비재"),
    ("XLV", "헬스케어"), ("XLF", "금융"), ("XLI", "산업재"), ("XLE", "에너지"),
    ("XLB", "소재"), ("XLU", "유틸리티"), ("XLRE", "부동산"),
]


def _log(msg: str) -> None:
    print(f"[{dt.datetime.now():%H:%M:%S}] {msg}", flush=True)


def _chg_vs_prev_distinct(v: list[float]) -> float | None:
    """마지막 값과 '그 전의 다른 값' 사이의 변동률 (장중 스냅샷 중복 대비)."""
    for x in reversed(v[:-1]):
        if x != v[-1]:
            return (v[-1] / x - 1) * 100
    return None


def _indexes(cnn_snap: dict) -> list[dict]:
    today = dt.date.today()
    frm = (today - dt.timedelta(days=380)).isoformat()
    out = []
    sp = cnn_snap.get("sp500_series") or []
    if sp:
        closes = [p["v"] for p in sp]
        spy = nasdaq.quote("SPY", "etf") or {}
        out.append({"symbol": "SPX", "label": "S&P 500", "desc": "미국 대표 대형주 500개",
                    "price": closes[-1], "change_pct": spy.get("change_pct"),
                    "spy_ratio": (closes[-1] / spy["price"]) if spy.get("price") else None,
                    "ret_1y": (closes[-1] / closes[0] - 1) * 100 if len(closes) > 200 else None,
                    "series": closes[-250:]})
    for sym, asset, label, desc in INDEXES:
        q = nasdaq.quote(sym, asset) or {}
        h = nasdaq.history(sym, asset, frm, today.isoformat())
        closes = [x["close"] for x in h]
        if not closes and q.get("price") is None:
            continue
        out.append({"symbol": sym, "label": label, "desc": desc,
                    "price": q.get("price") or closes[-1], "change_pct": q.get("change_pct"),
                    "ret_1y": (closes[-1] / closes[0] - 1) * 100 if len(closes) > 200 else None,
                    "series": closes[-250:]})
    vix = cnn_snap.get("vix_series") or []
    if vix:
        v = [p["v"] for p in vix]
        out.append({"symbol": "VIX", "label": "VIX 공포지수", "desc": "낮을수록 시장이 평온 (20 이하 안정)",
                    "price": v[-1], "change_pct": _chg_vs_prev_distinct(v),
                    "ret_1y": None, "series": v[-250:], "inverse": True})
    return out


def _sectors() -> list[dict]:
    today = dt.date.today()
    frm = (today - dt.timedelta(days=200)).isoformat()
    out = []
    for etf, label in SECTORS:
        q = nasdaq.quote(etf, "etf") or {}
        h = nasdaq.history(etf, "etf", frm, today.isoformat())
        c = [x["close"] for x in h]
        out.append({"etf": etf, "label": label, "change_pct": q.get("change_pct"),
                    "ret_1m": (c[-1] / c[-22] - 1) * 100 if len(c) > 22 else None,
                    "ret_3m": (c[-1] / c[-64] - 1) * 100 if len(c) > 64 else None})
    return out


def _analyze_universe(universe: list[dict], top: int, workers: int) -> list[dict]:
    targets = universe[:top]
    results: list[dict] = []
    done = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fundamentals.analyze, u["symbol"], u): u["symbol"] for u in targets}
        for f in as_completed(futs):
            done += 1
            try:
                r = f.result()
                if r.get("price"):
                    results.append(r)
            except Exception as e:  # noqa: BLE001
                _log(f"    [warn] {futs[f]} 분석 실패: {type(e).__name__}: {e}")
            if done % 25 == 0 or done == len(targets):
                _log(f"  종목 분석 {done}/{len(targets)} ({time.time() - t0:.0f}초)")
    results.sort(key=lambda x: -(x.get("market_cap") or 0))
    # 같은 재무제표(매출·순이익 동일)를 가진 복수 클래스 주식은 시총 큰 쪽만 남긴다
    seen, uniq = set(), []
    for r in results:
        key = (r.get("revenue"), r.get("net_income"), r.get("fiscal_period"))
        if r.get("revenue") and key in seen:
            continue
        seen.add(key)
        uniq.append(r)
    return uniq


def build(top: int = 200, workers: int = 5, n_recommend: int = 20) -> dict:
    _log("1/6 시장 심리·지수 (CNN Fear & Greed)")
    cnn_snap = cnn.snapshot()

    _log("2/6 금리 (미 재무부) · 고용/물가 (BLS)")
    tre = treasury.curve()
    macro = bls.macro()

    _log("3/6 미국 전체 상장 종목 목록 (Nasdaq 스크리너)")
    universe = nasdaq.screener()
    _log(f"  {len(universe)}개 종목, 시가총액 상위 {top}개 분석 예정")

    _log("4/6 거장 포트폴리오 (SEC 13F)")
    name_index = edgar.build_name_index(universe)
    gurus = edgar.guru_portfolios(name_index)

    _log(f"5/6 종목 재무·목표주가 분석 (동시 {workers}개)")
    stocks = _analyze_universe(universe, top, workers)

    _log("6/6 점수 계산")
    market = market_score.compute(cnn_snap, tre, macro, stocks)
    stock_score.score_all(stocks, gurus, market["score"])
    recs = stock_score.recommend(stocks, n=n_recommend)
    _log("  ETF 분석")
    etfs = etf.analyze_all(market["score"], workers=workers)
    indexes = _indexes(cnn_snap)
    sectors = _sectors()

    # 종목 목록에서 긴 시계열은 추천 종목에만 남긴다 (파일 크기 절약)
    rec_syms = {s["symbol"] for s in recs}
    for s in stocks:
        if s["symbol"] not in rec_syms:
            s["price_series"] = s["price_series"][-30:]

    data = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "universe_size": len(universe),
        "analyzed": len(stocks),
        "market": market,
        "indexes": indexes,
        "sectors": sectors,
        "sentiment": {k: v for k, v in cnn_snap.items() if k not in ("sp500_series", "vix_series")},
        "rates": {k: v for k, v in tre.items() if k != "history"},
        "rates_history": tre.get("history", [])[-250:],
        "macro": macro,
        "recommendations": [s["symbol"] for s in recs],
        "etfs": etfs,
        "etf_categories": etf.CATEGORIES,
        "allocation": etf.allocation(market["score"]),
        "stocks": stocks,
        "gurus": gurus,
        "sources": [
            "Nasdaq Data (시세·재무제표·목표주가·스크리너)", "CNN Fear & Greed (심리·S&P500·VIX)",
            "U.S. Treasury (국채 수익률)", "BLS (실업률·고용·CPI)", "SEC EDGAR 13F (거장 포트폴리오)",
        ],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    _log(f"완료 → {OUT} ({os.path.getsize(OUT)/1e6:.1f} MB) · 시장 점수 {market['score']}점 '{market['verdict']}'")
    return data
