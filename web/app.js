/* 미국 주식 나침반 — 화면 로직 (외부 라이브러리 없음) */
(() => {
"use strict";
const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

/* ---------- 포맷 ---------- */
const isNum = v => typeof v === "number" && isFinite(v);
const fNum = (v, d = 1) => isNum(v) ? v.toLocaleString("en-US", {minimumFractionDigits: d, maximumFractionDigits: d}) : "–";
const fPct = (v, d = 1, sign = true) => isNum(v) ? (sign && v > 0 ? "+" : "") + v.toFixed(d) + "%" : "–";
const fRatioPct = (v, d = 0) => isNum(v) ? (v > 0 ? "+" : "") + (v * 100).toFixed(d) + "%" : "–";
const fX = (v, d = 1) => isNum(v) ? v.toFixed(d) + "배" : "–";
const fCap = v => !isNum(v) ? "–" : v >= 1e12 ? (v / 1e12).toFixed(1) + "조$" : v >= 1e8 ? Math.round(v / 1e8).toLocaleString() + "억$" : (v / 1e6).toFixed(0) + "백만$";
const fPrice = v => isNum(v) ? "$" + v.toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2}) : "–";
const ud = v => !isNum(v) ? "" : v > 0 ? "up" : v < 0 ? "down" : "";
const arrow = v => !isNum(v) ? "" : v > 0 ? "▲ " : v < 0 ? "▼ " : "";

/* 점수 → 상태색 */
const band = s => s >= 65 ? "good" : s >= 50 ? "warn" : s >= 35 ? "serious" : "crit";
const bandColor = s => `var(--${band(s)})`;
const gradeColor = g => ({A: "var(--good)", B: "var(--accent)", C: "var(--warn)", D: "var(--serious)"}[g] || "var(--text-3)");

/* ---------- 스파크라인 (SVG) ---------- */
const sparkStore = new Map(); let sparkId = 0;
function spark(values, {h = 56, stroke = "var(--spark)", fill = true, big = false, labels = null} = {}) {
  const v = (values || []).filter(isNum);
  if (v.length < 2) return `<svg viewBox="0 0 100 ${h}"></svg>`;
  const w = 300, pad = 3, min = Math.min(...v), max = Math.max(...v), span = (max - min) || 1;
  const x = i => pad + (i / (v.length - 1)) * (w - pad * 2);
  const y = val => h - pad - ((val - min) / span) * (h - pad * 2);
  const pts = v.map((val, i) => `${x(i).toFixed(1)},${y(val).toFixed(1)}`).join(" ");
  const id = "sp" + (++sparkId); sparkStore.set(id, {v, labels});
  const upCol = v[v.length - 1] >= v[0] ? "var(--up)" : "var(--down)";
  const col = stroke === "auto" ? upCol : stroke;
  return `<svg class="${big ? "sparkbig" : "spark"}" data-spark="${id}" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
    ${fill ? `<polygon points="${x(0)},${h} ${pts} ${x(v.length - 1)},${h}" fill="${col}" opacity=".10"/>` : ""}
    <polyline points="${pts}" fill="none" stroke="${col}" stroke-width="2" vector-effect="non-scaling-stroke" stroke-linejoin="round"/>
    <circle cx="${x(v.length - 1)}" cy="${y(v[v.length - 1])}" r="3" fill="${col}"/>
    <line class="xh" x1="0" x2="0" y1="0" y2="${h}" stroke="var(--text-3)" stroke-width="1" vector-effect="non-scaling-stroke" style="display:none"/>
  </svg>`;
}
/* 스파크라인 호버: 세로선 + 툴팁 */
const tip = $("#tip");
document.addEventListener("mousemove", e => {
  const svg = e.target.closest("svg[data-spark]");
  if (!svg) { tip.style.display = "none"; document.querySelectorAll("svg[data-spark] .xh").forEach(l => l.style.display = "none"); return; }
  const d = sparkStore.get(svg.dataset.spark); if (!d) return;
  const r = svg.getBoundingClientRect(), fr = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width));
  const i = Math.round(fr * (d.v.length - 1)); const xh = svg.querySelector(".xh");
  const xv = 3 + fr * 294; xh.setAttribute("x1", xv); xh.setAttribute("x2", xv); xh.style.display = "";
  const ago = d.v.length - 1 - i;
  const lab = d.labels ? d.labels[i] : (ago === 0 ? "최근" : `${ago}거래일 전`);
  tip.innerHTML = `${esc(lab)} · <b>${fNum(d.v[i], d.v[i] > 1000 ? 0 : 2)}</b>`;
  tip.style.display = "block"; tip.style.left = (e.clientX + 12) + "px"; tip.style.top = (e.clientY - 28) + "px";
});

/* ---------- 게이지 ---------- */
function gauge(score, color) {
  const r = 110, cx = 140, cy = 130, a0 = Math.PI, a1 = Math.PI * (1 - score / 100);
  const arc = (from, to, col, w) => {
    const p = a => [cx + r * Math.cos(a), cy - r * Math.sin(a)];
    const [x0, y0] = p(from), [x1, y1] = p(to), large = (from - to) > Math.PI ? 1 : 0;
    return `<path d="M${x0.toFixed(1)},${y0.toFixed(1)} A${r},${r} 0 ${large} 1 ${x1.toFixed(1)},${y1.toFixed(1)}" fill="none" stroke="${col}" stroke-width="${w}" stroke-linecap="round"/>`;
  };
  return `<svg class="gauge" viewBox="0 0 280 150">${arc(a0, 0.001, "var(--surface-2)", 18)}${score > 0 ? arc(a0, a1 + 0.0001, color, 18) : ""}</svg>`;
}
const meter = (s, h) => `<div class="meter"${h ? ` style="height:${h}px"` : ""}><i style="width:${Math.max(2, s)}%;background:${bandColor(s)}"></i></div>`;

/* ---------- 렌더: 시장 점수 ---------- */
function renderMarket(m) {
  return `<section id="market"><h2>오늘의 시장 점수</h2>
  <p class="lead">100점에 가까울수록 "주식을 적극적으로 사도 되는 환경", 0점에 가까울수록 "현금을 들고 기다릴 환경"입니다. 각 항목을 누르면 이유가 나옵니다.</p>
  <div class="hero">
    <div class="card gauge-card">${gauge(m.score, m.color)}
      <div class="hero-num">${m.score}<small>/ 100</small></div>
      <div class="verdict" style="background:${m.color}">${esc(m.verdict)}</div>
      <p class="advice">${esc(m.advice)}</p>
      <div class="scale"><span>0 현금 보유</span><span>50 중립</span><span>100 적극 매수</span></div>
    </div>
    <div class="card"><div class="areas">
      ${m.areas.map(a => `<div class="area" data-k="${a.key}">
        <div class="lbl">${esc(a.label)}<small>비중 ${a.weight}%</small></div>${meter(a.score)}
        <div class="val num" style="color:${bandColor(a.score)}">${a.score}</div>
        <div class="area-why"><b>${esc(a.desc)}</b><br>${esc(a.why)}</div></div>`).join("")}
    </div><div class="summary-line">${esc(m.summary)}</div></div>
  </div></section>`;
}

