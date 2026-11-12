#!/usr/bin/env python3
"""Keep businesses that opted out of Chaffee Provides out of everything the site publishes.

The table is scripts/opt_outs.json. This module does three things with it:
  scrub(d)        removes opted-out producers, shops, markets and free-food sites from a scoped export (sync_data.py)
  violations(...) looks for any trace of an entry in the files the site publishes, independently of scrub
  main()          the command line: check (used by CI), list, apply

Usage:
  python scripts/opt_outs.py check    exit 1 if any opted-out business appears anywhere it should not
  python scripts/opt_outs.py list     the table, one line per business
  python scripts/opt_outs.py apply    remove opted-out businesses from data/chaffee-provides.json in place,
                                      then rebuild the Guidestone export with build_export.py
"""
import csv, datetime, glob, io, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
TABLE = os.path.join(HERE, "opt_outs.json")
DATA = os.path.join(ROOT, "data", "chaffee-provides.json")
LISTS = ("producers", "markets", "access_points", "outlets")
# every file the site or Guidestone's snapshot publishes; the table and scope.json are the only places an opted-out name may live
PUBLISHED = ["data/*.json", "guidestone-export/**/*", "assets/*.js", "assets/*.css", "*.html", "CNAME", "serve.json",
             "sitemap.xml", "provider/**/*"]


def fail(msg):
    print("OPT-OUT BLOCK: " + msg)
    sys.exit(1)


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def norm_url(u):
    u = re.sub(r"^[a-z]+://", "", (u or "").strip().lower())
    return re.sub(r"^www\.", "", u).rstrip("/")


def load_table(path=TABLE):
    """The entries, checked: a malformed table must stop the build, never silently block nothing."""
    with open(path, encoding="utf-8") as f:
        t = json.load(f)
    entries = t.get("opted_out")
    if not isinstance(entries, list):
        fail("opt_outs.json has no 'opted_out' list")
    seen = set()
    for e in entries:
        for k in ("name", "recorded_on", "recorded_by", "note"):
            if not e.get(k):
                fail("an entry (%r) is missing '%s'" % (e.get("name"), k))
        try:
            datetime.date.fromisoformat(e["recorded_on"])
        except ValueError:
            fail("%s: recorded_on must be YYYY-MM-DD" % e["name"])
        if not (e.get("ids") or e.get("slugs") or e.get("urls") or e.get("emails")):
            fail("%s needs at least one id, slug, url or email so it can be found again under another name" % e["name"])
        for k in ("aliases", "ids", "slugs", "urls", "emails"):
            if not isinstance(e.get(k, []), list):
                fail("%s: '%s' must be a list" % (e["name"], k))
        key = norm(e["name"])
        if key in seen:
            fail("%s is listed twice" % e["name"])
        seen.add(key)
    return [e for e in entries if not e.get("reinstated_on")]


def names(e):
    return {norm(n) for n in [e["name"]] + e.get("aliases", []) if norm(n)}


def strip_the(n):
    return n[4:] if n.startswith("the ") else n


def matches(e, rec):
    """Does this producer, shop, market or free-food site belong to an opted-out business?"""
    slug = rec.get("slug", "")
    if rec.get("id") in e.get("ids", []) or slug in e.get("slugs", []) or slug.replace("-outlet", "") in e.get("slugs", []):
        return True
    rn = norm(rec.get("name"))
    if any(" " + n + " " in " " + rn + " " for n in names(e)) or any(strip_the(n) == strip_the(rn) for n in names(e)):
        return True
    for k in ("website", "facebook", "instagram"):
        u = norm_url(rec.get(k))
        if u and any(u == x or u.startswith(x + "/") or u.startswith(x + "?") or ("/" not in x and u.split("/")[0].endswith(x))
                     for x in map(norm_url, e.get("urls", []))):
            return True
    return (rec.get("email") or "").lower() in {x.lower() for x in e.get("emails", [])} and bool(rec.get("email"))


def recount(d):
    """Counts in the export block follow the lists, so the counts check in build_export.py keeps passing."""
    c = d["export"]["counts"]
    c["producers"], c["markets"] = len(d["producers"]), len(d["markets"])
    c["access_points"], c["outlets"] = len(d["access_points"]), len(d["outlets"])
    if any("sells_at" in p for p in d["producers"]):                 # format 2
        c["market_links"] = sum(len(p["sells_at"]) for p in d["producers"])
    else:                                                          # format 3
        c["market_links"] = sum(1 for p in d["producers"] for o in p.get("offerings", []) if o.get("market"))
    c["outlet_pins"] = sum(o["location"]["pin"] for o in d["outlets"])
    c["pins"] = (sum(l["pin"] for p in d["producers"] for l in p["locations"]) + len(d["markets"])
                 + len(d["access_points"]))


