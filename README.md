# Buffy Blog — Deploy & Drip Runbook

Flash/knok publishing model, adapted to run **entirely in GitHub Actions** with no
local machine and no LLM calls in CI. Pages are generated up front, committed to
`staging/`, and released on a cron ramp.

## Architecture

```
generate up front (local, Claude)         ← one-off / batched
        ↓  seo-engine build  →  staging/           (FULL built site, incl. drafts)
        ↓  build_publish_queue.py → publish/publish_queue.json  (indexable, volume-ordered)
        ↓  commit staging/ + scripts + .github to the buffy-blog repo
GitHub Actions cron (drip.yml, 7 uneven runs/day)
        ↓  publish_drip.py publish → moves a ramped batch staging/ → output/
        ↓  regenerate live-only sitemap
        ↓  submit_indexnow.py → Bing/Yandex (NOT Google Indexing API)
        ↓  commit output/ + publish/  → push
deploy.yml (on push) → GitHub Pages serves output/
        ↓  proxy heybuffy.com/blog/* → Pages  (flat URLs, one indexable copy)
```

## Files (this dir + scripts/)

- `scripts/publish_drip.py` — the drip publisher (`init` / `publish` / `sync` / `status`).
- `scripts/submit_indexnow.py` — IndexNow (Bing/Yandex). Auto-creates the key + `output/<key>.txt`.
- `scripts/build_publish_queue.py` — writes the volume-ordered, indexable-only queue.
- `deploy/github/deploy.yml` — Pages deploy on push.
- `deploy/github/drip.yml` — cron drip (7 uneven times/day) + IndexNow + commit.

## Publishing ramp (page/day CEILING, not a quota)

| Week | Max/day |  | Week | Max/day |
|--|--|--|--|--|
| 1–2 | 30 | | 5 | 50 |
| 3 | 40 | | 6 | 60 |
| 4 | 45 | | 7 | 65 |
|  |  | | 8+ | 70 |

7 runs/day; each run releases `budget/7` (+0/1 random). If only N pages pass quality, publish N.

## Indexing — the corrected approach

- **Google:** sitemap + internal linking + Search Console. **Do NOT use the Google Indexing API** — it is restricted to JobPosting/livestream pages; using it for articles is non-compliant. Use GSC "Request indexing" manually for a few priority pages only.
- **Bing/Yandex:** IndexNow on newly-published URLs (fast, first-class). IndexNow confirms receipt, not indexing.

## One-time setup (needs you)

1. **Create the repo** `buffy-blog` (public — required for free GitHub Pages).
2. **Enable Pages** → Source: GitHub Actions.
3. **Canonical route:** point `heybuffy.com/blog/*` at the Pages deployment (Cloudflare/Netlify/app proxy). Canonicals already emit `https://heybuffy.com/blog/<slug>.html`.
4. **Google Search Console:** verify `heybuffy.com` (domain property), submit the sitemap, connect the API for index-rate monitoring.
5. **Bing Webmaster Tools:** add `heybuffy.com`, import verification from GSC, submit the sitemap. IndexNow key is auto-generated + served at `/<key>.txt`.
6. Optional: to also *generate* inside Actions, add an `ANTHROPIC_API_KEY` secret (Actions has no Claude login by default). The current model keeps generation local, so this is not required to drip.

## Throttle / stop rules (evaluate URLs ≥7 days old)

- Hold ramp: wk-2 index rate <40% (Google or Bing), or >2% non-200, or buffer <7 days.
- Drop to 20/day: wk-4 index rate <50%, or crawl errors rising, or crawled-not-indexed climbing.
- Stop: manual action (Google) or serious site issue (Bing); sitemap/live divergence; a deploy exposes staged drafts; source data corrupted.

## Local dry run (before wiring the repo)

```
seo-engine --project buffy build                 # → staging/ (full site, flat /blog URLs)
python scripts/build_publish_queue.py            # → publish/publish_queue.json
python scripts/publish_drip.py init              # seeds output/ root + queue
python scripts/publish_drip.py publish           # releases one batch into output/blog/
python scripts/publish_drip.py status
```
