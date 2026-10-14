"""SEC EDGAR 13F 공시 — 월가 거장들의 분기별 보유 종목 (키 불필요).

13F는 1억 달러 이상 운용사가 분기 종료 후 45일 안에 제출하는 미국 주식 보유 내역이다.
최근 2개 분기를 비교해 신규매수/비중확대/축소/전량매도를 계산한다.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from ..net import fetch_sec

DAY = 24 * 3600

# (CIK, 운용사, 대표 인물, 한 줄 소개)
GURUS = [
    (1067983, "Berkshire Hathaway", "워렌 버핏", "가치투자의 대명사. 이해하기 쉬운 사업, 강한 해자, 합리적 가격"),
    (1536411, "Duquesne Family Office", "스탠리 드러켄밀러", "거시경제 흐름을 읽고 과감하게 집중 투자"),
    (1336528, "Pershing Square", "빌 애크먼", "소수의 우량 기업에 집중하는 행동주의 투자자"),
    (1649339, "Scion Asset Management", "마이클 버리", "'빅쇼트'의 주인공. 역발상 가치투자"),
    (1656456, "Appaloosa Management", "데이비드 테퍼", "위기 때 과감히 사는 역발상 투자"),
    (1061768, "Baupost Group", "세스 클라먼", "'안전마진'의 저자. 극도로 보수적인 가치투자"),
    (1350694, "Bridgewater Associates", "레이 달리오", "세계 최대 헤지펀드. 경제 사이클 기반 분산투자"),
    (1079114, "Greenlight Capital", "데이비드 아인혼", "철저한 재무 분석 기반 가치투자"),
    (1040273, "Third Point", "댄 로브", "이벤트 중심·행동주의 투자"),
    (1167483, "Tiger Global", "체이스 콜먼", "기술·성장주 전문"),
]


def _tag(e: ET.Element) -> str:
    return e.tag.split("}")[-1]


def _filings(cik: int) -> list[dict]:
    """최근 13F-HR 제출 목록 (최신순)."""
    d = fetch_sec(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", ttl=DAY)
    if not d:
        return []
    rec = d.get("filings", {}).get("recent", {})
    out = []
    for form, acc, rdate, fdate in zip(rec.get("form", []), rec.get("accessionNumber", []),
                                       rec.get("reportDate", []), rec.get("filingDate", [])):
        if form == "13F-HR":  # 수정본(13F-HR/A)은 제외
            out.append({"acc": acc, "report_date": rdate, "filed": fdate})
    return out


def _holdings(cik: int, acc: str) -> dict[str, dict]:
    """한 13F의 보유 내역: {cusip: {name, value, shares}} (같은 CUSIP 합산)."""
    acc_nodash = acc.replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_nodash}"
    idx = fetch_sec(f"{base}/index.json", ttl=30 * DAY)
    if not idx:
        return {}
    xmls = [i["name"] for i in idx.get("directory", {}).get("item", [])
            if i["name"].lower().endswith(".xml") and "primary_doc" not in i["name"].lower()]
    if not xmls:
        return {}
    raw = fetch_sec(f"{base}/{xmls[0]}", kind="text", ttl=90 * DAY)
    if not raw:
        return {}
    try:
        root = ET.fromstring(raw.encode("utf-8"))
    except ET.ParseError:
        return {}

    out: dict[str, dict] = {}
    for e in root.iter():
        if _tag(e) != "infoTable":
            continue
        g = {_tag(c): c for c in e}
        cusip = (g.get("cusip").text or "").strip() if g.get("cusip") is not None else ""
        if not cusip:
            continue
        # 풋/콜 옵션 포지션은 주식 보유로 보지 않는다
        pc = g.get("putCall")
        if pc is not None and (pc.text or "").strip():
            continue
        try:
            value = float(g["value"].text or 0)
        except (KeyError, TypeError, ValueError):
            value = 0.0
        shares = 0.0
        sh = g.get("shrsOrPrnAmt")
        if sh is not None:
            for c in sh:
                if _tag(c) == "sshPrnamt":
                    try:
                        shares = float(c.text or 0)
                    except ValueError:
                        pass
        h = out.setdefault(cusip, {"name": (g["nameOfIssuer"].text or "").strip(), "value": 0.0, "shares": 0.0})
        h["value"] += value
        h["shares"] += shares
    return out


_STOP = {"INC", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LIMITED", "PLC", "HOLDINGS",
         "HLDGS", "HOLDING", "GROUP", "GRP", "THE", "CLASS", "CL", "A", "B", "C", "COMMON",
         "STOCK", "SHARES", "ORDINARY", "ADR", "ADS", "NEW", "DEL", "N", "V", "SA", "NV", "AG",
         "SE", "LP", "TRUST", "DEPOSITARY", "EACH", "REPRESENTING", "ONE", "&", "AND", "OF",
         "COM", "USD", "PAR", "VALUE", "SERIES", "UNITS", "REIT", "INTERNATIONAL", "INTL"}


def _norm(name: str) -> tuple[str, ...]:
    toks = re.sub(r"[^A-Z0-9 ]", " ", name.upper()).split()
    toks = [t for t in toks if t not in _STOP]
    return tuple(toks[:2]) if toks else tuple()


def build_name_index(universe: list[dict]) -> dict[tuple, str]:
    """상장사 이름 → 티커 (시가총액이 큰 쪽 우선: 같은 이름이면 보통주/대표 클래스)."""
    idx: dict[tuple, str] = {}
    for u in universe:  # universe는 시가총액 내림차순
        key = _norm(u["name"])
        if key and key not in idx:
            idx[key] = u["symbol"]
        # 첫 토큰만으로도 색인(예: 'ALPHABET' → GOOGL). 충돌 시 큰 회사 우선.
        if key and (key[0],) not in idx:
            idx[(key[0],)] = u["symbol"]
    return idx


def resolve_ticker(issuer: str, name_index: dict) -> str | None:
    key = _norm(issuer)
    if not key:
        return None
    return name_index.get(key) or name_index.get((key[0],))


def _cutoff_date() -> str:
    import datetime as dt
    return (dt.date.today() - dt.timedelta(days=15 * 30)).isoformat()


def _fix_scale(h: dict[str, dict]) -> None:
    """2023년 이전 양식은 금액을 '천 달러'로 적는다. 13F 의무 제출 기준(1억 달러)보다
    총액이 터무니없이 작으면 천 달러 단위로 보고 1000배 한다."""
    total = sum(x["value"] for x in h.values())
    if h and total < 50_000_000:
        for x in h.values():
            x["value"] *= 1000


def guru_portfolios(name_index: dict, top_n: int = 15) -> list[dict]:
    """거장별 최신 포트폴리오 + 직전 분기 대비 변화."""
    out = []
    for cik, firm, person, blurb in GURUS:
        filings = _filings(cik)
        if not filings:
            print(f"    [warn] 13F 없음: {firm}")
            continue
        cur = _holdings(cik, filings[0]["acc"])
        prev = _holdings(cik, filings[1]["acc"]) if len(filings) > 1 else {}
        if not cur:
            continue
        # 15개월 넘게 새 공시가 없으면 더 이상 운용하지 않는 것으로 보고 제외
        if filings[0]["report_date"] < _cutoff_date():
            print(f"    [skip] 공시 오래됨 ({filings[0]['report_date']}): {firm}")
            continue
        _fix_scale(cur); _fix_scale(prev)
        total = sum(h["value"] for h in cur.values()) or 1.0

        rows = []
        for cusip, h in cur.items():
            p = prev.get(cusip)
            if p is None:
                action = "신규매수"
            elif h["shares"] > p["shares"] * 1.02:
                action = "비중확대"
            elif h["shares"] < p["shares"] * 0.98:
                action = "비중축소"
            else:
                action = "유지"
            rows.append({
                "cusip": cusip,
                "issuer": h["name"],
                "ticker": resolve_ticker(h["name"], name_index),
                "value": round(h["value"]),
                "weight": round(h["value"] / total * 100, 2),
                "action": action,
                "shares_chg_pct": None if not p or not p["shares"] else round((h["shares"] / p["shares"] - 1) * 100, 1),
            })
        rows.sort(key=lambda r: -r["value"])

        sold = [{"issuer": p["name"], "ticker": resolve_ticker(p["name"], name_index),
                 "prev_value": round(p["value"])}
                for cusip, p in prev.items() if cusip not in cur]
        sold.sort(key=lambda r: -r["prev_value"])

        out.append({
            "firm": firm, "person": person, "blurb": blurb, "cik": cik,
            "report_date": filings[0]["report_date"], "filed": filings[0]["filed"],
            "total_value": round(total),
            "n_holdings": len(cur),
            "top": rows[:top_n],
            "new_buys": [r for r in rows if r["action"] == "신규매수"][:8],
            "added": [r for r in rows if r["action"] == "비중확대"][:8],
            "reduced": [r for r in rows if r["action"] == "비중축소"][:8],
            "sold_out": sold[:8],
        })
        print(f"    13F {firm}: {len(cur)}종목, 기준일 {filings[0]['report_date']}")
    return out