def scrub(d, entries=None):
    """Remove every opted-out business from a scoped export, and every reference to it. Returns what was removed."""
    entries = load_table() if entries is None else entries
    removed = []
    for k in LISTS:
        keep = []
        for rec in d[k]:
            hit = next((e for e in entries if matches(e, rec)), None)
            if hit:
                removed.append((k, rec["name"], hit["name"]))
            else:
                keep.append(rec)
        d[k] = keep
    gone = {i for e in entries for i in e.get("ids", [])}
    for m in d["markets"]:
        m["vendors"] = [v for v in m["vendors"] if v not in gone]
    for p in d["producers"]:
        if "sells_at" in p:
            p["sells_at"] = [s for s in p["sells_at"] if s.get("market_id") not in gone]
        if "offerings" in p:
            p["offerings"] = [o for o in p["offerings"] if (o.get("market") or {}).get("id") not in gone]
    recount(d)
    return removed


def terms(e):
    """Strings that must not appear anywhere published, lower-cased."""
    t = {n for n in names(e)}
    t |= {i.lower() for i in e.get("ids", [])} | {s.lower() for s in e.get("slugs", [])}
    t |= {norm_url(u) for u in e.get("urls", [])} | {x.lower() for x in e.get("emails", [])}
    return {x for x in t if x}


def published_files():
    seen = []
    for pat in PUBLISHED:
        for p in glob.glob(os.path.join(ROOT, pat), recursive=True):
            if os.path.isfile(p) and p not in seen:
                seen.append(p)
    return seen


def violations(entries=None, files=None):
    """Independent of scrub(): read the published files as plain text and report any trace of an entry."""
    entries = load_table() if entries is None else entries
    found = []
    for p in published_files() if files is None else files:
        try:
            with open(p, encoding="utf-8-sig") as f:
                text = f.read()
        except UnicodeDecodeError:
            continue                                  # an image or other binary file
        low = text.lower()
        flat = norm(text)
        rel = os.path.relpath(p, ROOT).replace(os.sep, "/")
        for e in entries:
            for t in sorted(terms(e)):
                hay = flat if " " in t else low           # names are compared as plain words, ids and addresses as written
                if re.search(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])", hay):
                    found.append((rel, e["name"], t))
                    break
    return found


def photo_assets(entries):
    """Photo files named for an opted-out business (assets/photos/<slug>...), so a leftover image is also caught."""
    out = []
    for p in glob.glob(os.path.join(ROOT, "assets", "photos", "**", "*"), recursive=True):
        if os.path.isfile(p):
            base = norm(os.path.splitext(os.path.basename(p))[0])
            for e in entries:
                if any(norm(t) and norm(t) in base for t in list(names(e)) + e.get("slugs", [])):
                    out.append((os.path.relpath(p, ROOT).replace(os.sep, "/"), e["name"], "file name"))
    return out


def check_or_fail(entries=None, files=None, what="the published files"):
    entries = load_table() if entries is None else entries
    bad = violations(entries, files) + photo_assets(entries)
    if bad:
        lines = ["%s mentions %s (%r)" % (f, n, t) for f, n, t in bad]
        fail("%d trace(s) of businesses that opted out in %s:\n  %s\nRemove them (python scripts/opt_outs.py apply, or fix "
             "the source), then run again." % (len(bad), what, "\n  ".join(lines)))
    return len(entries)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    entries = load_table()
    if cmd == "list":
        for e in entries:
            print("%-24s opted out %s  (%s)  %s" % (e["name"], e["recorded_on"], e["recorded_by"], e["note"]))
        print("%d businesses opted out" % len(entries))
    elif cmd == "check":
        n = check_or_fail(entries)
        print("ok: none of the %d opted-out business(es) appear in the %d published files" % (n, len(published_files())))
    elif cmd == "apply":
        with open(DATA, encoding="utf-8") as f:
            d = json.load(f)
        removed = scrub(d, entries)
        with open(DATA, "w", encoding="utf-8", newline="\n") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
            f.write("\n")
        for k, n, who in removed:
            print("removed %s: %s (opted out: %s)" % (k, n, who))
        if not removed:
            print("nothing to remove from data/chaffee-provides.json")
        for fn, key in (("descriptions.json", "descriptions"), ("photos.json", "photos")):
            path = os.path.join(ROOT, "data", fn)
            with open(path, encoding="utf-8") as f:
                content = json.load(f)
            drop = [s for s in content[key] if any(matches(e, {"slug": s, "id": s}) for e in entries)]
            for s in drop:
                del content[key][s]
                print("removed %s entry: %s" % (key, s))
            if drop:
                with open(path, "w", encoding="utf-8", newline="\n") as f:
                    json.dump(content, f, ensure_ascii=False, indent=1)
                    f.write("\n")
        print("now run: python scripts/build_export.py")
    else:
        fail("unknown command %r (check, list, apply)" % cmd)


if __name__ == "__main__":
    main()