/* ---------- 렌더: 지수 ---------- */
function renderIndexes(ix, sectors) {
  const cards = ix.map(i => {
    const c = i.change_pct, cls = i.inverse ? (c > 0 ? "down" : c < 0 ? "up" : "") : ud(c);
    return `<div class="card idx"><div class="top"><div class="name">${esc(i.label)}<small>${esc(i.symbol)}</small></div>
      <div class="chg ${cls}">${arrow(c)}${fPct(c, 2)}</div></div>
      <div class="price num">${fNum(i.price, i.price > 1000 ? 0 : 2)}</div>
      ${spark(i.series, {stroke: "auto"})}
      <div class="foot"><span>${esc(i.desc)}</span><span>1년 ${fPct(i.ret_1y, 1)}</span></div></div>`;
  }).join("");
  const sec = sectors.map(s => {
    const c = s.change_pct, bg = !isNum(c) ? "var(--surface-2)" : c >= 0 ? `color-mix(in srgb, var(--good) ${Math.min(60, Math.abs(c) * 25)}%, var(--surface))` : `color-mix(in srgb, var(--crit) ${Math.min(60, Math.abs(c) * 25)}%, var(--surface))`;
    return `<div class="sec" style="background:${bg}"><small>${esc(s.label)}</small><b class="${ud(c)}">${fPct(c, 1)}</b><small>3개월 ${fPct(s.ret_3m, 0)}</small></div>`;
  }).join("");
  return `<section id="index"><h2>주요 지수 한눈에</h2>
  <p class="lead">오늘 하루 변동과 최근 1년 흐름입니다. <span class="up">▲ 초록 = 상승</span>, <span class="down">▼ 빨강 = 하락</span> (미국식). 선 위에 마우스를 올리면 값이 보입니다.</p>
  <div class="grid g3">${cards}</div>
  <h2 style="margin-top:18px;font-size:15px">섹터별 오늘 등락</h2><div class="sectors">${sec}</div></section>`;
}

/* ---------- 렌더: 거시 ---------- */
function renderMacro(r, mac, sen, rh) {
  const un = mac.unemployment || {}, pay = mac.payrolls || {}, cpi = mac.cpi || {};
  const polTxt = !isNum(r.m3_chg_6m) ? "–" : r.m3_chg_6m < -0.15 ? "금리 인하 중" : r.m3_chg_6m > 0.15 ? "금리 인상 중" : "동결 수준";
  const polCls = !isNum(r.m3_chg_6m) ? "warn" : r.m3_chg_6m < -0.15 ? "good" : r.m3_chg_6m > 0.15 ? "crit" : "warn";
  const curveCls = !isNum(r.spread_10y_2y) ? "warn" : r.spread_10y_2y < 0 ? "crit" : r.spread_10y_2y < 0.3 ? "warn" : "good";
  const unCls = un.rise_from_12m_low >= 0.5 ? "crit" : un.rise_from_12m_low >= 0.3 ? "serious" : "good";
  const cpiCls = cpi.yoy_pct > 4 ? "crit" : cpi.yoy_pct > 3 ? "warn" : "good";
  const y10s = (rh || []).map(x => x.y10), y10l = (rh || []).map(x => x.date);
  const fng = sen.score ?? 50;
  return `<section id="macro"><h2>금리 · 경기 · 투자 심리</h2>
  <p class="lead">주식 시장 바깥의 날씨입니다. 금리가 내려가고, 고용이 탄탄하고, 물가가 안정되면 주식에 유리합니다.</p>
  <div class="grid g4">
    <div class="card stat"><div class="lbl">정책 금리 방향 <span class="tiny">(3개월 국채)</span></div>
      <div class="v num">${fNum(r.m3, 2)}<small>%</small></div>
      <div><span class="pill ${polCls}">${polTxt}</span> <span class="sub">6개월 전 대비 ${fPct(r.m3_chg_6m, 2)}p</span></div></div>
    <div class="card stat"><div class="lbl">10년 국채 금리 <span class="tiny">(주식의 경쟁자)</span></div>
      <div class="v num">${fNum(r.y10, 2)}<small>%</small></div>
      <div class="sub">3개월 전 대비 ${fPct(r.y10_chg_3m, 2)}p · ${esc(r.date || "")}</div>
      ${spark(y10s, {h: 40, stroke: "var(--spark)", labels: y10l})}</div>
    <div class="card stat"><div class="lbl">장단기 금리차 <span class="tiny">(10년 − 2년)</span></div>
      <div class="v num">${fPct(r.spread_10y_2y, 2)}<small>p</small></div>
      <div><span class="pill ${curveCls}">${r.spread_10y_2y < 0 ? "역전 (침체 경고)" : r.spread_10y_2y < 0.3 ? "평탄" : "정상"}</span></div>
      <div class="sub">마이너스(역전)면 역사적으로 1~2년 내 침체가 잦았습니다</div></div>
    <div class="card stat"><div class="lbl">실업률 <span class="tiny">${esc(un.period || "")}</span></div>
      <div class="v num">${fNum(un.value, 1)}<small>%</small></div>
      <div><span class="pill ${unCls}">1년 최저 대비 ${fPct(un.rise_from_12m_low, 1)}p</span></div>
      <div class="sub">0.5%p 이상 오르면 침체 신호(삼의 법칙)</div></div>
    <div class="card stat"><div class="lbl">월평균 고용 증가 <span class="tiny">최근 3개월</span></div>
      <div class="v num">${fNum(pay.avg_monthly_change_3m, 0)}<small>천 명</small></div>
      <div class="sub">10만 명 이상이면 건강, 마이너스면 위험</div></div>
    <div class="card stat"><div class="lbl">물가 상승률 <span class="tiny">CPI ${esc(cpi.period || "")}</span></div>
      <div class="v num">${fNum(cpi.yoy_pct, 1)}<small>%</small></div>
      <div><span class="pill ${cpiCls}">${cpi.yoy_pct > 4 ? "높음 — 금리 인하 어려움" : cpi.yoy_pct > 3 ? "목표(2%)보다 높음" : "안정"}</span></div></div>
    <div class="card stat" style="grid-column: span 2"><div class="lbl">수익률 곡선 <span class="tiny">만기별 국채 금리 ${esc(r.date || "")}</span></div>
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:6px">${Object.entries(r.latest || {}).map(([k, v]) => `<div class="mini" style="display:block"><div style="min-width:52px"><small>${k}</small><b class="num">${fNum(v, 2)}%</b></div></div>`).join("")}</div>
      <div class="sub">보통 만기가 길수록 금리가 높아야 정상입니다. 짧은 쪽이 더 높으면 '역전'.</div></div>
  </div>
  <div class="card fng" style="margin-top:12px">
    <div style="text-align:center"><div class="lbl muted" style="font-size:13px">CNN 공포 · 탐욕 지수</div>
      <div class="hero-num" style="margin-top:4px;font-size:48px">${Math.round(fng)}</div>
      <div><span class="pill ${fng < 25 ? "crit" : fng < 45 ? "serious" : fng < 55 ? "warn" : "good"}">${esc(({"extreme fear": "극도의 공포", fear: "공포", neutral: "중립", greed: "탐욕", "extreme greed": "극도의 탐욕"})[sen.rating] || sen.rating || "")}</span></div>
      <div class="sub" style="margin-top:6px">1주 전 ${fNum(sen.prev_week, 0)} · 1달 전 ${fNum(sen.prev_month, 0)} · 1년 전 ${fNum(sen.prev_year, 0)}</div>
      <div class="sub" style="margin-top:6px">0 = 모두가 공포, 100 = 모두가 탐욕.<br>역발상 투자자는 공포일 때 사고 탐욕일 때 조심합니다.</div></div>
    <div class="fng-comps">${(sen.components || []).map(c => `<div class="fng-comp" title="${esc(c.desc)}"><span>${esc(c.label)}</span>${meter(c.score, 8)}<b class="num" style="text-align:right">${Math.round(c.score)}</b></div>`).join("")}
      <div class="tiny">각 지표 0~100, 높을수록 '탐욕(낙관)'. 항목에 마우스를 올리면 설명이 보입니다.</div></div>
  </div></section>`;
}

