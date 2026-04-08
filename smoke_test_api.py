#!/usr/bin/env python3
"""
Quick VM / local checks (no pytest). Run while the server is up:

  python3 smoke_test_api.py
  API_BASE=http://127.0.0.1:8002/api python3 smoke_test_api.py
"""

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("API_BASE", "http://127.0.0.1:8002/api").rstrip("/")


def get(path: str):
    url = f"{BASE}{path}"
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def main():
    print(f"Checking {BASE} ...")
    try:
        st = get("/status")
        assert st.get("success"), st
        print("  [ok] GET /status — database:", st.get("database_connected"))

        rd = get("/training/readiness")
        assert rd.get("success"), rd
        print("  [ok] GET /training/readiness — can_train:", rd.get("can_train"))
        if rd.get("messages"):
            for m in rd["messages"]:
                print("       note:", m)

        print("\nSmoke tests passed. Next: capture training images, train model, then POST /recognize from the UI.")
        return 0
    except urllib.error.URLError as e:
        print("  [fail] Cannot reach API — is Flask running?", e, file=sys.stderr)
        return 1
    except Exception as e:
        print("  [fail]", e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
