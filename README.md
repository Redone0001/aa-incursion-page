# Incursion Status for Alliance Auth

A small Alliance Auth 5 app that displays current EVE Online incursions and keeps
an append-only history of meaningful changes.

## Features

- Retrieves the public ESI `GetIncursions` operation every five minutes.
- Uses Alliance Auth's bundled `django-esi` client, HTTP cache, ETags, rate-limit
  handling, and required User-Agent configuration.
- Resolves faction, constellation, staging-system, and infested-system names with
  one `PostUniverseNames` request.
- Records appeared, updated, and ended events while avoiding duplicate history
  rows for unchanged responses.
- Displays influence, state, mothership availability, staging system, and infested
  systems on an Alliance Auth Bootstrap 5 page.
- Hides both the page and sidebar item unless the user has the
  `incursionstatus.incursion_view` permission.

The app does not need an ESI access token or additional SSO scopes because both ESI
operations are public.

## Requirements

- Alliance Auth 5.x
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
python manage.py collectstatic --noinput
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
history event.

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
