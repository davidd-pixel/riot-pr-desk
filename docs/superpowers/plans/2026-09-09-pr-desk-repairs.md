# PR Desk Repairs Implementation Plan

**Goal:** Repair Dave's live PR workflows using davidd-pixel/riot-pr-desk main (db41989) as the base.

**Architecture:** Keep Streamlit, Google Drive and GitHub Actions. The scheduled runner owns opportunity creation and daily digest snapshots. The app reads the saved briefing and records user decisions as separate immutable events so a background briefing cannot overwrite them. Persist the exact daily snapshot before sending; record an uncertain send before SMTP and require explicit recovery if delivery cannot be confirmed.

**Approved scope:** Weekday morning delivery around 08:00 Europe/London via GitHub Actions; Regulatory Radar defaults to 30 days with older-history access; preserve unapproved opportunities; repair AI/News Desk/blog flows; remove Story Ladder, Quote Generator and Crisis Comms. No live email tests or deployment during development.

## Tasks

- [x] AI and News Desk/blog: reproduce with offline Streamlit AppTest; test malformed JSON and provider errors; configure both Anthropic calls using ANTHROPIC_MODEL while preserving Dave's default; fix widget state with callbacks. Files: services/ai_engine.py, services/content_generator.py, pages/1_news_desk.py, pages/16_blog_writer.py, tests/test_ai_ui.py.
- [x] Regulatory Radar and navigation: test ISO/RFC dates, unknown/future dates, 30-day boundary, older history and force refresh. Filter before limiting results, propagate refresh through RSS cache; remove the three requested pages and navigation. Files: services/regulator_monitor.py, services/news_monitor.py, pages/15_regulators.py, app.py, utils/styles.py, tests/test_radar.py.
- [x] Persistence: test failed reads/writes and concurrent briefing/approval using temporary directories and fake external Drive transport. Add strict Drive operations for core briefing data and immutable opportunity action files. Read legacy opportunities without destructive migration. Stop automatic expiry/trim mutating the backlog. Files: services/drive_persistence.py, services/opportunity_tracker.py, tests/test_briefing.py.
- [x] Digest: test summer/winter weekdays, late starts, duplicates, uncertain SMTP outcome, failed persistence and stable snapshots. Keep only seasonal morning slots, runtime guard for the intended slot, job concurrency and runner ownership guard. App home becomes read-only. Store snapshot under daily local-date ID and link digest to that snapshot in Inbox. Files: services/digest_delivery.py, services/autonomous_engine.py, pages/17_inbox.py, app.py, .github/workflows/daily_briefing.yml.
- [x] Verify with unittest discovery and compilation, independent review and inspect complete diff against db41989. Write operational recovery/deployment instructions. Prepare a reviewable commit/patch; do not merge or deploy.

## Verification commands

```sh
.venv-test/bin/python -m unittest discover -s tests -v
.venv-test/bin/python -m compileall -q app.py pages services config utils
 git diff --check
```

All automated tests use synthetic records and external-service doubles. Live API model access, shared Drive permissions, scheduler execution and Dave's deployment need final operator verification.
