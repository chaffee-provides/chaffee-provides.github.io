"""Build what search engines need: a real page for every listing, sitemap.xml, and the redirect pages
for the old site's addresses.

    python scripts/build_seo.py

Run by sync_data.py after every data sync, so the pages and the sitemap always match
data/chaffee-provides.json. Safe to run by hand at any time; run it after editing provider.html.

- provider/<slug>/index.html: one page per listing. It is provider.html (the template) with the listing's
  own title, description and a plain-text version of the listing already in the page, so a search engine
  that does not run JavaScript still reads it. In a browser the script in provider.html then draws the
  full listing over it (map, directions, previous / next).
- sitemap.xml: the four pages plus every listing page.
- Redirect pages: GitHub Pages cannot send real redirects, so each old address in scripts/old_urls.json
  gets a tiny index.html that forwards straight away and names the new page as canonical. Search engines
  treat that as a permanent move. An old listing address whose business has no listing today goes to the
  home page.
- A page under provider/ that is no longer wanted (the listing left the data, or its line was taken out of
  old_urls.json) is deleted; 404.html then sends that address to the home page.

The plain-text version is deliberately smaller than what the script draws, and stricter about places: it
gives a street address only for a place that is pinned on the map, and otherwise only the town.
"""
import html, json, os, re, shutil, sys
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
DATA = os.path.join(ROOT, "data", "chaffee-provides.json")
OLD = os.path.join(HERE, "old_urls.json")
TEMPLATE = os.path.join(ROOT, "provider.html")
SITE = "https://chaffeeprovides.org/"
PAGES = ["", "find-food.html", "directory.html", "list-your-business.html"]
LISTS = ("producers", "markets", "access_points", "outlets")
BUILT = "built by scripts/build_seo.py, do not edit"
MARK = "<!-- redirect from the old site; %s -->" % BUILT
PAGE_MARK = "<!-- listing page; %s: edit provider.html or the data instead -->" % BUILT
LOADING = '<main id="main" class="wrap"><p style="padding:40px 0" class="muted">Loading…</p></main>'

# What a listing is called, as on the site (GROUPS in assets/app.js).
SINGLE = {"farm": "Farm", "ranch": "Ranch", "orchard": "Orchard", "bakery": "Bakery", "maker": "Food maker",
          "winery": "Winery", "education": "Agricultural education", "market": "Farmers market", "access": "Free food"}
SHOP = {"apothecary": "Apothecary", "farm_store": "Farm store", "grocery": "Grocer", "garden_center": "Garden center",
        "other_retail": "Shop"}

esc = lambda s: html.escape(str(s if s is not None else ""), quote=True)


def listing_url(slug):
    return "provider/%s/" % quote(slug, safe="")


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def records(d):
    """Every listing as (group, record), in the order the site loads them."""
    for key, group in (("producers", "farm"), ("markets", "market"), ("access_points", "access"), ("outlets", "outlet")):
        for r in d.get(key, []):
            yield group, r


def slugs(d):
    return {r["slug"] for _, r in records(d)}


def label(group, r):
    if group == "outlet":
        return SHOP.get(r.get("kind"), "Shop")
    return SINGLE.get(r.get("producer_type"), "Farm") if group == "farm" else SINGLE[group]


def places(group, r):
    locs = r.get("locations", []) if group == "farm" else [r.get("location")]
    return [l for l in locs if l]


def pinned(l):
    return bool(l.get("pin")) and l.get("lat") is not None


def town(group, r):
    """Where a farm is based (its home town, as the listing says), or where a market, shop or free-food site is."""
    ps = places(group, r)
    if group == "farm":
        for l in ps:
            if l.get("role") == "home_base" and l.get("city"):
                return l["city"]
    for pick in (pinned, lambda l: True):
        for l in ps:
            if pick(l) and l.get("city"):
                return l["city"]
    return ""


def where(l):
    a, c = l.get("address"), l.get("city")
    if a and c and c.lower() not in a.lower():
        return "%s, %s" % (a, c)
    return a or c or ""


def clip(text, n=158):
    text = " ".join(str(text).split())
    if len(text) <= n:
        return text
    return text[:n].rsplit(" ", 1)[0].rstrip(",;:.") + "…"


def http(u):
    return u if re.match(r"https?://", u or "", re.I) else None


