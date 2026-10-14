#!/usr/bin/env python3
"""미국 주식 나침반 — 데이터 갱신 + 로컬 웹 대시보드.

  python run.py            # 데이터 갱신 후 브라우저 열기
  python run.py --top 400  # 시가총액 상위 400개 분석 (기본 200)
  python run.py --serve    # 갱신 없이 서버만
  python run.py --build    # 서버 없이 갱신만
"""
import argparse
import http.server
import json
import os
import sys
import threading
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
WEB = os.path.join(ROOT, "web")


class Handler(http.server.SimpleHTTPRequestHandler):
    """정적 파일 + /live (장중 시세) + /status."""

    def __init__(self, *a, **k):
        super().__init__(*a, directory=WEB, **k)

    def log_message(self, *a, **k):  # 콘솔 조용히
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/live":
            from src import live
            try:
                return self._json(live.snapshot())
            except Exception as e:  # noqa: BLE001
                return self._json({"error": f"{type(e).__name__}: {e}"}, 500)
        if path == "/status":
            from src import live
            return self._json({"market": live.market_status()})
        if path.startswith("/data.json"):
            if not os.path.exists(os.path.join(WEB, "data.json")):
                return self.send_error(404)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            with open(os.path.join(WEB, "data.json"), "rb") as f:
                body = f.read()
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return self.wfile.write(body)
        return super().do_GET()


def serve(port: int, open_browser: bool, host: str = "127.0.0.1") -> None:
    httpd = http.server.ThreadingHTTPServer((host, port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"\n대시보드: {url}   (종료: Ctrl+C)")
    if host == "0.0.0.0":
        import socket, subprocess
        try:
            name = subprocess.run(["scutil", "--get", "LocalHostName"], capture_output=True, text=True).stdout.strip()
        except OSError:
            name = socket.gethostname()
        print(f"같은 Wi-Fi의 핸드폰에서: http://{name}.local:{port}/")
    if open_browser:
        threading.Timer(0.6, webbrowser.open, args=(url,)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--top", type=int, default=200, help="시가총액 상위 N개 종목 분석 (기본 200)")
    ap.add_argument("--workers", type=int, default=5, help="동시 요청 수")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1", help="0.0.0.0 이면 같은 Wi-Fi의 핸드폰에서도 접속 가능")
    ap.add_argument("--build", action="store_true", help="데이터만 갱신")
    ap.add_argument("--serve", action="store_true", help="서버만 실행")
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()

    if not a.serve:
        from src.build import build
        build(top=a.top, workers=a.workers)
    if not a.build:
        serve(a.port, not a.no_browser, a.host)


if __name__ == "__main__":
    main()
