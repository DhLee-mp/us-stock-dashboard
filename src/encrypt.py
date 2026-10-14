"""배포용 데이터 암호화: data.json → data.enc (AES-256-GCM, PBKDF2-SHA256).

브라우저의 Web Crypto API가 같은 방식으로 복호화한다 (web/app.js의 decryptData).
  python -m src.encrypt web/data.json web/data.enc   # 비밀번호는 환경변수 DASHBOARD_PASSWORD
"""
from __future__ import annotations

import base64
import json
import os
import sys

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ITERATIONS = 300_000


def encrypt(plaintext: bytes, password: str) -> dict:
    salt, iv = os.urandom(16), os.urandom(12)
    key = PBKDF2HMAC(hashes.SHA256(), 32, salt, ITERATIONS).derive(password.encode("utf-8"))
    ct = AESGCM(key).encrypt(iv, plaintext, None)
    b64 = lambda b: base64.b64encode(b).decode()
    return {"v": 1, "kdf": "PBKDF2-SHA256", "iter": ITERATIONS, "salt": b64(salt), "iv": b64(iv), "ct": b64(ct)}


def main(src: str, dst: str) -> None:
    pw = os.environ.get("DASHBOARD_PASSWORD", "")
    if len(pw) < 6:
        sys.exit("DASHBOARD_PASSWORD 환경변수를 6자 이상으로 설정하세요")
    with open(src, "rb") as f:
        data = f.read()
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(encrypt(data, pw), f)
    os.remove(src)
    print(f"암호화 완료: {dst} ({os.path.getsize(dst)/1e6:.1f} MB), 원본 삭제")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
