"""Build what search engines need: sitemap.xml and the redirect pages for the old site's addresses.

    python scripts/build_seo.py

Run by sync_data.py after every data sync, so the sitemap always lists exactly the listings in
data/chaffee-provides.json. Safe to run by hand at any time.

- sitemap.xml: the four pages plus one address per listing (provider.html?slug=...).
- Redirect pages: GitHub Pages cannot send real redirects, so each old address in scripts/old_urls.json
  gets a tiny index.html that forwards straight away and names the new page as canonical. Search engines
  treat that as a permanent move.
- A redirect to a listing that has left the data (closed, out of scope, opted out) is deleted, so the old
  address falls through to 404.html.
"""
import html, json, os, shutil, sys
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
DATA = os.path.join(ROOT, "data", "chaffee-provides.json")
OLD = os.path.join(HERE, "old_urls.json")
SITE = "https://chaffeeprovides.org/"
PAGES = ["", "find-food.html", "directory.html", "list-your-business.html"]
LISTS = ("producers", "markets", "access_points", "outlets")
MARK = "<!-- redirect from the old site; built by scripts/build_seo.py, do not edit -->"


def listing_url(slug):
    return "provider.html?slug=" + quote(slug, safe="")


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def sitemap(d):
    day = d["export"]["generated"]
    urls = [SITE + p for p in PAGES] + [SITE + listing_url(s) for s in sorted(slugs(d))]
    rows = ["  <url><loc>%s</loc><lastmod>%s</lastmod></url>" % (html.escape(u), day) for u in urls]
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "\n".join(rows) + "\n</urlset>\n"), len(urls)


def slugs(d):
    return {r["slug"] for k in LISTS for r in d.get(k, [])}


def stub(target):
    to = html.escape(SITE + target)
    return ('<!doctype html>\n<html lang="en">\n<head>\n' + MARK + '\n<meta charset="utf-8">\n'
            '<title>This page has moved · Chaffee Provides</title>\n'
            '<link rel="canonical" href="%s">\n<meta http-equiv="refresh" content="0; url=%s">\n'
            '</head>\n<body>\n<p>This page has moved to <a href="%s">%s</a>.</p>\n</body>\n</html>\n' % (to, to, to, to))


def is_ours(path):
    try:
        return MARK in open(path, encoding="utf-8").read()
    except OSError:
        return False


def main():
    d = json.load(open(DATA, encoding="utf-8"))
    old = json.load(open(OLD, encoding="utf-8"))
    xml, n = sitemap(d)
    write(os.path.join(ROOT, "sitemap.xml"), xml)

    wanted = dict(old["pages"])
    live = slugs(d)
    for was, now in old["providers"].items():
        if now in live:
            wanted["provider/%s/" % was] = listing_url(now)
    for path, target in wanted.items():
        if path.startswith(("/", ".")) or ".." in path or not path.endswith("/"):
            sys.exit("build_seo: bad old address %r in old_urls.json" % path)
        write(os.path.join(ROOT, path.replace("/", os.sep), "index.html"), stub(target))
    # a listing that left the data loses its redirect
    gone = 0
    pdir = os.path.join(ROOT, "provider")
    for name in (os.listdir(pdir) if os.path.isdir(pdir) else []):
        if "provider/%s/" % name not in wanted and is_ours(os.path.join(pdir, name, "index.html")):
            shutil.rmtree(os.path.join(pdir, name))
            gone += 1
    print("sitemap.xml: %d addresses; %d redirects from old addresses%s"
          % (n, len(wanted), ", %d removed" % gone if gone else ""))


if __name__ == "__main__":
    main()
