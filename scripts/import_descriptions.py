"""Pull the business descriptions out of a WordPress export of the old Chaffee Provides site.

    python scripts/import_descriptions.py ../colorado-open-food-web-sources/chaffee-provides-wordpress/wordpress-export-2026-10-15.xml

Writes data/descriptions.json, keyed by Food Web slug (like data/photos.json). Only published "provider" posts
with text are used; the text is what each business submitted to the old site. Contact details live in the
post's custom fields, not in the text, so they are not copied here.
"""
import html, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def norm(s):
    return re.sub(r"[^a-z0-9]+", "", html.unescape(s).lower())

def field(item, tag):
    m = re.search(r"<%s>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</%s>" % (tag, tag), item, re.S)
    return m.group(1) if m else ""

def clean(text):
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n\n", text)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    paras = [re.sub(r"[ \t]+", " ", p).strip() for p in re.split(r"\n+", text)]
    return "\n".join(p for p in paras if p)

def main(xml_path):
    xml = Path(xml_path).read_text(encoding="utf-8")
    data = json.loads((ROOT / "data" / "chaffee-provides.json").read_text(encoding="utf-8"))
    records = data["producers"] + data["markets"] + data["access_points"]
    by_slug = {p["slug"]: p for p in records}
    by_name = {norm(p["name"]): p for p in records}
    out, unmatched = {}, []
    for item in re.findall(r"<item>(.*?)</item>", xml, re.S):
        if field(item, "wp:post_type") != "provider" or field(item, "wp:status") != "publish":
            continue
        text = clean(field(item, "content:encoded"))
        if not text:
            continue
        title, wp_slug = html.unescape(field(item, "title")), field(item, "wp:post_name")
        rec = by_slug.get(wp_slug) or by_name.get(norm(title))
        if not rec:
            unmatched.append(title)
            continue
        out[rec["slug"]] = text
    note = ("Descriptions each business submitted to the old Chaffee Provides site, from the WordPress export of "
            "Oct 15, 2026; reuse approved by Guidestone Colorado, who review them before publishing. Keyed by Food Web slug.")
    (ROOT / "data" / "descriptions.json").write_text(
        json.dumps({"note": note, "descriptions": dict(sorted(out.items()))}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote %d descriptions" % len(out))
    if unmatched:
        print("no match in the export for:", "; ".join(unmatched))

if __name__ == "__main__":
    main(sys.argv[1])