def listing(group, r, d, descs, photos, live):
    """(title, description, html) for one listing's plain-text version."""
    name, what, tw = r["name"], label(group, r), town(group, r)
    vocab = d.get("vocab", {}).get("product_groups", {})
    desc = descs.get(r["slug"]) or descs.get(re.sub(r"-outlet$", "", r["slug"])) or ""
    products = ", ".join(r.get("products") or [])
    groups = [vocab.get(g, g) for g in r.get("product_groups") or []]
    title = "%s · %s%s · Chaffee Provides" % (name, what, " in %s, CO" % tw if tw else "")
    # The town is the listing's own; a few farms that serve the county are based just outside it, so the county is not claimed here.
    summary = "%s%s." % (what, (" based in %s, Colorado" if group == "farm" else " in %s, Colorado") % tw if tw else " serving Chaffee County, Colorado")
    guide = "Listed on Chaffee Provides, the local food guide for Chaffee County, Colorado."
    loc = (r.get("location") or {}) if group != "farm" else {}
    extra = [products or ", ".join(groups), where(loc) if loc.get("address") else "", r.get("hours_text") if group != "farm" else ""]
    meta = clip(desc) if desc else clip("%s: %s %s" % (name, summary[0].lower() + summary[1:], " ".join(x.rstrip(".") + "." for x in extra if x)))
    up = "../../"
    out = ['<nav class="crumbs" aria-label="Breadcrumb"><a href="%sfind-food.html">Map</a> › <a href="%sdirectory.html">Directory</a> › %s</nav>'
           % (up, up, esc(name)),
           '<div class="provider"><div>', "<h1>%s</h1>" % esc(name), "<p>%s %s</p>" % (esc(summary), esc(guide))]
    ph = photos.get(r["slug"])
    if ph:
        out.append('<img class="hero-photo" src="%s%s" alt="%s" width="%s" height="%s">'
                   % (up, esc(ph["file"]), esc(ph.get("alt", "")), esc(ph.get("width", "")), esc(ph.get("height", ""))))
    if desc:
        out.append('<div class="about">%s</div>' % "".join("<p>%s</p>" % esc(t) for t in desc.split("\n") if t.strip()))
    if products or groups:
        out.append("<h2>What they offer</h2>")
        if groups:
            out.append("<p>%s</p>" % esc(", ".join(groups)))
        if products:
            out.append("<p>%s</p>" % esc(products))
    # Places: a street address only where the place is pinned on the map.
    spots = []
    for l in places(group, r):
        if pinned(l) or group != "farm":
            hours = l.get("hours_text") or ("" if group == "farm" else r.get("hours_text")) or ""
            named = l.get("name") if l.get("name") not in (l.get("address"), l.get("city")) else None
            spots.append("<li>%s%s%s</li>" % ("<strong>%s</strong><br>" % esc(named) if named else "", esc(where(l)),
                                              "<br>%s" % esc(hours) if hours else ""))
    if spots:
        out.append("<h2>%s</h2><ul>%s</ul>" % ("Location" if group in ("market", "access") else "Places to find them", "".join(spots)))
    # A producer links to the markets it sells at, and a market to its vendors.
    seen, links = set(), []
    for o in r.get("offerings") or []:
        m = o.get("market")
        if m and m.get("slug") in live and m["slug"] not in seen:
            seen.add(m["slug"])
            links.append('<li><a href="../%s/">%s</a></li>' % (quote(m["slug"], safe=""), esc(m["name"])))
    if links:
        out.append("<h2>At the farmers market</h2><ul>%s</ul>" % "".join(links))
    if group == "market":
        here = (r.get("location") or {}).get("id")
        vs = sorted((p for p in d.get("producers", []) if any(l.get("id") == here for l in p.get("locations", []))),
                    key=lambda p: p["name"].lower())
        if vs:
            out.append("<h2>Vendors at this market (%d)</h2><ul>%s</ul>" % (len(vs), "".join(
                '<li><a href="../%s/">%s</a></li>' % (quote(p["slug"], safe=""), esc(p["name"])) for p in vs)))
    facts = []
    if r.get("phone"):
        facts.append('Phone: <a href="tel:%s">%s</a>' % (esc(re.sub(r"[^0-9+]", "", r["phone"])), esc(r["phone"])))
    if http(r.get("website")):
        facts.append('Website: <a href="%s" rel="noopener">%s</a>' % (esc(r["website"]), esc(re.sub(r"^https?://(www\.)?", "", r["website"]).rstrip("/"))))
    if r.get("hours_text") and group == "farm":
        facts.append("Hours: %s" % esc(r["hours_text"]))
    if facts:
        out.append("<h2>Contact</h2><ul>%s</ul>" % "".join("<li>%s</li>" % f for f in facts))
    out.append("</div></div>")
    return title, meta, "\n".join(out)


