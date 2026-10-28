# Chaffee Provides: data snapshot for Guidestone Colorado

A one-time, static copy of the local-food data behind [ChaffeeProvides.org](https://chaffeeprovides.org),
taken from Colorado Open Food Web release **v2026.10.8** (generated 2026-10-28).
Nothing in this folder updates by itself.

## What is in it

| Item | What it is |
|---|---|
| `chaffee-provides.json` | The file the website runs from. 27 producers, 3 farmers' markets, 2 free-food sites, 4 shops, 38 map pins. Complete, with sources and hours. |
| `csv/producers.csv` | One row per farm, ranch, orchard, food maker and so on. Opens in Excel or Google Sheets. |
| `csv/producer_locations.csv` | One row per place a producer can be found (home base, farm stand, market, store). Joins to `producers.csv` on `producer_id`. |
| `csv/markets.csv`, `csv/free_food_sites.csv`, `csv/shops.csv` | One row per market, free-food site (community fridges) and shop. |
| `site-content/descriptions.json` | 15 business descriptions (only for businesses the site shows), keyed by business `slug`. |
| `site-content/photos.json` | 15 photo records, keyed by `slug`. The image files are in the website's `assets/photos/`. |
| `MANIFEST.json` | The release, counts, and a sha256 checksum for every file, so you can confirm nothing changed. |

## How to read it

- **Status.** 27 of 27 producers are `unverified`: the facts were collected from public sources
  and checked by hand where noted under `sources`, but the business has not yet confirmed them.
- **On map / location precision.** `on_map` says whether the place gets a pin on the Find Food map. `precision`
  of `town` means the exact address is deliberately hidden and only the town is shown; those rows have no street address.
- **Hours.** `hours` is the text shown on the site. Some weekly hours in the JSON are marked `inferred`; check the
  business before relying on them.
- **IDs and slugs.** `id` values (`co-p-…`, `co-m-…`, `co-o-…`, `co-ap-…`) are stable Food Web identifiers.
  `slug` is the business's address on the site (`provider.html?slug=…`).

## How the site uses this

The website reads `chaffee-provides.json` directly (it is `data/chaffee-provides.json` in the site's repository).
There is no server and no live connection to the Food Web, so the site keeps working from this snapshot
indefinitely, with no action needed. Listings will age: phone numbers, hours and seasons change.

## Resuming updates later

The site can switch back to live Food Web data at any time. From the website repository:

```
python scripts/sync_data.py https://github.com/open-food-web/colorado-open-food-web/releases/download/<tag>/open-food-web.json <sha256 from that release's MANIFEST.json>
python scripts/build_export.py      # optional: rebuild this folder from the new data
```

`scripts/scope.json` controls which county, business types and shops the site shows. `sync_data.py` refuses a release
it does not understand (wrong format, mismatched counts, a hidden address that carries a street address, a wrong
checksum), so a bad release never reaches the site. Do not edit `chaffee-provides.json` by hand; corrections go
in the Food Web, then a new release is synced.

## License and credit

- **Listings data** (everything in `chaffee-provides.json` and `csv/`): Colorado Open Food Web, CC BY 4.0. Partner data from Guidestone Colorado. Licensed
  [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/): reuse it freely, with that credit.
- **Descriptions and photos** (`site-content/`): submitted by businesses to the old Chaffee Provides site and reused
  with Guidestone Colorado's permission. They are **not** covered by CC BY. Open question for Guidestone: who owns
  them, and may they be shown on other sites? Until that is settled they stay on this site only.

## Before launch (website checklist)

- Remove the "Draft for review" banner and the `noindex` tags.
- Connect the list-your-business form to Guidestone's intake.
- Set up redirects from old chaffeeprovides.org addresses (needs control of the domain).
- Confirm the map basemap key or switch to OpenStreetMap tiles.