/* ---------- 렌더: 추천 종목 ---------- */
function stockCard(s, rank) {
  const t = s.target || {};
  return `<div class="card stock" data-sym="${esc(s.symbol)}">
    <div class="head"><div class="badge" style="background:${gradeColor(s.grade)}">${s.score}<small>${s.grade}등급</small></div>
      <div class="title"><b>${esc(s.name)}</b><span>${esc(s.symbol)} · ${esc(s.sector || "")} · 시총 ${fCap(s.market_cap)}</span></div>
      <div class="px"><b class="num">${fPrice(s.price)}</b><span class="${ud(s.change_pct)}">${arrow(s.change_pct)}${fPct(s.change_pct, 2)}</span></div></div>
    <ul class="reasons">${s.reasons.good.map(r => `<li>${esc(r)}</li>`).join("")}${s.reasons.bad.map(r => `<li class="bad">${esc(r)}</li>`).join("")}</ul>
    <div class="mini">
      <div><small>PER</small><b class="num">${fX(s.per, 0)}</b></div>
      <div><small>매출성장(3년)</small><b class="num">${fRatioPct(s.rev_cagr3)}</b></div>
      <div><small>부채/자본</small><b class="num">${fX(s.debt_to_equity, 1)}</b></div>
      <div><small>FCF 마진</small><b class="num">${fRatioPct(s.fcf_margin)}</b></div>
      <div><small>목표가 여유</small><b class="num ${ud(s.target_upside)}">${fRatioPct(s.target_upside)}</b></div>
    </div>
    ${spark(s.price_series, {h: 40, stroke: "auto"})}
    <div class="rank">#${rank} · 최근 6개월 주가 ${fRatioPct(s.ret_6m)} · 월가 목표 ${fPrice(t.mean)} (${t.analysts || 0}명)</div>
  </div>`;
}
function renderPicks(recs, bySym, m) {
  const regime = m.score < 40 ? "약세 환경이라 <b>재무 안정·현금흐름</b>을 더 무겁게 봤습니다." : m.score >= 70 ? "강세 환경이라 <b>성장·주가 흐름</b>을 더 무겁게 봤습니다." : "중립 환경이라 가치·성장·안정을 고르게 봤습니다.";
  return `<section id="picks"><h2>상승 가능성이 높은 종목 TOP ${recs.length}</h2>
  <p class="lead">시가총액 상위 종목을 가치·성장·재무 안정·현금흐름·월가 목표주가·주가 흐름·거장 보유 7가지로 채점했습니다. ${regime} 섹터 쏠림을 막기 위해 섹터당 최대 4개입니다. 카드를 누르면 자세한 설명이 나옵니다.</p>
  <div class="stocks">${recs.map((sym, i) => stockCard(bySym[sym], i + 1)).join("")}</div></section>`;
}

