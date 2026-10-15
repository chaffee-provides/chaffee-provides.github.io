# Chaffee Provides: website

The front end of [ChaffeeProvides.org](https://chaffeeprovides.org), Guidestone Colorado's local-food
directory for Chaffee County. This repo is **only the website**: pages, styles and scripts, hosted on
GitHub Pages in place of the old WordPress site. It holds no scraping or data pipeline.

## Where the data comes from

The producer data lives in [colorado-open-food-web](https://github.com/open-food-web/colorado-open-food-web).
It builds one export for this site (`exports/chaffee-provides.json`, format described in its
`docs/EXPORTS.md`). This site keeps a copy in `data/chaffee-provides.json` and nothing else from the Food Web.

```bash
python scripts/sync_data.py ../colorado-open-food-web/exports/chaffee-provides.json
```

The sync script refuses an export it doesn't understand (wrong format version, counts that don't match,
a hidden address that carries a street address), so a bad release never reaches the published site.
Do not edit `data/chaffee-provides.json` by hand. Monthly updates and Guidestone's review happen in the
Food Web repo, not here. `data/photos.json` and `assets/photos/` are this site's own (photos reused from
the old site with Guidestone's permission; thumbnails in `assets/photos/thumb/`).

## Pages

| Page | What it is |
|---|---|
| `find-food.html` | The map: one pin per place to buy, filters, search, faded pins for places not yet confirmed |
| `directory.html` | Scrolling card list with the same filters and a search box with suggestions |
| `provider.html?slug=` | One business: photo, every place to find them with hours, contact, sources, suggest-an-update and remove buttons |
| `list-your-business.html` | Prototype form (opens an email) with a hidden spam trap |
| `about.html` | About, how listings stay current, contact, attribution |

## Scope (agreed with Guidestone, Oct 2026)

Producer map, producer directory (cards, category filters, name and address search), About, Contact,
and the list-your-business form. Not included: Spotlight blog (dropped), food assistance schedule
(possible later), restaurants (off for now).

## Ideas for later

- **Season tags.** A small tag on a way to buy ("Closing for the season soon", "Opens for the season soon")
  that appears by itself for about a month before a place's season ends or starts. The export already has
  `season_start` / `season_end` on each location but they are empty today, so this needs those dates filled in
  during the monthly review first. Not built yet.

## Run locally

```bash
npx serve . -l 3011
```

`serve.json` turns off clean-URL redirects, which would drop `?id=` query strings.

## Hosting

GitHub Pages from `main`. The custom domain is set with a `CNAME` file once Guidestone controls the
DNS for chaffeeprovides.org. Cost: the domain only. GitHub Pages is free for public repos.

## Before launch

- Remove the "Draft for review" banner and `noindex` tags.
- Copy photos into the repo (they are hotlinked from chaffeeprovides.org).
- Connect the list-your-business form to Guidestone's intake.
- Redirects from old chaffeeprovides.org addresses (needs control of the domain).
- Map basemap key: the prototype uses the Farm Trail's; use a separate key or OpenStreetMap tiles.