def page(template, slug, title, meta, body):
    """provider.html with this listing's head and plain-text body, moved two folders down."""
    t = template
    for a, b in (('<html lang="en" data-root=".">\n<head>', '<html lang="en" data-root="../.." data-slug="%s">\n<head>\n%s' % (esc(slug), PAGE_MARK)),
                 ("<title>Listing · Chaffee Provides</title>",
                  '<title>%s</title>\n<meta name="description" content="%s">\n<link rel="canonical" href="%s">'
                  % (esc(title), esc(meta), esc(SITE + listing_url(slug)))),
                 (LOADING, '<main id="main" class="wrap">\n%s\n</main>' % body)):
        if t.count(a) != 1:
            sys.exit("build_seo: provider.html no longer contains %r exactly once; update build_seo.py to match" % a)
        t = t.replace(a, b)
    return t.replace('href="assets/', 'href="../../assets/').replace('src="assets/', 'src="../../assets/')


def sitemap(d):
    day = d["export"]["generated"]
    urls = [SITE + p for p in PAGES] + [SITE + listing_url(s) for s in sorted(slugs(d))]
    rows = ["  <url><loc>%s</loc><lastmod>%s</lastmod></url>" % (html.escape(u), day) for u in urls]
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "\n".join(rows) + "\n</urlset>\n"), len(urls)


def stub(target):
    to = html.escape(SITE + target)
    return ('<!doctype html>\n<html lang="en">\n<head>\n' + MARK + '\n<meta charset="utf-8">\n'
            '<title>This page has moved · Chaffee Provides</title>\n'
            '<link rel="canonical" href="%s">\n<meta http-equiv="refresh" content="0; url=%s">\n'
            '</head>\n<body>\n<p>This page has moved to <a href="%s">%s</a>.</p>\n</body>\n</html>\n' % (to, to, to, to))


def is_ours(path):
    try:
        return BUILT in open(path, encoding="utf-8").read()
    except OSError:
        return False


def read_json(path, key):
    try:
        return json.load(open(path, encoding="utf-8")).get(key) or {}
    except OSError:
        return {}


def main():
    d = json.load(open(DATA, encoding="utf-8"))
    old = json.load(open(OLD, encoding="utf-8"))
    descs = read_json(os.path.join(ROOT, "data", "descriptions.json"), "descriptions")
    photos = read_json(os.path.join(ROOT, "data", "photos.json"), "photos")
    template = open(TEMPLATE, encoding="utf-8").read().replace("\r\n", "\n")
    live = slugs(d)

    for group, r in records(d):
        title, meta, body = listing(group, r, d, descs, photos, live)
        write(os.path.join(ROOT, "provider", r["slug"], "index.html"), page(template, r["slug"], title, meta, body))

    xml, n = sitemap(d)
    write(os.path.join(ROOT, "sitemap.xml"), xml)

    wanted = dict(old["pages"])
    for was, now in old["providers"].items():
        if was in live:
            continue   # the listing's own page lives at the old address
        # no listing on the new site (or it has since left the data): send people to the home page
        wanted["provider/%s/" % was] = listing_url(now) if now in live else ""
    for path, target in wanted.items():
        if path.startswith(("/", ".")) or ".." in path or not path.endswith("/"):
            sys.exit("build_seo: bad old address %r in old_urls.json" % path)
        write(os.path.join(ROOT, path.replace("/", os.sep), "index.html"), stub(target))
    # a page under provider/ that is neither a listing nor a wanted redirect goes
    gone = 0
    pdir = os.path.join(ROOT, "provider")
    for name in (os.listdir(pdir) if os.path.isdir(pdir) else []):
        if name not in live and "provider/%s/" % name not in wanted and is_ours(os.path.join(pdir, name, "index.html")):
            shutil.rmtree(os.path.join(pdir, name))
            gone += 1
    print("%d listing pages; sitemap.xml: %d addresses; %d redirects from old addresses%s"
          % (len(live), n, len(wanted), ", %d removed" % gone if gone else ""))


if __name__ == "__main__":
    main()
