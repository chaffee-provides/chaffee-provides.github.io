#!/usr/bin/env python3
"""Build guidestone-export/: a static snapshot of the Chaffee Provides data for Guidestone Colorado.

Reads data/chaffee-provides.json (written by sync_data.py) plus this site's own descriptions and photos,
and writes the snapshot folder: the JSON the site runs from, spreadsheet-friendly CSVs, the site-owned content,
a MANIFEST.json with a sha256 for every file, and a README.md filled in from scripts/export_readme.md.
Rebuilding is safe: the folder is regenerated from scratch, and the script re-reads what it wrote to verify it.

Usage:  python scripts/build_export.py
"""
import csv, hashlib, json, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "guidestone-export")


def fail(msg):
    print("NOT EXPORTED: " + msg)
    sys.exit(1)


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def split(entries, keep):
    return ({k: v for k, v in entries.items() if k in keep}, sorted(k for k in entries if k not in keep))


def cell(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, list):
        return "; ".join(str(x) for x in v)
    return v


def hours_cell(rec):
    return rec.get("hours_text") or ""


def write_csv(path, columns, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:   # BOM so Excel reads UTF-8
        w = csv.writer(f)
        w.writerow(columns)
        for r in rows:
            w.writerow([cell(r.get(c)) for c in columns])


def sources_cell(rec):
    return "; ".join(s["label"] for s in rec.get("sources", []))


def place_row(rec, loc, group, **extra):
    row = {"id": rec["id"], "name": rec["name"], "group": group, "slug": rec["slug"], "address": loc.get("address"),
           "city": loc.get("city"), "zip": loc.get("zip"), "county_fips": loc.get("county_fips"), "lat": loc.get("lat"),
           "lon": loc.get("lon"), "location_precision": loc.get("precision"), "on_map": loc.get("pin"),
           "phone": rec.get("phone"), "email": rec.get("email"), "website": rec.get("website"),
           "facebook": rec.get("facebook"), "instagram": rec.get("instagram"), "hours": hours_cell(rec),
           "status": rec.get("status"), "last_verified": rec.get("last_verified"), "sources": sources_cell(rec)}
    row.update(extra)
    return row


def build_csvs(d, out):
    v = d["vocab"]
    ptypes = v.get("producer_types", {})
    channels = v["sales_channels"]
    counties = v["counties"]
    os.makedirs(out, exist_ok=True)

    producers, locations = [], []
    for p in d["producers"]:
        producers.append({
            "id": p["id"], "name": p["name"], "slug": p["slug"],
            "type": ptypes.get(p["producer_type"], p["producer_type"]),
            "products": p["products"], "product_groups": p["product_groups"],
            "sales_channels": [channels.get(c, c) for c in p["sales_channels"]],
            "months_open": p["months_open"], "hours": hours_cell(p), "farm_visits": p["visits"],
            "visit_note": p["visit_note"], "call_first": p["call_first"],
            "certified_organic": p["certified_organic"], "accepts_snap": p["accepts_snap"],
            "ada_accessible": p["ada_accessible"], "phone": p["phone"], "email": p["email"],
            "website": p["website"], "facebook": p["facebook"], "instagram": p["instagram"],
            "sells_at_market_ids": p["sells_at"], "locations": len(p["locations"]),
            "status": p["status"], "last_verified": p["last_verified"], "sources": sources_cell(p)})
        for l in p["locations"]:
            locations.append({
                "location_id": l["id"], "producer_id": p["id"], "producer": p["name"], "role": l["role"],
                "place_name": l["name"], "address": l["address"], "city": l["city"], "zip": l["zip"],
                "county": counties.get(l["county_fips"], l["county_fips"]), "lat": l["lat"], "lon": l["lon"],
                "precision": l["precision"], "on_map": l["pin"], "hours": l["hours_text"], "days": l["days"],
                "season_start": l["season_start"], "season_end": l["season_end"], "status": l["status"]})
    write_csv(os.path.join(out, "producers.csv"), list(producers[0]), producers)
    write_csv(os.path.join(out, "producer_locations.csv"), list(locations[0]), locations)

    place_cols = list(place_row(d["markets"][0], d["markets"][0]["location"], "", operator=None, vendor_ids=None,
                                days=None, accepts_snap=None, ada_accessible=None, kind=None))
    markets = [place_row(m, m["location"], "farmers_market", operator=m["operator"], vendor_ids=m["vendors"],
                         days=m["days"], accepts_snap=m["accepts_snap"], ada_accessible=m["ada_accessible"])
               for m in d["markets"]]
    free = [place_row(a, a["location"], "free_food_site", kind=a["kind"]) for a in d["access_points"]]
    shops = [place_row(o, o["location"], "shop", kind=v.get("outlet_kinds", {}).get(o["kind"], o["kind"]))
             for o in d["outlets"]]
    write_csv(os.path.join(out, "markets.csv"), place_cols, markets)
    write_csv(os.path.join(out, "free_food_sites.csv"), place_cols, free)
    write_csv(os.path.join(out, "shops.csv"), place_cols, shops)
    return {"producers.csv": len(producers), "producer_locations.csv": len(locations), "markets.csv": len(markets),
            "free_food_sites.csv": len(free), "shops.csv": len(shops)}


def main():
    src = os.path.join(DATA, "chaffee-provides.json")
    d = read_json(src)
    ex, c = d["export"], d["export"]["counts"]
    for k, key in (("producers", "producers"), ("markets", "markets"), ("access_points", "access_points"),
                   ("outlets", "outlets")):
        if c[k] != len(d[key]):
            fail("counts say %s=%s but the file has %d; run sync_data.py again" % (k, c[k], len(d[key])))
    if ex["release"].startswith("local"):
        fail("the data is pinned to %r, not a tagged Food Web release; run sync_data.py with a release URL" % ex["release"])
    desc = read_json(os.path.join(DATA, "descriptions.json"))
    photos = read_json(os.path.join(DATA, "photos.json"))
    # the site matches an outlet to its description or photo by slug, with "-outlet" removed
    slugs = {r["slug"].replace("-outlet", "") if r in d["outlets"] else r["slug"]
             for k in ("producers", "markets", "access_points", "outlets") for r in d[k]}
    desc["descriptions"], dropped_d = split(desc["descriptions"], slugs)
    photos["photos"], dropped_p = split(photos["photos"], slugs)
    for name, dropped in (("descriptions", dropped_d), ("photos", dropped_p)):
        if dropped:
            print("note: left out %s for businesses the site no longer shows: %s" % (name, ", ".join(dropped)))

    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, "site-content"))
    shutil.copyfile(src, os.path.join(OUT, "chaffee-provides.json"))
    rows = build_csvs(d, os.path.join(OUT, "csv"))
    for f, content in (("descriptions.json", desc), ("photos.json", photos)):
        with open(os.path.join(OUT, "site-content", f), "w", encoding="utf-8", newline="\n") as fh:
            json.dump(content, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
    photo_files = sorted({p[k] for p in photos["photos"].values() for k in ("file", "thumb") if p.get(k)})
    missing = [f for f in photo_files if not os.path.exists(os.path.join(ROOT, f))]
    if missing:
        fail("photos.json points at files that are not in the repo: " + ", ".join(missing))

    with open(os.path.join(HERE, "export_readme.md"), encoding="utf-8") as f:
        readme = f.read()
    fill = {"release": ex["release"], "generated": ex["generated"], "attribution": ex["attribution"],
            "producers": c["producers"], "markets": c["markets"], "access_points": c["access_points"],
            "outlets": c["outlets"], "pins": c["pins"], "descriptions": len(desc["descriptions"]),
            "photos": len(photos["photos"]), "unverified": sum(p["status"] == "unverified" for p in d["producers"])}
    for k, val in fill.items():
        readme = readme.replace("{" + k + "}", str(val))
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(readme)

    files = {}
    for dirpath, _, names in os.walk(OUT):
        for n in sorted(names):
            p = os.path.join(dirpath, n)
            rel = os.path.relpath(p, OUT).replace(os.sep, "/")
            files[rel] = {"sha256": sha256(p)}
            if rel.startswith("csv/"):
                files[rel]["rows"] = rows[n]
    for f in photo_files:   # the image files live in the site (assets/photos), not copied here
        files["(site) " + f] = {"sha256": sha256(os.path.join(ROOT, f))}
    manifest = {"name": "Chaffee Provides data snapshot for Guidestone Colorado", "food_web_release": ex["release"],
                "generated": ex["generated"], "format_version": ex["format_version"], "county_fips": ex["county_fips"],
                "license": "Food Web data: CC BY 4.0. Descriptions and photos: used with Guidestone's permission, see README.",
                "attribution": ex["attribution"], "counts": c, "files": files}
    with open(os.path.join(OUT, "MANIFEST.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
        f.write("\n")

    # verify what was written
    for rel, info in files.items():
        p = os.path.join(ROOT, rel[7:]) if rel.startswith("(site) ") else os.path.join(OUT, rel)
        if sha256(p) != info["sha256"]:
            fail("hash mismatch on " + rel)
        if "rows" in info:
            with open(p, encoding="utf-8-sig", newline="") as f:
                if sum(1 for _ in csv.reader(f)) - 1 != info["rows"]:
                    fail("row count mismatch in " + rel)
    if read_json(os.path.join(OUT, "chaffee-provides.json")) != d:
        fail("the exported JSON differs from data/chaffee-provides.json")
    print("exported %s (generated %s): %d files, %d producers, %d markets, %d free-food sites, %d shops"
          % (ex["release"], ex["generated"], len(files), c["producers"], c["markets"], c["access_points"], c["outlets"]))


if __name__ == "__main__":
    main()
