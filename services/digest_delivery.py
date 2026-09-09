"""Daily digest lifecycle. The single GitHub Actions job owns these records.

SMTP has no idempotency key: a stranded 'sending' record requires operator
review, never an automatic retry. Shared storage errors stop delivery.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from services import drive_persistence as drive

UK = ZoneInfo('Europe/London')


class DeliveryWindowClosed(RuntimeError):
    """SMTP was not attempted because its deadline passed."""



def _delivery_time(now):
    local = now.astimezone(UK)
    return local.weekday() < 5 and local.hour >= 8


def active_schedule(now):
    local = now.astimezone(UK)
    hour = 8 - int(local.utcoffset().total_seconds() // 3600)
    return f'0 {hour} * * 1-5'


def scheduled_run_due(now, schedule):
    """The season's intended slot may arrive any time after 08:00 UK."""
    return _delivery_time(now) and schedule == active_schedule(now)


def _filename(briefing_id):
    # Validate before using user-supplied query parameters in a Drive filename.
    date = datetime.strptime(briefing_id, '%Y-%m-%d').date()
    if date.isoformat() != briefing_id:
        raise ValueError('Invalid briefing date')
    return f'briefing_{briefing_id}.json'


def load_briefing(briefing_id=None):
    if not drive.is_configured():
        return None
    if briefing_id is None:
        latest = drive.download_json('latest_briefing.json', strict=True)
        if latest is None:
            return None
        briefing_id = latest['id']
    record = drive.download_json(_filename(briefing_id), strict=True)
    if record is not None and (not isinstance(record, dict) or
            record.get('id') != briefing_id or not isinstance(record.get('opportunities'), list)):
        raise RuntimeError('Invalid saved briefing')
    return record


def select_opportunities(records, per_type=5):
    """Limit only the digest, never mutate or hide the remaining inbox backlog."""
    selected = []
    counts = {}
    for opp in sorted(records, key=lambda o: (o.get('created_at', ''), o.get('relevance_score', 0)), reverse=True):
        kind = opp.get('opportunity_type', 'pr_commentary')
        if kind not in ('pr_commentary', 'newsjacking', 'blog'):
            continue
        if counts.get(kind, 0) < per_type:
            selected.append(opp)
            counts[kind] = counts.get(kind, 0) + 1
    return selected


def deliver_digest(to_email, *, build, send, now=None, force_resend=False):
    now = now or (lambda: datetime.now(timezone.utc))
    started = now()
    briefing_id = started.astimezone(UK).date().isoformat()
    filename = _filename(briefing_id)
    record = drive.download_json(filename, strict=True)
    if record and record.get('status') == 'sent' and not force_resend:
        return 'already_sent'
    if record and record.get('status') == 'sending' and not force_resend:
        raise RuntimeError('Delivery outcome is uncertain. Check the mailbox before explicitly retrying this briefing.')
    if record is None:
        # Honor the old marker when deploying mid-day, but never mask read failures.
        legacy = drive.download_json('digest_sent.json', strict=True)
        if legacy and legacy.get('last_sent_at') and not force_resend:
            previous = datetime.fromisoformat(legacy['last_sent_at'])
            if previous.tzinfo is None:
                previous = previous.replace(tzinfo=timezone.utc)
            if previous.astimezone(UK).date().isoformat() == briefing_id:
                return 'already_sent'
    if not _delivery_time(started):
        raise RuntimeError('Digest delivery starts at 08:00 UK on weekdays; delayed runs remain eligible.')
    if record is None:
        opportunities = select_opportunities(build())
        record = {'id': briefing_id, 'created_at': started.isoformat(),
                  'status': 'ready', 'opportunities': opportunities, 'attempts': 0}
        drive.upload_json(filename, record, strict=True)
        if drive.download_json(filename, strict=True) != record:
            raise RuntimeError('Saved briefing could not be verified; no email sent.')
    if record.get('id') != briefing_id or not isinstance(record.get('opportunities'), list):
        raise RuntimeError('Invalid saved briefing; no email sent.')
    # The Inbox opens this exact snapshot even after subsequent briefings.
    drive.upload_json('latest_briefing.json', {'id': briefing_id}, strict=True)
    current = now()
    if not _delivery_time(current) or current.astimezone(UK).date().isoformat() != briefing_id:
        raise RuntimeError('The UK briefing date changed during preparation; no previous-day email sent.')
    record['status'] = 'sending'
    record['attempts'] += 1
    record['attempted_at'] = current.isoformat()
    drive.upload_json(filename, record, strict=True)
    def before_send():
        instant = now()
        if not _delivery_time(instant) or instant.astimezone(UK).date().isoformat() != briefing_id:
            raise DeliveryWindowClosed('The UK briefing date changed before SMTP send; no previous-day email sent.')

    try:
        success = send(record['opportunities'], to_email, briefing_id=briefing_id, before_send=before_send)
    except DeliveryWindowClosed:
        record['status'] = 'ready'
        drive.upload_json(filename, record, strict=True)
        raise
    if not success:
        raise RuntimeError('Delivery could not be confirmed. Check the mailbox before retrying.')
    record['status'] = 'sent'
    record['sent_at'] = now().isoformat()
    drive.upload_json(filename, record, strict=True)
    return 'sent'


def inbox_opportunities(briefing, current_records):
    """Keep emailed story/angle text while applying current user decisions."""
    current = {o['id']: o for o in current_records}
    pending, handled = [], []
    for saved in briefing['opportunities']:
        opp = dict(saved)
        live = current.get(opp['id'])
        if live is None:
            opp['status'] = 'unavailable'
        else:
            for key in ('status', 'pack_id', 'custom_angle'):
                if key in live:
                    opp[key] = live[key]
        (pending if opp.get('status') == 'pending' else handled).append(opp)
    return pending, handled
