"""공용 HTTP 계층: 디스크 캐시 + 재시도 + 요청 간격 제어.

모든 외부 호출은 이 모듈을 거친다. 캐시가 있으면 네트워크를 타지 않으므로
재실행이 빠르고, 데이터 제공처에 부담을 주지 않는다.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import threading
import time
from typing import Any

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(ROOT, "data", "cache")

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
# SEC는 연락처가 포함된 User-Agent를 요구한다 (sec.gov/os/webmaster-faq#developers).
# 환경변수 SEC_CONTACT 에 이메일을 넣는다 (GitHub Actions에서는 Secret으로 주입).
SEC_UA = f"us-stock-dashboard/1.0 (contact: {os.environ.get('SEC_CONTACT', 'anonymous@example.com')})"

_lock = threading.Lock()
_last_call: dict[str, float] = {}
_session_local = threading.local()


def _session() -> requests.Session:
    s = getattr(_session_local, "s", None)
    if s is None:
        s = requests.Session()
        _session_local.s = s
    return s


def _throttle(host: str, min_interval: float) -> None:
    """같은 호스트로의 연속 요청 사이에 최소 간격을 둔다."""
    if min_interval <= 0:
        return
    while True:
        with _lock:
            now = time.monotonic()
            wait = min_interval - (now - _last_call.get(host, 0.0))
            if wait <= 0:
                _last_call[host] = now
                return
        time.sleep(wait)


def _cache_path(key: str) -> str:
    h = hashlib.sha256(key.encode()).hexdigest()[:40]
    return os.path.join(CACHE_DIR, f"{h}.json")


def _cache_read(key: str, ttl: float) -> Any | None:
    if ttl <= 0:
        return None
    path = _cache_path(key)
    try:
        if time.time() - os.path.getmtime(path) > ttl:
            return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)["body"]
    except (OSError, ValueError, KeyError):
        return None


def _cache_write(key: str, body: Any) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    tmp = _cache_path(key) + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"key": key, "at": time.time(), "body": body}, f)
        os.replace(tmp, _cache_path(key))
    except OSError:
        pass


def fetch(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    kind: str = "json",
    ttl: float = 6 * 3600,
    min_interval: float = 0.25,
    tries: int = 3,
    timeout: float = 30.0,
) -> Any | None:
    """URL을 가져온다. 실패하면 None (앱 전체가 멈추지 않도록).

    kind="json"이면 파싱된 객체, "text"면 문자열을 돌려준다.
    """
    cache_key = f"{kind}|{url}|{json.dumps(params or {}, sort_keys=True)}"
    cached = _cache_read(cache_key, ttl)
    if cached is not None:
        return cached

    host = requests.utils.urlparse(url).netloc
    hdrs = {"User-Agent": BROWSER_UA, "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9"}
    hdrs.update(headers or {})

    last_err: str | None = None
    for attempt in range(tries):
        _throttle(host, min_interval)
        try:
            r = _session().get(url, params=params, headers=hdrs, timeout=timeout)
            if r.status_code == 200:
                body = r.json() if kind == "json" else r.text
                if ttl > 0:
                    _cache_write(cache_key, body)
                return body
            # 429/5xx는 백오프 후 재시도할 가치가 있다.
            last_err = f"HTTP {r.status_code}"
            if r.status_code not in (429, 500, 502, 503, 504):
                break
        except Exception as e:  # noqa: BLE001 - 네트워크/파싱 오류 전부 흡수
            last_err = f"{type(e).__name__}: {e}"
        time.sleep((1.6 ** attempt) + random.uniform(0, 0.4))

    # 만료된 캐시라도 있으면 쓰는 편이 빈손보다 낫다.
    stale = _cache_read(cache_key, ttl=10 ** 9)
    if stale is not None:
        return stale
    print(f"    [warn] {host} 실패 ({last_err}) {url}")
    return None


def fetch_sec(url: str, **kw) -> Any | None:
    """SEC 전용: 요구되는 User-Agent와 10req/s 제한을 지킨다."""
    kw.setdefault("headers", {})
    kw["headers"] = {"User-Agent": SEC_UA, "Accept-Encoding": "gzip, deflate", **kw["headers"]}
    kw.setdefault("min_interval", 0.15)
    return fetch(url, **kw)
