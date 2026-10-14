# 🧭 미국 주식 나침반

초보자를 위한 미국 주식 대시보드. **외부 유료 API 없이**, 공개 데이터만으로 동작합니다.

- 오늘의 **시장 점수 (0~100)** — 100 = 적극 매수, 0 = 현금 보유. 7개 영역(추세·시장 폭·금리·경기/고용·심리·변동성·밸류에이션)으로 설명
- **주요 지수** (S&P500·나스닥·나스닥100·러셀2000·다우·VIX) + 11개 섹터 등락
- **금리·고용·물가** (미 재무부 수익률 곡선, BLS 실업률/고용/CPI), CNN 공포·탐욕 지수
- **추천 종목 TOP 20** — PER·PEG·성장률·부채·현금흐름·월가 목표주가·주가 흐름·거장 보유 7가지로 채점
- **ETF 50개** — 핵심·섹터·테마·배당·채권·금/원자재·해외·방어 8개 분류, 수익 흐름·추세·위험·비용으로 채점. 시장 점수에 따른 주식/채권/금 배분 예시
- **거장 포트폴리오** — 버핏·드러켄밀러·애크먼·테퍼·클라먼·달리오 등 SEC 13F 공시 기반, 직전 분기 대비 신규/확대/축소/매도
- 분석한 전체 종목 정렬·검색 테이블, 초보자용 용어 사전

## 실행

```bash
cd us-stock-dashboard
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt   # 최초 1회
./.venv/bin/python run.py            # 데이터 수집(약 5분) 후 브라우저가 열립니다
```

옵션:

| 명령 | 설명 |
|---|---|
| `python run.py --top 400` | 시가총액 상위 400개 분석 (기본 200, 많을수록 오래 걸림) |
| `python run.py --serve` | 수집 없이 마지막 데이터로 바로 열기 |
| `python run.py --build` | 서버 없이 데이터만 갱신 |

수집한 원본은 `data/cache/`에 캐시되어(시세 1시간, 재무제표 3일, 13F 90일) 재실행이 빠릅니다.

## 데이터 출처 (모두 무료·키 불필요)

| 데이터 | 출처 |
|---|---|
| 시세·과거주가·재무제표·애널리스트 목표주가·전체 종목 목록 | Nasdaq (api.nasdaq.com) |
| S&P500·VIX 시계열, 심리 7개 지표 | CNN Fear & Greed |
| 국채 수익률 곡선 | U.S. Treasury |
| 실업률·비농업 취업자·CPI | BLS Public API v1 |
| 거장 보유 종목 (13F-HR) | SEC EDGAR |

## 점수는 어떻게 매기나

**시장 점수** (`src/market_score.py`): 각 영역을 0~100으로 매긴 뒤 가중 평균 — 추세 20%, 금리·통화정책 20%, 시장 폭 15%, 경기·고용 15%, 심리 10%(역발상), 변동성 10%, 밸류에이션 10%.

**ETF 점수** (`src/etf.py`): 수익 흐름(1·3·6·12개월) 35%, 추세(200일선) 20%, 위험(변동성·최대낙폭) 35%, 비용(보수율) 10%. 약세장이면 위험 비중을 50%로, 강세장이면 수익 흐름을 45%로 올립니다. ETF 목록은 `UNIVERSE` 상수에서 추가/삭제할 수 있습니다.

**종목 점수** (`src/stock_score.py`): 각 지표를 분석 종목 내 백분위로 바꾼 뒤 가치 20%, 성장 20%, 재무 안정 15%, 현금흐름 15%, 월가 목표주가 15%, 주가 흐름 10%, 거장 보유 5%로 가중 평균. 시장 점수가 40 미만이면 안정·현금흐름 비중을 올리고, 70 이상이면 성장·모멘텀 비중을 올립니다. 금융주는 부채비율 대신 ROE로 안정성을 봅니다. 가중치는 두 파일 상단의 상수로 바꿀 수 있습니다.

## 주의

투자 권유가 아닌 참고 자료입니다. 13F는 분기 종료 후 최대 45일 뒤에 공개되어 시차가 있습니다. 비공식 엔드포인트(Nasdaq, CNN)는 예고 없이 바뀔 수 있으며, 그 경우 해당 영역은 중립(50점)으로 처리되고 나머지는 정상 동작합니다.

## 자동 갱신 (macOS launchd)

| 에이전트 | 동작 |
|---|---|
| `com.dlee.stockdash.serve` | 로그인 시 서버 자동 실행, 죽으면 재시작 → http://127.0.0.1:8765 항상 열림 |
| `com.dlee.stockdash.build` | 매일 07:00 (미국 장 마감 후) 전체 데이터 재수집 |

장중(미 동부 9:30~16:00)에는 화면이 1분마다 `/live`를 불러 지수·섹터·추천 종목 시세, VIX, 공포·탐욕 지수를 갱신합니다. 점수·재무지표는 하루 1회 계산합니다.

```bash
# 상태 확인 / 해제 / 재등록
launchctl list | grep stockdash
launchctl bootout gui/$(id -u)/com.dlee.stockdash.build
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.dlee.stockdash.build.plist
# 갱신 시각 변경: plist의 Hour/Minute 수정 후 bootout → bootstrap
```

## 바탕화면 앱

`~/Desktop/미국 주식 나침반.app` — 더블클릭하면 서버를 확인(없으면 실행)한 뒤 Chrome 앱 창(주소창 없는 전용 창)으로 엽니다. Chrome이 없으면 기본 브라우저로 엽니다.
Dock에 두려면 아이콘을 Dock으로 끌어다 놓고, /Applications에 두려면 복사하면 됩니다.
아이콘·앱 번들 소스는 `build/`에 있습니다 (`build/icon.html` → Chrome 헤드리스 렌더 → `iconutil`).

Safari를 쓰는 경우: 대시보드를 연 상태에서 **파일 → Dock에 추가**를 누르면 Safari 웹앱으로도 설치됩니다 (`web/manifest.json`).

## 핸드폰에서 보기

서버는 `--host 0.0.0.0`으로 실행되며(launchd 기본), 같은 Wi-Fi에서 `http://<맥이름>.local:8765/` 로 접속합니다. 맥 이름은 `scutil --get LocalHostName`. `.local`이 안 되면 `ipconfig getifaddr en0`의 IP를 씁니다.
iPhone Safari에서 공유 → **홈 화면에 추가**를 누르면 앱 아이콘으로 설치됩니다. macOS 방화벽이 켜져 있으면 처음 한 번 Python의 수신 연결을 허용해야 합니다.

## GitHub Pages 자동 배포

`.github/workflows/pages.yml`이 매일 07:00 KST에 데이터를 수집해 Pages로 배포합니다. SEC 접속용 연락처는 저장소 Secret `SEC_CONTACT`에 넣습니다 (로컬은 환경변수).
