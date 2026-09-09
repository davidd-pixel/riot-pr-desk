# PR Desk repairs and rollout

These changes are based on `davidd-pixel/riot-pr-desk` main at `db41989`.
The live repository is Dave's. `tyng1/riot-pr-desk` is an independent copy,
not a GitHub fork. Merge the review branch into Dave's repository only after
his review and the configuration checks below.

## Result

- Radar shows the last 30 days by default; 90/365-day history is optional.
  Invalid, missing and future publication dates are excluded. Refresh bypasses
  both service and RSS caches.
- News Desk catches AI failures and validates triage JSON before rendering.
  Blog suggestion failures leave manual entry available; quickstarts update
  widget state before render. Both Claude calls honor `ANTHROPIC_MODEL`, with
  Dave's current `claude-sonnet-5` as the default. Model availability has not
  been tested against Dave's account.
- Story Ladder, Quote Generator and Crisis Comms are removed from navigation
  and multipage discovery.
- Only the scheduled runner creates opportunities. Opening the dashboard
  reads a saved briefing. Pending ideas no longer expire or get silently
  trimmed to five; the email alone selects up to five per category.
- Each email links to its saved dated briefing. Inbox retains that briefing's
  story/angle text and shows the current decision for actioned ideas. The full
  backlog is accessible using All pending ideas.

## Scheduling and delivery

GitHub runs at 07:00 and 08:00 UTC on weekdays. The runtime selects the slot
corresponding to 08:00 Europe/London for the current season. Job concurrency
serializes scheduled and manually dispatched runs. The inactive slot exits;
late active runs fail visibly without sending. Generation must finish before
09:00 UK or the ready snapshot is retained without email. This prioritizes
avoiding late/repeated mail; GitHub cannot guarantee daily punctual delivery.
Recent live runs inspected on 9 September 2026 were delayed into the afternoon.

Only `davidd-pixel/riot-pr-desk` can run the delivery workflow. Do not enable
an older version of the workflow in a copy against the same Drive/mailbox.
Retire other email schedules before enabling this version. Runtime gates also
protect accidental scheduled copies. CLI invocations must not run concurrently
with the Actions job; workflow concurrency is scoped to one repository.

## Shared storage and migration

Existing `riot_db_opportunities.json` remains the source of opportunity records.
Only the briefing job writes it. User decisions are separate immutable
`riot_db_opportunity_action_<uuid>.json` files in the same Drive folder.
Readers overlay these events onto legacy records. A stale job snapshot cannot
overwrite an approval. Each app instance caches downloaded action files and
checks for new events periodically; new instances rebuild from Drive. Actions
on the same idea resolve in timestamp order, with UUID as a tie breaker.

Do not roll back to the old app while continuing the new workflow: old code
does not understand action files. Roll out app and workflow together, outside
the morning window, and prevent in-flight old jobs from writing during rollout.
The old opportunity data is not deleted. Previously skipped ideas are not
restored automatically because intentional skips cannot be distinguished from
old automatic expiration.

Core opportunity/digest cloud failures now stop the operation. Missing or
invalid permissions must not be treated as successful local-only saves.
Duplicate Drive filenames are rejected for reconciliation rather than choosing
an arbitrary old copy. The remaining library services retain their existing
persistence behavior; this repair does not migrate every app datastore.

## Configuration and operator checks

Use Python 3.12. Preserve existing SMTP and Google service-account secrets.
Both Streamlit and Actions must use the same `GOOGLE_DRIVE_FOLDER_ID` and
service-account configuration. If delegated ownership is used, provide
`GOOGLE_DRIVE_OWNER_EMAIL` in both. The optional GitHub repository variables
`ANTHROPIC_MODEL` and `PR_DESK_APP_URL` override the current defaults; set the
same values in Streamlit. Verify model access with Dave's credentials during
rollout, not using the offline tests.

A daily `riot_db_briefing_YYYY-MM-DD.json` stores the exact opportunities and
lifecycle state. `riot_db_latest_briefing.json` points the home dashboard to it.
Before email, the snapshot is saved and read back, then marked `sending`.
Only an acknowledged SMTP call followed by a successful cloud write marks it
`sent`. Normal retries of `sent` do nothing. Legacy `digest_sent.json` is
honored for same-day rollout.

If a run reports uncertain delivery, check the recipient mailbox and SMTP
provider history first. A `sending` state may mean delivery succeeded; it is
never automatically retried. If delivery is confirmed, reconcile that daily
record to `sent` while the job is idle. If non-delivery is confirmed, an operator
can explicitly run `python -m services.autonomous_engine --send-digest
--force-resend` in the morning window with the same configuration and no other
job running. This override reuses the saved snapshot and increments its attempt
count; it can produce a duplicate if used without checking. If the window has
passed, retain the snapshot in the app and wait for the next weekday.

## Validation

Run `python -m unittest discover -s tests -v` and
`python -m compileall -q app.py pages services config utils`.
Tests use synthetic records and mocked remote boundaries; they cover DST and
late starts, duplicates, uncertain SMTP outcome, cloud failure, snapshot
fidelity, stale-write approval preservation, feed failures, UI errors,
navigation and regulatory freshness. They do not send emails or validate live
Drive credentials, provider access or Streamlit deployment settings.
