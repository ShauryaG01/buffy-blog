"""Buffy drip publisher — Flash/knok model, runs in GitHub Actions.

All built pages live in staging/blog/. This moves a small batch into output/blog/
on each cron run, following a weekly ramp, regenerates a live-only sitemap, and logs
everything. A push of output/ triggers the Pages deploy; submit_indexnow.py then
pings Bing. No LLM runs here — generation happens up front; Actions only publishes.

Commands (run from the buffy-blog repo root):
    python scripts/publish_drip.py init      # build queue, stage everything, seed output root
    python scripts/publish_drip.py publish   # release the next ramped batch
    python scripts/publish_drip.py sync       # re-stage unpublished after a rebuild (never bulk-publishes)
    python scripts/publish_drip.py status
"""
from __future__ import annotations

import json
import random
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "staging"
OUTPUT = ROOT / "output"
PUB = ROOT / "publish"
STATE = PUB / "publish_state.json"
QUEUE = PUB / "publish_queue.json"
LOG = PUB / "publish_log.json"

DOMAIN = "https://heybuffy.com"
RUNS_PER_DAY = 7
# (max week, pages/day) — a page/day CEILING, not an obligation.
RAMP = [(2, 30), (3, 40), (4, 45), (5, 50), (6, 60), (7, 65), (999, 70)]
# Root files always live (never dripped).
ALWAYS_LIVE = {"index.html", "about.html", "editorial.html", "privacy.html",
               "terms.html", "robots.txt", "all.html"}


def _load(p, default):
    return json.loads(p.read_text()) if p.is_file() else default


def _save(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2))


def _daily_budget(launch: date) -> int:
    weeks = max(1, ((date.today() - launch).days // 7) + 1)
    for max_wk, budget in RAMP:
        if weeks <= max_wk:
            return budget
    return RAMP[-1][1]


def _copy_root():
    """Seed output/ with the always-live root files + static assets."""
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name in ALWAYS_LIVE:
        src = STAGING / name
        if src.is_file():
            shutil.copy2(src, OUTPUT / name)
    if (STAGING / "static").is_dir():
        shutil.copytree(STAGING / "static", OUTPUT / "static", dirs_exist_ok=True)


def _regen_sitemap():
    """Sitemap of LIVE pages only (root + published /blog pages)."""
    urls = []
    for name in sorted(ALWAYS_LIVE):
        if (OUTPUT / name).is_file() and name.endswith(".html"):
            loc = "/" if name == "index.html" else f"/{name}"
            urls.append(f"{DOMAIN}{loc}")
    for f in sorted((OUTPUT / "blog").glob("*.html")) if (OUTPUT / "blog").is_dir() else []:
        urls.append(f"{DOMAIN}/blog/{f.name}")
    today = date.today().isoformat()
    body = "".join(
        f"<url><loc>{u}</loc><lastmod>{today}</lastmod></url>" for u in urls
    )
    (OUTPUT / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>'
    )
    return len(urls)


def cmd_init():
    """Build the publish queue from staging/blog + publish/publish_queue.json order."""
    STAGING_BLOG = STAGING / "blog"
    if not STAGING_BLOG.is_dir():
        sys.exit("No staging/blog/ — build the site into staging first.")
    # Queue is ONLY the indexable pages listed in publish_queue.json (volume-ordered).
    # noindex drafts remain in staging and are never queued/published.
    queue = [q for q in _load(QUEUE, []) if (STAGING_BLOG / q).is_file()]
    if not queue:
        sys.exit("publish_queue.json is empty — run build_publish_queue.py first.")
    _copy_root()
    _regen_sitemap()
    _save(STATE, {"launch_date": date.today().isoformat(), "queue": queue, "published": []})
    print(f"init: {len(queue)} pages queued, output seeded with root pages")


def cmd_publish():
    st = _load(STATE, None)
    if not st:
        sys.exit("Run `init` first.")
    launch = date.fromisoformat(st["launch_date"])
    budget = _daily_budget(launch)
    per_run = max(1, budget // RUNS_PER_DAY)
    n = per_run + random.choice([0, 0, 1])  # slight natural variation
    (OUTPUT / "blog").mkdir(parents=True, exist_ok=True)

    moved = []
    for _ in range(min(n, len(st["queue"]))):
        name = st["queue"].pop(0)
        src = STAGING / "blog" / name
        if src.is_file():
            shutil.copy2(src, OUTPUT / "blog" / name)
            st["published"].append(name)
            moved.append(f"/blog/{name}")
    total_urls = _regen_sitemap()
    _save(STATE, st)
    log = _load(LOG, [])
    log.append({"ts": datetime.now(timezone.utc).isoformat(), "published": moved,
                "daily_budget": budget, "live_total": len(st["published"]),
                "remaining": len(st["queue"])})
    _save(LOG, log)
    # newly-published URLs for the IndexNow step
    (PUB / "last_published.json").write_text(json.dumps([f"{DOMAIN}{u}" for u in moved]))
    print(f"publish: +{len(moved)} live (budget {budget}/day) | "
          f"{len(st['published'])} live, {len(st['queue'])} queued, {total_urls} in sitemap")


def cmd_sync():
    """After a rebuild: refresh already-live pages from staging without publishing new ones."""
    st = _load(STATE, None)
    if not st:
        sys.exit("Run `init` first.")
    _copy_root()
    for name in st["published"]:
        src = STAGING / "blog" / name
        if src.is_file():
            shutil.copy2(src, OUTPUT / "blog" / name)
    total = _regen_sitemap()
    print(f"sync: refreshed {len(st['published'])} live pages ({total} sitemap URLs); no new pages published")


def cmd_status():
    st = _load(STATE, {"published": [], "queue": []})
    launch = st.get("launch_date", "not launched")
    budget = _daily_budget(date.fromisoformat(launch)) if st.get("launch_date") else 0
    print(f"launch={launch} budget={budget}/day live={len(st['published'])} queued={len(st['queue'])}")


CMDS = {"init": cmd_init, "publish": cmd_publish, "sync": cmd_sync, "status": cmd_status}

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    CMDS.get(cmd, cmd_status)()
