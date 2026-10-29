#!/usr/bin/env python3
"""Build data/chaffee-provides.json from a Colorado Open Food Web release, after checking it.

The Food Web publishes one statewide file per release (open-food-web.json). This site pins a release and
applies its own scope here (scripts/scope.json: county, producer types, shop kinds, pins). The site reads
data/chaffee-provides.json and nothing else from the Food Web, and this script is the only thing that writes it,
so a bad release fails here and never reaches the published site.

Usage:
  python scripts/sync_data.py <path or URL of open-food-web.json> [expected sha256]
  python scripts/sync_data.py ../colorado-open-food-web/release/open-food-web.json
  python scripts/sync_data.py https://github.com/open-food-web/colorado-open-food-web/releases/download/v2026.10.7/open-food-web.json <sha256 from MANIFEST.json>
"""
import hashlib, json, os, sys, urllib.request

SUPPORTED = 3
HERE = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(HERE, "..", "data", "chaffee-provides.json")
SCOPE = os.path.join(HERE, "scope.json")


def fail(msg):
    print("NOT SYNCED: " + msg)
    sys.exit(1)


def load(src):
    if src.startswith("http"):
        return urllib.request.urlopen(urllib.request.Request(src, headers={"User-Agent": "chaffee-provides-sync"}), timeout=60).read()
    return open(src, "rb").read()


def check_statewide(d):
    """The release must be internally consistent and statewide before anything is taken from it."""
    ex = d.get("export") or fail("no 'export' block")
    if ex.get("format_version") != SUPPORTED:
        fail("export format %r, this site understands %r" % (ex.get("format_version"), SUPPORTED))
    for k in ("producers", "markets", "access_points", "outlets"):
        if k not in d:
            fail("the release has no '%s' (is it the statewide open-food-web.json?)" % k)
    c = ex.get("counts", {})
    real = {"producers": len(d["producers"]), "markets": len(d["markets"]), "access_points": len(d["access_points"]),
            "outlets": len(d["outlets"])}
    for k, v in real.items():
        if c.get(k) != v:
            fail("counts say %s=%r but the file has %r" % (k, c.get(k), v))
    if len(ex.get("county_fips", [])) != 64:
        fail("this is not the statewide file (it lists %d counties)" % len(ex.get("county_fips", [])))
    if not d["producers"]:
        fail("no producers in the release")


def apply_scope(d, scope):
    """The Chaffee Provides slice of a statewide release. The rules the Food Web's per-app export used to apply."""
    counties = set(scope["county_fips"])
    sources = set(scope.get("include_sources", []))
    exclude_slugs = set(scope.get("exclude_slugs", {}))
    hide_pin_slugs = set(scope.get("hide_pin_slugs", {}))
    exclude_producer_types = set(scope.get("exclude_producer_types", {}))
    exclude_only_channels = set(scope.get("exclude_only_channels", {}))
    outlet_kinds = set(scope.get("include_outlet_kinds", []))
    show_home = scope.get("show_unconfirmed_home_pins", False)
    outside = {"producers": 0, "markets": 0, "access_points": 0, "outlets": 0}

    def in_area(rec, locs, service=()):
        return (any(l["county_fips"] in counties for l in locs) or bool(counties & set(service))
                or any(s["source"] in sources for s in rec["sources"]))

    producers = []
    for p in d["producers"]:
        chans = set(p["sales_channels"])
        if p["slug"] in exclude_slugs or p["producer_type"] in exclude_producer_types \
                or (chans and chans <= exclude_only_channels):
            continue
        if not in_area(p, p["locations"], p["service_county_fips"]):
            outside["producers"] += 1
            continue
        locs = []
        for l in p["locations"]:
            l = dict(l)
            pin = l["pin"]
            if show_home and l.get("pin_unconfirmed_home") and p["slug"] not in hide_pin_slugs:
                pin = True
            if l["county_fips"] and l["county_fips"] not in counties:
                pin = False       # a place outside these counties is not a place to buy on this map
            l["pin"] = bool(pin and l["lat"] is not None)
            l.pop("pin_unconfirmed_home", None)
            locs.append(l)
        q = {k: v for k, v in p.items() if k != "service_county_fips"}
        q["locations"] = locs
        producers.append(q)
    keep = {p["id"] for p in producers}

    markets = []
    for m in d["markets"]:
        if not in_area(m, [m["location"]]):
            outside["markets"] += 1
            continue
        markets.append(dict(m, vendors=[v for v in m["vendors"] if v in keep]))
    access = []
    for a in d["access_points"]:
        if not in_area(a, [a["location"]]):
            outside["access_points"] += 1
            continue
        access.append(a)
    outlets = []
    for o in d["outlets"]:
        if o["kind"] not in outlet_kinds or o["slug"] in exclude_slugs:
            continue
        if not in_area(o, [o["location"]]):
            outside["outlets"] += 1
            continue
        outlets.append(o)

    ex = d["export"]
    counts = {"producers": len(producers), "markets": len(markets), "access_points": len(access),
              "market_links": sum(1 for p in producers for o in p.get("offerings", []) if o.get("market")),
              "outlets": len(outlets), "outlet_pins": sum(o["location"]["pin"] for o in outlets),
              "pins": sum(l["pin"] for p in producers for l in p["locations"]) + len(markets) + len(access),
              "excluded_outside_area": outside}
    vocab = dict(d["vocab"])
    vocab["counties"] = {c: n for c, n in vocab["counties"].items() if c in counties}
    vocab["outlet_kinds"] = {k: v for k, v in vocab.get("outlet_kinds", {}).items() if k in outlet_kinds}
    return {
        "export": {"app": "chaffee-provides", "format_version": ex["format_version"], "release": ex["release"],
                   "generated": ex["generated"], "source": ex["source"], "county_fips": sorted(counties),
                   "attribution": ex["attribution"], "counts": counts},
        "vocab": vocab, "producers": producers, "markets": markets, "access_points": access, "outlets": outlets,
        "removed_ids": d["removed_ids"]}


def check_scoped(d):
    """Public-safety checks on what will be published."""
    for p in d["producers"]:
        for l in p["locations"]:
            if l["precision"] == "town" and (l["address"] or l["zip"]):
                fail("%s has a hidden location with an address" % p["name"])
    for o in d["outlets"]:
        if o["location"]["precision"] == "town" and (o["location"]["address"] or o["location"]["zip"]):
            fail("%s has a hidden location with an address" % o["name"])
    if not d["producers"]:
        fail("the scope leaves no producers")


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else fail("give the path or address of open-food-web.json")
    raw = load(src)
    if len(sys.argv) > 2 and hashlib.sha256(raw).hexdigest() != sys.argv[2].lower():
        fail("sha256 of the release file does not match the one given")
    d = json.loads(raw.decode("utf-8"))
    check_statewide(d)
    out = apply_scope(d, json.load(open(SCOPE, encoding="utf-8")))
    check_scoped(out)
    old = json.load(open(DEST, encoding="utf-8"))["export"] if os.path.exists(DEST) else None
    os.makedirs(os.path.dirname(DEST), exist_ok=True)
    with open(DEST, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    ex, c = out["export"], out["export"]["counts"]
    print("synced release %s (generated %s): %d producers, %d markets, %d free-food sites, %d shops, %d pins"
          % (ex["release"], ex["generated"], c["producers"], c["markets"], c["access_points"], c["outlets"], c["pins"]))
    if old:
        print("previous: release %s, %d pins" % (old["release"], old["counts"]["pins"]))


if __name__ == "__main__":
    main()