/* ---------- 렌더: ETF ---------- */
let etfCat = "추천";
const ALLOC_COLOR = {"주식": "var(--accent)", "채권": "#1baf7a", "금": "#eda100"};
function etfCard(e, rank) {
  return `<div class="card etf" data-etf="${esc(e.symbol)}">
    <div class="head"><div class="badge" style="background:${gradeColor(e.grade)}">${e.score}<small>${e.grade}</small></div>
      <div class="title" style="flex:1;min-width:0"><b>${esc(e.name)} <span class="cat-tag">${esc(e.category)}</span></b><span>${esc(e.symbol)}${rank ? ` · #${rank}` : ""}</span></div>
      <div class="px" style="text-align:right"><b class="num" style="display:block">${fPrice(e.price)}</b><span class="${ud(e.change_pct)}" style="font-size:12px;font-weight:600">${arrow(e.change_pct)}${fPct(e.change_pct, 2)}</span></div></div>
    <div class="desc">${esc(e.desc)}</div>
    <ul class="reasons">${e.reasons.good.slice(0, 2).map(r => `<li>${esc(r)}</li>`).join("")}${e.reasons.bad.slice(0, 1).map(r => `<li class="bad">${esc(r)}</li>`).join("")}</ul>
    <div class="mini">
      <div><small>1년</small><b class="num ${ud(e.ret_1y)}">${fRatioPct(e.ret_1y)}</b></div>
      <div><small>3개월</small><b class="num ${ud(e.ret_3m)}">${fRatioPct(e.ret_3m)}</b></div>
      <div><small>변동성</small><b class="num">${isNum(e.volatility) ? e.volatility.toFixed(0) + "%" : "–"}</b></div>
      <div><small>연 보수</small><b class="num">${isNum(e.expense_ratio) ? e.expense_ratio.toFixed(2) + "%" : "–"}</b></div>
    </div>
    ${spark(e.price_series, {h: 36, stroke: "auto"})}</div>`;
}
function renderEtf(etfs, cats, alloc, m) {
  if (!etfs || !etfs.length) return "";
  const tabs = ["추천", ...cats].map(c => `<button class="btn ${c === etfCat ? "active" : ""}" data-etfcat="${esc(c)}">${esc(c)}</button>`).join("");
  const list = etfCat === "추천" ? etfs.slice(0, 9) : etfs.filter(e => e.category === etfCat);
  const bar = alloc.mix.map(x => `<div style="width:${x.pct}%;background:${ALLOC_COLOR[x.asset]}">${x.asset} ${x.pct}%</div>`).join("");
  const legend = alloc.mix.map(x => `<div><i style="background:${ALLOC_COLOR[x.asset]}"></i><b>${x.asset} ${x.pct}%</b> — 예: ${x.etfs.map(s => `<span class="chip" data-etf="${s}">${s}</span>`).join(" ")}</div>`).join("");
  return `<section id="etf"><h2>ETF — 한 번에 여러 종목을 사는 법</h2>
  <p class="lead">ETF는 수십~수천 개 종목을 묶은 상품이라 한 종목이 망해도 타격이 작습니다. 초보자는 개별 종목보다 ETF로 시작하는 것이 보통 안전합니다. 대표 ETF ${etfs.length}개를 수익 흐름·추세·위험·비용으로 채점했습니다.</p>
  <div class="card alloc" style="margin-bottom:14px">
    <div><div style="font-weight:700;margin-bottom:4px">시장 점수 ${m.score}점일 때의 배분 예시</div><div class="muted" style="font-size:13px">${esc(alloc.note)}</div>
      <div class="tiny" style="margin-top:6px">교육용 예시입니다. 나이·목표·기간에 따라 달라져야 하고, 투자 조언이 아닙니다.</div></div>
    <div><div class="alloc-bar">${bar}</div><div class="alloc-legend">${legend}</div></div>
  </div>
  <div class="guru-tabs">${tabs}</div>
  <div class="etf-grid">${list.map((e, i) => etfCard(e, etfCat === "추천" ? i + 1 : 0)).join("")}</div></section>`;
}
function openEtf(e) {
  const AL = {momentum: "수익 흐름 (1·3·6·12개월)", trend: "추세 (200일선)", risk: "위험 (변동성·최대낙폭)", cost: "비용 (보수율)"};
  const kv = [["현재가", fPrice(e.price)], ["1개월", fRatioPct(e.ret_1m, 1)], ["3개월", fRatioPct(e.ret_3m, 1)], ["6개월", fRatioPct(e.ret_6m, 1)], ["1년", fRatioPct(e.ret_1y, 1)],
    ["200일선 대비", fPct(e.dist_200dma_pct, 1)], ["52주 고점 대비", fPct(e.week52_from_high, 1)], ["연 변동성", isNum(e.volatility) ? e.volatility.toFixed(1) + "%" : "–"],
    ["1년 최대낙폭", fPct(e.max_drawdown, 1)], ["연 보수율", isNum(e.expense_ratio) ? e.expense_ratio.toFixed(2) + "%" : "–"], ["베타 (시장 대비 민감도)", isNum(e.beta) ? e.beta.toFixed(2) : "–"],
    ["배당수익률", isNum(e.dividend_yield) ? e.dividend_yield.toFixed(2) + "%" : "자료 없음"], ["시가총액", fCap(e.aum)]];
  $("#modalBody").innerHTML = `
    <div style="display:flex;gap:14px;align-items:center"><div class="badge" style="background:${gradeColor(e.grade)}">${e.score}<small>${e.grade}등급</small></div>
      <div><h3>${esc(e.name)} <span class="muted" style="font-size:15px;font-weight:500">${esc(e.symbol)}</span> <span class="cat-tag">${esc(e.category)}</span></h3><div class="sub">${esc(e.desc)}</div></div></div>
    <ul class="reasons" style="margin-top:12px">${e.reasons.good.map(r => `<li>${esc(r)}</li>`).join("")}${e.reasons.bad.map(r => `<li class="bad">${esc(r)}</li>`).join("")}</ul>
    <h4>영역 점수 (대표 ETF ${DATA.etfs.length}개 내 상대 순위)</h4>
    <div class="areas">${Object.entries(e.areas).map(([k, v]) => `<div class="area"><div class="lbl" style="font-size:13px">${AL[k]}</div>${v == null ? '<div class="tiny">–</div>' : meter(v)}<div class="val num" style="color:${v == null ? "var(--text-3)" : bandColor(v)}">${v ?? "–"}</div></div>`).join("")}</div>
    <h4>최근 1년 가격</h4>${spark(e.price_series, {h: 120, stroke: "auto", big: true})}
    <h4>지표</h4><div class="kv">${kv.map(([k, v]) => `<div><span>${k}</span><b>${v}</b></div>`).join("")}</div>`;
  $("#modal").classList.add("show");
}

/* ---------- 렌더: 거장 ---------- */
let guruIdx = 0;
function renderGurus(gs) {
  if (!gs.length) return "";
  const g = gs[guruIdx];
  const tabs = gs.map((x, i) => `<button class="btn ${i === guruIdx ? "active" : ""}" data-guru="${i}">${esc(x.person)}</button>`).join("");
  const uniq = arr => { const seen = new Set(); return arr.filter(r => { const k = r.ticker || r.issuer; if (seen.has(k)) return false; seen.add(k); return true; }); };
  const chips = (arr0, cls, label) => { const arr = uniq(arr0); return arr.length ? `<div style="margin-top:8px"><span class="tiny">${label}</span><div class="chips">${arr.map(r => `<span class="chip ${cls}" data-sym="${esc(r.ticker || "")}" title="${esc(r.issuer)}">${esc(r.ticker || r.issuer.slice(0, 14))}${isNum(r.shares_chg_pct) ? ` <span class="tiny">${fPct(r.shares_chg_pct, 0)}</span>` : ""}</span>`).join("")}</div></div>` : ""; };
  const maxW = Math.max(...g.top.map(r => r.weight), 1);
  return `<section id="gurus"><h2>월가 거장들은 무엇을 들고 있을까</h2>
  <p class="lead">SEC에 제출된 13F 공시(분기별)로 본 실제 보유 종목입니다. 피터 린치는 은퇴해 공시가 없지만, 그의 'PEG 1 미만' 기준은 종목 점수의 '가치' 항목에 들어 있습니다.</p>
  <div class="guru-tabs">${tabs}</div>
  <div class="card"><div class="guru-head"><h3>${esc(g.person)}</h3><span class="muted">${esc(g.firm)}</span><span class="blurb">${esc(g.blurb)}</span></div>
    <div class="tiny" style="margin:4px 0 12px">기준일 ${esc(g.report_date)} (제출 ${esc(g.filed)}) · 미국 주식 ${fCap(g.total_value)} · ${g.n_holdings}종목</div>
    <div class="grid g2" style="gap:20px"><div>
      <div class="tiny" style="margin-bottom:4px">보유 비중 상위</div>
      ${g.top.slice(0, 12).map(r => `<div class="hold"><span class="t" ${r.ticker ? `data-sym="${esc(r.ticker)}" style="cursor:pointer;color:var(--accent)"` : ""}>${esc(r.ticker || "?")}</span>
        <div><div class="tiny" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(r.issuer)}</div><div class="meter"><i style="width:${(r.weight / maxW * 100).toFixed(0)}%;background:var(--accent)"></i></div></div>
        <span class="w num">${r.weight.toFixed(1)}%</span><span class="act ${esc(r.action)}">${esc(r.action)}</span></div>`).join("")}
    </div><div>
      <div class="tiny">직전 분기 대비 변화</div>
      ${chips(g.new_buys, "buy", "🟢 신규 매수")}${chips(g.added, "add", "🔵 비중 확대")}${chips(g.reduced, "cut", "🟡 비중 축소")}${chips(g.sold_out, "sell", "🔴 전량 매도")}
      ${!(g.new_buys.length || g.added.length || g.reduced.length || g.sold_out.length) ? '<div class="muted" style="margin-top:8px">이번 분기엔 변화가 없었습니다.</div>' : ""}
    </div></div></div></section>`;
}

/* ---------- 렌더: 전체 테이블 ---------- */
const COLS = [
  ["score", "점수", s => `<span class="sc" style="background:${gradeColor(s.grade)}">${s.score}</span>`],
  ["symbol", "티커", s => `<b>${esc(s.symbol)}</b>`],
  ["name", "이름", s => esc(s.name)],
  ["sector", "섹터", s => esc(s.sector || "–")],
  ["market_cap", "시총", s => fCap(s.market_cap)],
  ["change_pct", "오늘", s => `<span class="${ud(s.change_pct)}">${fPct(s.change_pct, 1)}</span>`],
  ["per", "PER", s => fX(s.per, 0)],
  ["peg", "PEG", s => isNum(s.peg) ? s.peg.toFixed(1) : "–"],
  ["rev_cagr3", "매출성장", s => fRatioPct(s.rev_cagr3)],
  ["debt_to_equity", "부채/자본", s => fX(s.debt_to_equity, 1)],
  ["fcf_margin", "FCF마진", s => fRatioPct(s.fcf_margin)],
  ["target_upside", "목표가여유", s => `<span class="${ud(s.target_upside)}">${fRatioPct(s.target_upside)}</span>`],
  ["ret_6m", "6개월", s => `<span class="${ud(s.ret_6m)}">${fRatioPct(s.ret_6m)}</span>`],
  ["gurus", "거장", s => s.gurus.length ? `${s.gurus.length}명` : ""],
];
let sortKey = "score", sortAsc = false, query = "", sectorF = "";
function renderTable(stocks) {
  const sectors = [...new Set(stocks.map(s => s.sector).filter(Boolean))].sort();
  let rows = stocks.filter(s => (!sectorF || s.sector === sectorF) && (!query || (s.symbol + " " + s.name).toLowerCase().includes(query)));
  rows.sort((a, b) => {
    let va = a[sortKey], vb = b[sortKey];
    if (sortKey === "gurus") { va = va.length; vb = vb.length; }
    if (va == null) return 1; if (vb == null) return -1;
    if (typeof va === "string") return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
    return sortAsc ? va - vb : vb - va;
  });
  return `<section id="all"><h2>분석한 전체 종목 (${stocks.length}개)</h2>
  <p class="lead">열 제목을 누르면 정렬됩니다. 행을 누르면 상세가 열립니다.</p>
  <div class="card"><div class="table-tools">
    <input id="q" placeholder="티커 또는 회사명 검색" value="${esc(query)}">
    <select id="sectorF"><option value="">모든 섹터</option>${sectors.map(x => `<option ${x === sectorF ? "selected" : ""}>${esc(x)}</option>`).join("")}</select>
    <span class="tiny">${rows.length}개 표시</span></div>
  <div class="tbl-wrap"><table><thead><tr>${COLS.map(([k, l]) => `<th data-k="${k}" class="${k === sortKey ? "s" + (sortAsc ? " asc" : "") : ""}">${l}</th>`).join("")}</tr></thead>
  <tbody>${rows.map(s => `<tr class="row num" data-sym="${esc(s.symbol)}">${COLS.map(([, , f]) => `<td>${f(s)}</td>`).join("")}</tr>`).join("")}</tbody></table></div></div></section>`;
}

/* ---------- 용어 ---------- */
const GLOSS = [
  ["PER (주가수익비율)", "주가가 1년 이익의 몇 배인지. 15배면 '지금 이익이 유지될 때 15년이면 본전'. 낮을수록 싸지만, 성장이 없으면 싼 이유가 있습니다."],
  ["PEG", "PER ÷ 이익성장률(%). 피터 린치가 애용한 지표로 1 미만이면 '성장에 비해 싸다'고 봅니다."],
  ["P/FCF", "시가총액 ÷ 잉여현금흐름. PER과 비슷하지만 '장부상 이익' 대신 '실제 남은 현금'으로 계산해 더 솔직합니다."],
  ["부채/자본", "빚이 자기자본의 몇 배인지. 1 아래면 안정적, 2 넘으면 금리 오를 때 힘들어집니다. (은행·보험은 사업 특성상 높아 따로 봅니다)"],
  ["유동비율", "1년 안에 갚을 빚 대비 1년 안에 현금화할 자산. 1 아래면 단기 자금 압박 가능."],
  ["잉여현금흐름 (FCF)", "영업으로 번 현금에서 설비투자를 빼고 진짜 남은 돈. 배당·자사주매입·빚 상환의 원천입니다."],
  ["FCF 마진", "매출 100원 중 잉여현금으로 남는 돈. 20% 넘으면 매우 우수."],
  ["매출 성장률(3년 CAGR)", "최근 3년간 매출이 매년 평균 몇 % 늘었는지."],
  ["ROE", "자기자본으로 1년에 몇 % 벌었는지. 버핏이 가장 중시한 지표 중 하나(15% 이상 선호)."],
  ["목표가 여유", "월가 애널리스트 평균 목표주가가 현재가보다 몇 % 위인지. 참고용 — 애널리스트는 대체로 낙관적입니다."],
  ["200일선", "최근 200거래일 평균 주가. 이 위에 있으면 장기 상승 추세로 봅니다."],
  ["VIX", "'공포지수'. S&P500 옵션으로 계산한 예상 변동성. 20 아래 평온, 30 위 공포."],
  ["장단기 금리차", "10년물 − 2년물 금리. 마이너스(역전)는 역사적으로 침체 1~2년 전에 자주 나타났습니다."],
  ["삼의 법칙 (Sahm rule)", "실업률 3개월 평균이 최근 1년 최저보다 0.5%p 이상 오르면 침체가 시작됐을 확률이 높다는 경험칙."],
  ["ETF", "여러 종목을 묶어 주식처럼 사고파는 펀드. VOO 한 주를 사면 미국 500대 기업을 조금씩 다 갖는 셈. 연 보수(0.03~0.75%)가 자동으로 빠집니다."],
  ["변동성 (연)", "1년 동안 가격이 평균적으로 얼마나 출렁이는지. 채권 5%, S&P500 15%, 반도체 35% 정도. 낮을수록 마음 편합니다."],
  ["최대낙폭 (MDD)", "최근 1년 중 고점에서 저점까지 가장 크게 떨어진 폭. -30%면 고점에 샀을 때 한때 30% 손실을 봤다는 뜻."],
  ["13F", "1억 달러 이상 굴리는 운용사가 분기마다 SEC에 내는 미국 주식 보유 내역. 분기 끝나고 45일 뒤에 공개돼 시차가 있습니다."],
  ["공포·탐욕 지수", "CNN이 7가지 지표로 만든 시장 심리. 극단적 공포는 역발상 매수 기회, 극단적 탐욕은 주의 신호로 봅니다."],
];
const renderGloss = () => `<section id="gloss"><details open><summary>📘 용어 사전 — 초보자를 위한 쉬운 설명</summary><div class="gloss">${GLOSS.map(([k, v]) => `<div><b>${k}</b><p>${v}</p></div>`).join("")}</div></details></section>`;

/* ---------- 상세 모달 ---------- */
const AREA_LABEL = {value: "가치", growth: "성장", safety: "재무 안정", cashflow: "현금흐름", analyst: "월가 목표주가", momentum: "주가 흐름", guru: "거장 보유"};
function openStock(s) {
  const t = s.target;
  let tbar = "";
  if (t && isNum(t.low) && isNum(t.high) && isNum(s.price)) {
    const lo = Math.min(t.low, s.price) * 0.97, hi = Math.max(t.high, s.price) * 1.03, p = v => ((v - lo) / (hi - lo) * 100).toFixed(1) + "%";
    tbar = `<h4>월가 목표주가 범위 (애널리스트 ${t.analysts}명: 매수 ${t.buy} · 보유 ${t.hold} · 매도 ${t.sell})</h4>
    <div class="target-bar"><div class="track"></div><div class="rng" style="left:${p(t.low)};width:calc(${p(t.high)} - ${p(t.low)})"></div>
      <div class="mk" style="left:${p(t.low)};background:var(--text-3)"></div><div class="lb" style="left:${p(t.low)}">최저 ${fPrice(t.low)}</div>
      <div class="mk" style="left:${p(t.mean)};background:var(--accent)"></div><div class="lb" style="left:${p(t.mean)}">평균 ${fPrice(t.mean)}</div>
      <div class="mk" style="left:${p(t.high)};background:var(--text-3)"></div><div class="lb" style="left:${p(t.high)}">최고 ${fPrice(t.high)}</div>
      <div class="mk" style="left:${p(s.price)};background:var(--crit);height:26px;top:4px"></div></div>
    <div class="tiny" style="margin-top:10px">빨간 선 = 현재가 ${fPrice(s.price)} → 평균 목표가까지 <b class="${ud(s.target_upside)}">${fRatioPct(s.target_upside)}</b></div>`;
  }
  const yrs = (s.revenue_series || []).length;
  const kv = [
    ["PER", fX(s.per, 1), "낮을수록 저렴"], ["PEG", isNum(s.peg) ? s.peg.toFixed(2) : "–", "1 미만이면 성장 대비 저렴"],
    ["P/FCF", fX(s.p_fcf, 1), "현금 기준 PER"], ["배당수익률", isNum(s.dividend_yield) ? s.dividend_yield.toFixed(2) + "%" : "–", ""],
    ["매출 성장(최근 1년)", fRatioPct(s.rev_growth, 1), ""], ["매출 성장(3년 연평균)", fRatioPct(s.rev_cagr3, 1), ""],
    ["순이익 성장(최근 1년)", fRatioPct(s.eps_growth, 1), ""], ["순이익 성장(3년 연평균)", fRatioPct(s.ni_cagr3, 1), ""],
    ["영업이익률", fRatioPct(s.op_margin, 1), ""], ["순이익률", fRatioPct(s.net_margin, 1), ""], ["ROE", fRatioPct(s.roe, 1), "15% 이상 우수"],
    ["부채/자본", fX(s.debt_to_equity, 2), "1 미만 안정"], ["유동비율", fX(s.current_ratio, 2), "1 이상 안정"],
    ["순부채/FCF", fX(s.net_debt_to_fcf, 1), "몇 년치 현금으로 빚을 갚나 (음수=순현금)"],
    ["현금성 자산", fCap(s.cash), ""], ["총 차입금", fCap(s.debt), ""],
    ["영업현금흐름", fCap(s.ocf), ""], ["잉여현금흐름(FCF)", fCap(s.fcf), ""], ["FCF 마진", fRatioPct(s.fcf_margin, 1), ""],
    ["현금전환(OCF/순이익)", fX(s.ocf_to_ni, 2), "1 이상이면 이익이 진짜 현금"], ["FCF 흑자 연도", `${s.fcf_positive_years}/${s.fcf_years}년`, ""],
    ["52주 범위", `${fPrice(s.week52_low)} ~ ${fPrice(s.week52_high)}`, ""], ["200일선 대비", fPct(s.dist_200dma_pct, 1), "플러스면 장기 상승 추세"],
    ["6개월 수익률", fRatioPct(s.ret_6m, 1), ""], ["1년 수익률", fRatioPct(s.ret_1y, 1), ""],
  ];
  $("#modalBody").innerHTML = `
    <div style="display:flex;gap:14px;align-items:center"><div class="badge" style="background:${gradeColor(s.grade)}">${s.score}<small>${s.grade}등급</small></div>
      <div><h3>${esc(s.name)} <span class="muted" style="font-size:15px;font-weight:500">${esc(s.symbol)}</span></h3>
      <div class="sub">${esc(s.sector || "")} · ${esc(s.industry || "")} · 시총 ${fCap(s.market_cap)} · 회계연도 ${esc(s.fiscal_period || "")}</div></div>
      <div class="px" style="margin-left:auto;text-align:right"><b class="num" style="font-size:22px">${fPrice(s.price)}</b><br><span class="${ud(s.change_pct)}">${arrow(s.change_pct)}${fPct(s.change_pct, 2)}</span></div></div>
    <ul class="reasons" style="margin-top:12px">${s.reasons.good.map(r => `<li>${esc(r)}</li>`).join("")}${s.reasons.bad.map(r => `<li class="bad">${esc(r)}</li>`).join("")}</ul>
    <h4>7가지 영역 점수 (분석 종목 내 상대 순위 기준)</h4>
    <div class="areas">${Object.entries(s.areas).map(([k, v]) => `<div class="area"><div class="lbl">${AREA_LABEL[k]}</div>${v == null ? '<div class="tiny">해당 없음</div>' : meter(v)}<div class="val num" style="color:${v == null ? "var(--text-3)" : bandColor(v)}">${v ?? "–"}</div></div>`).join("")}</div>
    ${s.gurus.length ? `<h4>이 종목을 들고 있는 거장</h4><div class="chips">${s.gurus.map(g => `<span class="chip ${g.action === "신규매수" ? "buy" : g.action === "비중확대" ? "add" : ""}">${esc(g.person)} · ${esc(g.action)}</span>`).join("")}</div>` : ""}
    ${tbar}
    <h4>최근 ${s.price_series.length > 60 ? "6개월" : "1개월"} 주가</h4>${spark(s.price_series, {h: 120, stroke: "auto", big: true})}
    ${yrs > 1 ? `<h4>연간 추이 (최근 → 과거)</h4><div class="kv">
      <div><span>매출</span><b>${s.revenue_series.map(v => fCap(v)).join(" ← ")}</b></div>
      <div><span>순이익</span><b>${s.net_income_series.map(v => fCap(v)).join(" ← ")}</b></div>
      <div><span>잉여현금흐름</span><b>${(s.fcf_series || []).map(v => fCap(v)).join(" ← ")}</b></div></div>` : ""}
    <h4>모든 지표</h4><div class="kv">${kv.map(([k, v, h]) => `<div title="${esc(h)}"><span>${k}${h ? ` <span class="tiny">(${esc(h)})</span>` : ""}</span><b>${v}</b></div>`).join("")}</div>`;
  $("#modal").classList.add("show");
}
function openHelp() {
  $("#modalBody").innerHTML = `<h3>이 화면 읽는 법</h3>
  <h4>1. 시장 점수 (맨 위)</h4><p>"지금 주식을 사도 되는 날씨인가"를 0~100점으로 요약했습니다. <b>65점 이상</b>이면 우량주를 나눠서 사볼 만하고, <b>35점 아래</b>면 현금을 들고 기다리는 편이 안전합니다. 7개 항목을 누르면 왜 그 점수인지 나옵니다.</p>
  <h4>2. 지수</h4><p>S&P500(미국 대표 500개), 나스닥(기술주), 러셀2000(중소형주)이 오늘 얼마나 움직였는지와 1년 흐름입니다. VIX는 거꾸로 — 낮을수록 좋습니다.</p>
  <h4>3. 금리·경기</h4><p>금리가 내려가면 주식에 유리하고, 실업률이 급하게 오르면 위험 신호입니다. 초록 배지 = 좋음, 빨강 = 나쁨.</p>
  <h4>4. 추천 종목</h4><p>점수가 높은 순서입니다. A등급(75점 이상)은 여러 기준을 두루 만족하는 종목입니다. 카드의 ✓는 강점, !는 약점. <b>한 종목에 몰아넣지 말고</b> 여러 섹터로 나누세요.</p>
  <h4>5. ETF</h4><p>초보자는 여기서 시작하는 것이 보통 안전합니다. '배분 예시'는 시장 점수에 따라 주식·채권·금 비중을 어떻게 나눌지 보여줍니다. 탭에서 분류별로 볼 수 있습니다.</p>
  <h4>6. 거장 포트폴리오</h4><p>버핏 등이 실제로 신고한 보유 종목입니다. '신규 매수'와 '비중 확대'가 특히 참고할 만합니다. 단 최대 45일 지난 정보입니다.</p>
  <h4>초보자를 위한 세 가지 원칙</h4><ol><li>한 번에 다 사지 말고 몇 달에 걸쳐 나눠 사세요 (분할 매수).</li><li>점수가 높아도 이해 못 하는 회사는 사지 마세요.</li><li>이 앱은 참고 자료입니다. 최종 판단은 본인이 합니다.</li></ol>`;
  $("#modal").classList.add("show");
}

/* ---------- 조립 ---------- */
let DATA = null, bySym = {}, byEtf = {};
function renderAll() {
  const d = DATA;
  $("#app").innerHTML = renderMarket(d.market) + renderIndexes(d.indexes, d.sectors) + renderMacro(d.rates, d.macro, d.sentiment, d.rates_history)
    + renderPicks(d.recommendations, bySym, d.market) + renderEtf(d.etfs, d.etf_categories, d.allocation, d.market) + renderGurus(d.gurus) + renderTable(d.stocks) + renderGloss();
}
function renderPart(id, html) { const el = document.getElementById(id); if (el) el.outerHTML = html; }

document.addEventListener("click", e => {
  const area = e.target.closest(".area[data-k]"); if (area) { area.classList.toggle("open"); return; }
  const ec = e.target.closest("[data-etfcat]"); if (ec) { etfCat = ec.dataset.etfcat; renderPart("etf", renderEtf(DATA.etfs, DATA.etf_categories, DATA.allocation, DATA.market)); return; }
  const et = e.target.closest("[data-etf]"); if (et) { const x = byEtf[et.dataset.etf]; if (x) openEtf(x); return; }
  const g = e.target.closest("[data-guru]"); if (g) { guruIdx = +g.dataset.guru; renderPart("gurus", renderGurus(DATA.gurus)); return; }
  const th = e.target.closest("th[data-k]"); if (th) { const k = th.dataset.k; if (sortKey === k) sortAsc = !sortAsc; else { sortKey = k; sortAsc = (k === "symbol" || k === "name" || k === "sector" || k === "per" || k === "peg" || k === "debt_to_equity"); } renderPart("all", renderTable(DATA.stocks)); return; }
  const sym = e.target.closest("[data-sym]"); if (sym && sym.dataset.sym) { const s = bySym[sym.dataset.sym]; if (s) openStock(s); else if (sym.classList.contains("chip") || sym.classList.contains("t")) { alert(`${sym.dataset.sym}: 시가총액 상위 분석 대상에 포함되지 않은 종목입니다. python run.py --top 500 처럼 범위를 넓히면 분석됩니다.`); } return; }
  if (e.target.id === "modalClose" || e.target.id === "modal") $("#modal").classList.remove("show");
});
document.addEventListener("keydown", e => { if (e.key === "Escape") $("#modal").classList.remove("show"); });
document.addEventListener("input", e => {
  if (e.target.id === "q") { query = e.target.value.trim().toLowerCase(); const pos = e.target.selectionStart; renderPart("all", renderTable(DATA.stocks)); const q = $("#q"); q.focus(); q.setSelectionRange(pos, pos); }
  if (e.target.id === "sectorF") { sectorF = e.target.value; renderPart("all", renderTable(DATA.stocks)); }
});
$("#helpBtn").addEventListener("click", openHelp);
$("#themeBtn").addEventListener("click", () => {
  const cur = document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  const next = cur === "dark" ? "light" : "dark"; document.documentElement.dataset.theme = next;
  try { localStorage.setItem("theme", next); } catch (_) {}
});
try { const t = new URLSearchParams(location.search).get("theme") || localStorage.getItem("theme"); if (t) document.documentElement.dataset.theme = t; } catch (_) {}

/* ---------- 장중 시세 폴링 ---------- */
let liveTimer = null;
function applyLive(l) {
  const flash = el => { if (!el) return; el.classList.remove("flash"); void el.offsetWidth; el.classList.add("flash"); };
  DATA.indexes.forEach(i => { const u = l.indexes[i.symbol]; if (u) { i.price = u.price; i.change_pct = u.change_pct; } });
  DATA.sectors.forEach(s => { if (isNum(l.sectors[s.etf])) s.change_pct = l.sectors[s.etf]; });
  renderPart("index", renderIndexes(DATA.indexes, DATA.sectors));
  if (l.fng && isNum(l.fng.score)) { DATA.sentiment.score = l.fng.score; DATA.sentiment.rating = l.fng.rating; renderPart("macro", renderMacro(DATA.rates, DATA.macro, DATA.sentiment, DATA.rates_history)); }
  Object.entries(l.stocks).forEach(([sym, u]) => {
    const s = bySym[sym]; if (!s) return;
    s.price = u.price; s.change_pct = u.change_pct;
    if (s.target && isNum(s.target.mean) && u.price) s.target_upside = s.target.mean / u.price - 1;
    document.querySelectorAll(`.stock[data-sym="${sym}"] .px`).forEach(px => {
      px.innerHTML = `<b class="num">${fPrice(s.price)}</b><span class="${ud(s.change_pct)}">${arrow(s.change_pct)}${fPct(s.change_pct, 2)}</span>`; flash(px);
    });
    document.querySelectorAll(`.stock[data-sym="${sym}"] .mini div:last-child b`).forEach(b => { b.className = "num " + ud(s.target_upside); b.textContent = fRatioPct(s.target_upside); });
  });
  Object.entries(l.etfs || {}).forEach(([sym, u]) => {
    const e = byEtf[sym]; if (!e) return; e.price = u.price; e.change_pct = u.change_pct;
    document.querySelectorAll(`.etf[data-etf="${sym}"] .px`).forEach(px => {
      px.innerHTML = `<b class="num" style="display:block">${fPrice(e.price)}</b><span class="${ud(e.change_pct)}" style="font-size:12px;font-weight:600">${arrow(e.change_pct)}${fPct(e.change_pct, 2)}</span>`; flash(px);
    });
  });
  const m = l.market, at = (l.at || "").slice(11, 16);
  const badge = $("#liveBadge"); badge.classList.toggle("open", !!m.open);
  badge.textContent = m.open ? `장중 · 시세 ${at} 기준 (1분마다 갱신)` : `장 마감 (${m.et.slice(11)}) · 마지막 시세 ${at}`;
}
let STATIC = false;
async function pollLive() {
  clearTimeout(liveTimer);
  if (STATIC) return;
  let open = false;
  try {
    const r = await fetch("live");
    if (!r.ok || !(r.headers.get("content-type") || "").includes("json")) {
      STATIC = true;
      $("#liveBadge").textContent = "자동 갱신본 (매일 07:00 KST) · 장중 실시간 시세는 맥에서 열 때만";
      return;
    }
    const l = await r.json();
    if (!l.error) {
      open = !!l.market.open;
      // 서버에서 매일 아침 전체 갱신이 끝났으면 데이터 전체를 다시 읽는다
      if (l.data_generated_at && DATA && l.data_generated_at > DATA.generated_at) { location.reload(); return; }
      applyLive(l);
    }
  } catch (_) { /* 서버가 잠시 없어도 조용히 다음을 기다린다 */ }
  liveTimer = setTimeout(pollLive, open ? 60 * 1000 : 10 * 60 * 1000);
}
document.addEventListener("visibilitychange", () => { if (!document.hidden && DATA) pollLive(); });

fetch("data.json?" + Date.now()).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); }).then(d => {
  DATA = d; d.stocks.forEach(s => bySym[s.symbol] = s); (d.etfs || []).forEach(e => byEtf[e.symbol] = e);
  $("#gen").textContent = "분석 " + d.generated_at.replace("T", " ") + ` · 전체 ${d.universe_size.toLocaleString()}종목 중 ${d.analyzed}개`;
  $("#sources").textContent = d.sources.join(", ");
  renderAll();
  pollLive();
}).catch(err => { $("#app").innerHTML = `<div class="loading">데이터를 불러오지 못했습니다 (${esc(err.message)}).<br>터미널에서 <code>python run.py</code> 를 실행하면 수집·갱신 후 자동으로 열립니다.</div>`; });
})();
