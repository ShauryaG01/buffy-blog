"""Submit newly-published URLs to IndexNow (Bing, Yandex, and participating engines).

Deliberately does NOT use the Google Indexing API: Google restricts that API to
JobPosting and livestream pages, so using it for articles is non-compliant. Google
discovery relies on the sitemap + internal linking + Search Console instead.

IndexNow confirms receipt, not indexing. Submit only newly added / materially
updated URLs — never the whole site each run. Stdlib only (runs in Actions with no deps).

Usage (buffy-blog repo root):
    python scripts/submit_indexnow.py --newly-published   # reads publish/last_published.json
    python scripts/submit_indexnow.py --urls https://heybuffy.com/blog/x.html ...
"""
from __future__ import annotations

import json
import secrets
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"
PUB = ROOT / "publish"
HOST = "heybuffy.com"
KEY_FILE = PUB / "indexnow_key.txt"
LOG = PUB / "indexnow_log.json"
ENDPOINT = "https://api.indexnow.org/indexnow"


def _key() -> str:
    """Stable per-site key; also written as output/<key>.txt for verification."""
    if KEY_FILE.is_file():
        key = KEY_FILE.read_text().strip()
    else:
        key = secrets.token_hex(16)
        KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        KEY_FILE.write_text(key)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / f"{key}.txt").write_text(key)  # served at https://heybuffy.com/<key>.txt
    return key


def _urls() -> list[str]:
    if "--urls" in sys.argv:
        return sys.argv[sys.argv.index("--urls") + 1:]
    if "--newly-published" in sys.argv:
        f = PUB / "last_published.json"
        return json.loads(f.read_text()) if f.is_file() else []
    return []


def main() -> int:
    urls = [u for u in _urls() if u.startswith(f"https://{HOST}/")]
    if not urls:
        print("indexnow: no new URLs to submit")
        return 0
    key = _key()
    payload = json.dumps({
        "host": HOST, "key": key,
        "keyLocation": f"https://{HOST}/{key}.txt",
        "urlList": urls[:10000],
    }).encode()
    req = urllib.request.Request(ENDPOINT, data=payload,
                                 headers={"Content-Type": "application/json"})
    status, err = None, None
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            status = r.status
    except urllib.error.HTTPError as e:
        status, err = e.code, e.reason
    except Exception as e:  # network etc. — log, don't fail the workflow
        status, err = "error", str(e)
    log = json.loads(LOG.read_text()) if LOG.is_file() else []
    log.append({"ts": datetime.now(timezone.utc).isoformat(), "count": len(urls),
                "status": status, "error": err})
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text(json.dumps(log, indent=2))
    print(f"indexnow: submitted {len(urls)} URLs -> status {status}"
          f"{' (' + str(err) + ')' if err else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
