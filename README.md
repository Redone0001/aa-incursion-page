# Incursion Status for Alliance Auth

A small Alliance Auth 5 app that displays current EVE Online incursions and keeps
an append-only history of meaningful changes.

## Features

- Retrieves the public ESI `GetIncursions` operation every five minutes.
- Uses Alliance Auth's bundled `django-esi` client, HTTP cache, ETags, rate-limit
  handling, and required User-Agent configuration.
- Resolves region, constellation, and system names, security status, and localized display
  text from `django-eveonline-sde`/`modeltranslation`; faction names use ESI.
- Uses the bundled `incursion_layout.csv` to label Vanguard, Assault, and
  Headquarter systems and displays the Headquarter system instead of staging.
- Records appeared, updated, and ended events while avoiding duplicate history
  rows for unchanged responses.
- Displays influence, state, mothership availability, staging system, and infested
  systems on an Alliance Auth Bootstrap 5 page.
- Colours state badges green for established, orange for mobilizing, and red for
  withdrawing. Card borders use the staging system security: green above 0.5,
  orange from 0.0 through 0.5, and red below 0.0.
- Hides both the page and sidebar item unless the user has the
  `incursionstatus.incursion_view` permission.

The app does not need an ESI access token or additional SSO scopes because both ESI
operations are public.

## Requirements

- Alliance Auth 5.x
- Django EVE Online SDE 0.2.x, loaded with `modeltranslation`
- Django-ESI 9.4 or later in the 9.x series
- A working Alliance Auth Celery worker and Celery Beat scheduler

## Installation

Activate the Alliance Auth virtual environment and install the latest version
directly from GitHub:

```shell
source venv/bin/activate
python -m pip install git+https://github.com/Redone0001/aa-incursion-page.git
```

For an editable development installation, run this from the directory containing
the Alliance Auth project and this repository:

```shell
source venv/bin/activate
python -m pip install -e ./aa-incursion-page
```

Add the app and five-minute schedule to your project's `settings/local.py`:

```python
from celery.schedules import crontab

# django-eveonline-sde requires modeltranslation to be first, and provides the
# constellation/system names and security values used by this app.
INSTALLED_APPS = ["modeltranslation", "eve_sde"] + INSTALLED_APPS
INSTALLED_APPS += ["incursionstatus"]

CELERYBEAT_SCHEDULE["incursionstatus_update_incursions"] = {
    "task": "incursionstatus.update_incursions",
    "schedule": crontab(minute="*/5"),
    "apply_offset": True,
}
```

Then initialize the database and static files:

```shell
python manage.py migrate
python manage.py esde_load_sde
python manage.py collectstatic --noinput
```

Keep the SDE data current using its daily task as well:

```python
CELERYBEAT_SCHEDULE["eve_sde_check_for_updates"] = {
    "task": "eve_sde.tasks.check_for_sde_updates",
    "schedule": crontab(minute="0", hour="12"),
}
```

Restart Alliance Auth's Gunicorn, Celery worker, and Celery Beat processes. The first
scheduled update will run within five minutes. To request an immediate first update:

```shell
python manage.py shell -c "from incursionstatus.tasks import update_incursions; update_incursions.delay()"
```

## Access control

In the Alliance Auth admin site, create or choose an AA group/role named
`incursion-view` and grant it this Django permission:

```text
incursionstatus | general | Can view incursion status
```

The permission identifier used by the code is:

```text
incursionstatus.incursion_view
```

Authorized users will see **Incursion Status** in the sidebar at `/incursions/`.

## Data model

- `Incursion` contains the latest state for each constellation. Ended incursions are
  retained with `is_active=False`, so a later recurrence can begin a new active
  period without losing history.
- `IncursionChange` stores a full snapshot and the list of fields that changed for
  each appeared, updated, or ended event.
- `IncursionSyncStatus` stores the most recent attempt, success, change, and ESI
  error for display and operational checks.

Influence changes are recorded exactly as supplied by ESI. Infested-system IDs are
sorted before comparison so a harmless ordering change does not create a false
history event. The CSV layout is matched against the English SDE system names so
it remains stable when modeltranslation serves another locale.

## Testing

```shell
python runtests.py -v 2
```

To check formatting and migrations:

```shell
ruff check .
python -m django makemigrations incursionstatus --check --dry-run \
  --settings=testauth.settings.local
```

## ESI compatibility date

The app is pinned to ESI compatibility date `2026-05-19`, matching the tested
Alliance Auth 5.2 ESI generation. Advance the date only after testing the app against
the newer ESI contract.

## License

GPL-3.0-or-later.

## Discord notifications

Install the optional client dependency in the Auth environment:

```shell
python -m pip install 'aa-incursion-status[discord] @ git+https://github.com/Redone0001/aa-incursion-page.git'
python manage.py migrate
```

Run a Discord Proxy server following its
[operations guide](https://discordproxy.readthedocs.io/en/latest/operations.html).
The proxy bot needs access to the destination channel and permission to send
messages. To ping a role, that role must be mentionable or the bot must have the
appropriate mention permission.

Add this independent delivery schedule to Auth settings and restart Celery workers
and Beat:

```python
INCURSIONSTATUS_DISCORD_PROXY_TARGET = "localhost:50051"
CELERYBEAT_SCHEDULE["incursionstatus_deliver_notifications"] = {
    "task": "incursionstatus.deliver_notifications",
    "schedule": crontab(minute="*"),
}
```

In **Admin → Incursion Status → Notification rules**, add a rule with:

- A name and enabled switch.
- An exact region name, case-insensitive, matching the name stored by the ESI
  worker (leave blank for all regions).
- A Discord channel ID and optional Discord role ID, copied using Discord's
  Developer Mode.
- Events: spawn, disappearance, phase change, boss availability change, or
  influence change. Spawn and disappearance are enabled by default.

Create separate rules for multiple regions or destinations. Django's normal
notification-rule add/change/delete permissions control who can manage these
settings; the page-view permission alone does not grant administration access.

An incursion stays in its constellation: another location appearing is a new
spawn, and the old location disappearing is a separate event. Recurrence in the
same constellation after disappearance is also a new spawn. Unchanged polls and
map-name/layout enrichment do not trigger notifications. Multiple selected fields
changing in one update produce one message per rule. Influence alerts can be
frequent, so they are off by default.

Rules apply to newly observed events only; existing history is not replayed.
On the first ever synchronization, currently active incursions count as spawns.
Events and their pending messages are saved in one database transaction. Delivery
uses the event's saved location, destination, and role, even if a later event or
rule edit changes them. Disabling a rule pauses its pending messages; deleting it
removes them. Re-enabling resumes pending delivery.

**Notification deliveries** in admin shows message content, attempts, errors, and
delivery time. Each delivery run processes up to 100 pending messages and retries
failures on the next run, independently of ESI availability. Already successful
messages are skipped. Delivery is at least once: a timeout or worker crash after
Discord accepts a message but before the database records success can cause a
duplicate on retry. No live Discord test is sent automatically.
