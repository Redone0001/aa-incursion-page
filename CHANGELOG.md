# Changelog

## 0.3.2

- Resolve and display the SDE region name in the incursion card header.

## 0.3.1

- Add the systems shown in the supplied incursion screenshots to the bundled layout.
- Remove the attacking faction and incursion type fields from the page display.

## 0.3.0

- Colour incursion state badges by established, mobilizing, and withdrawing state.
- Use django-eveonline-sde/modeltranslation for map names and security status.
- Bundle the incursion layout CSV, label site roles, and display Headquarters.

## 0.2.0

## 0.1.0

- Add a permission-gated Incursion Status page.
- Poll the public ESI `GetIncursions` operation through Celery every five minutes.
- Store current incursion state and append-only appeared, updated, and ended history.
- Resolve constellation, faction, staging-system, and infested-system names through ESI.
