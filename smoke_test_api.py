#!/usr/bin/env python3
"""
Quick VM / local checks (no pytest). Run while the server is up:

  python3 smoke_test_api.py
  API_BASE=http://127.0.0.1:8002/api python3 smoke_test_api.py
  WEB_ADMIN_PASSWORD=yourpass python3 smoke_test_api.py
"""

import json
import os
import sys
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from typing import Optional

BASE = os.environ.get("API_BASE", "http://127.0.0.1:8002/api").rstrip("/")


def _opener(jar: CookieJar):
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def get(path: str, jar: Optional[CookieJar] = None):
    url = f"{BASE}{path}"
    req = urllib.request.Request(url, method="GET")
    o = _opener(jar) if jar else urllib.request.build_opener()
    with o.open(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def post_json(path: str, body: dict, jar: CookieJar):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with _opener(jar).open(req, timeout=20) as resp:
        return json.loads(resp.read().decode()), resp.status


def main():
    print(f"Checking {BASE} ...")
    jar = CookieJar()
    try:
        cfg = get("/auth/config")
        assert cfg.get("success"), cfg
        auth_on = cfg.get("auth_required", True)
        print("  [ok] GET /auth/config — auth_required:", auth_on)

        st = get("/status")
        assert st.get("success"), st
        print("  [ok] GET /status — database:", st.get("database_connected"))

        if auth_on:
            user = (os.environ.get("WEB_ADMIN_USERNAME") or "admin").strip()
            pw = (os.environ.get("WEB_ADMIN_PASSWORD") or "").strip()
            if not pw:
                print(
                    "  [skip] Authenticated checks — set WEB_ADMIN_PASSWORD to test "
                    "/auth/login and /training/readiness with a session."
                )
                print("\nSmoke tests passed (public endpoints only).")
                return 0
            login_body, status = post_json(
                "/auth/login",
                {"username": user, "password": pw},
                jar,
            )
            if status != 200 or not login_body.get("success"):
                print("  [fail] POST /auth/login:", login_body, file=sys.stderr)
                return 1
            print("  [ok] POST /auth/login — user:", login_body.get("user"))
        else:
            print("  [info] AUTH disabled — calling readiness without session")

        rd = get("/training/readiness", jar if auth_on else None)
        assert rd.get("success"), rd
        print("  [ok] GET /training/readiness — can_train:", rd.get("can_train"))
        if rd.get("messages"):
            for m in rd["messages"]:
                print("       note:", m)

        print("\nSmoke tests passed. Next: capture training images, train model, then POST /recognize from the UI.")
        return 0
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        print("  [fail] HTTP", e.code, body, file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print("  [fail] Cannot reach API — is Flask running?", e, file=sys.stderr)
        return 1
    except Exception as e:
        print("  [fail]", e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
