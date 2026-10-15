#!/usr/bin/env python3
"""Copy the Chaffee Provides export from the Colorado Open Food Web into data/, after checking it.

The site reads data/chaffee-provides.json and nothing else from the Food Web. This script is the only
thing that writes it, so a bad export fails here and never reaches the published site.

Usage:
  python scripts/sync_data.py <path or URL of chaffee-provides.json>
  python scripts/sync_data.py ../colorado-open-food-web/exports/chaffee-provides.json
  python scripts/sync_data.py https://raw.githubusercontent.com/open-food-web/colorado-open-food-web/main/exports/chaffee-provides.json
"""
import json, os, sys, urllib.request

SUPPORTED = 1
HERE = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(HERE, "..", "data", "chaffee-provides.json")

def fail(msg):
    print("NOT SYNCED: " + msg)
    sys.exit(1)

src = sys.argv[1] if len(sys.argv) > 1 else fail("give the path or address of the export")
raw = (urllib.request.urlopen(urllib.request.Request(src, headers={"User-Agent": "chaffee-provides-sync"}), timeout=30).read()
       if src.startswith("http") else open(src, "rb").read())
d = json.loads(raw.decode("utf-8"))
ex = d.get("export") or fail("no 'export' block")
if ex.get("format_version") != SUPPORTED:
    fail("export format %r, this site understands %r" % (ex.get("format_version"), SUPPORTED))
counts = ex.get("counts", {})
real = {"producers": len(d["producers"]), "markets": len(d["markets"]), "access_points": len(d["access_points"]),
        "pins": sum(l["pin"] for p in d["producers"] for l in p["locations"]) + len(d["markets"]) + len(d["access_points"])}
for k, v in real.items():
    if counts.get(k) != v:
        fail("counts say %s=%r but the file has %r" % (k, counts.get(k), v))
if not d["producers"]:
    fail("no producers in the export")
# Public-safety check: a hidden address must never carry a street address or an exact pin.
for p in d["producers"]:
    for l in p["locations"]:
        if l["precision"] == "town" and (l["address"] or l["zip"]):
            fail("%s has a hidden location with an address" % p["name"])
old = json.load(open(DEST, encoding="utf-8"))["export"] if os.path.exists(DEST) else None
os.makedirs(os.path.dirname(DEST), exist_ok=True)
with open(DEST, "wb") as f:
    f.write(raw)
print("synced release %s (generated %s): %d producers, %d markets, %d free-food sites, %d pins"
      % (ex["release"], ex["generated"], real["producers"], real["markets"], real["access_points"], real["pins"]))
if old:
    print("previous: release %s, %d pins" % (old["release"], old["counts"]["pins"]))
