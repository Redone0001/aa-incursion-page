# Changelog

## 0.1.0

- Add a permission-gated Incursion Status page.
- Poll the public ESI `GetIncursions` operation through Celery every five minutes.
- Store current incursion state and append-only appeared, updated, and ended history.
- Resolve constellation, faction, staging-system, and infested-system names through ESI.

